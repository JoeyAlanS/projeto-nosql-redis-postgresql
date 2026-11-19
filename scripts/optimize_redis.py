"""Constrói índices adicionais a partir dos hashes reais e confere com PostgreSQL.

Execute sem outras escritas. A API atualizada rejeita escritas Redis durante
a construção. Falhas não ativam índices incompletos; --retry reinicia uma
construção interrompida, nunca substitui índices já ativos.
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

from app.redis_optimized import PREFIX, STATE, DAY, BUCKET_FIELDS
from app.store import ROOT, FIELDS, canonical, pg_connect, redis_connect, normalized


def build(pg, rd, retry=False):
    if rd.get(STATE) == 'ready':
        return {'state': 'ready', 'note': 'Índices existentes preservados'}
    if rd.get('iot:load_state') != 'complete':
        raise RuntimeError('A carga original precisa estar completa')
    if not rd.set(STATE, 'building', nx=True):
        if not retry:
            raise RuntimeError('Construção anterior em andamento/interrompida; confira o processo antes de --retry')
        # --retry exige ausência do processo anterior; não é desbloqueio automático.
        rd.set(STATE, 'building')
    before = rd.info('memory')['used_memory']
    started = time.perf_counter()
    checked = buckets_total = 0
    digest = hashlib.sha256()
    try:
        for pattern in (PREFIX + ':sensor:*',):
            batch = []
            for key in rd.scan_iter(pattern, count=2000):
                batch.append(key)
                if len(batch) >= 2000:
                    rd.unlink(*batch); batch.clear()
            if batch:
                rd.unlink(*batch)
        sensors = sorted(map(int, rd.smembers('iot:sensors')))
        for pos, sid in enumerate(sensors, 1):
            expected = pg.execute('SELECT * FROM readings WHERE sensor_id=%s ORDER BY ts,id', (sid,)).fetchall()
            ids = rd.zrange(f'iot:sensor:{sid}:readings', 0, -1, withscores=True)
            if len(ids) != len(expected):
                raise AssertionError(f'Contagem divergente no sensor {sid}')
            full, buckets = {}, {}
            for offset in range(0, len(ids), 2000):
                chunk = ids[offset:offset+2000]
                with rd.pipeline(transaction=False) as p:
                    for rid, _ in chunk:
                        p.hgetall(f'iot:reading:{rid}')
                    rows = p.execute()
                for j, (raw, (rid, score)) in enumerate(zip(rows, chunk)):
                    row = normalized(raw)
                    if row != expected[offset+j] or row['id'] != int(rid) or row['ts'] != int(score):
                        raise AssertionError(f'Leitura/índice divergente: {rid}')
                    line = canonical(row)
                    digest.update(line.encode())
                    full[line.strip()] = row['ts']
                    day = row['ts']//DAY*DAY
                    t, h, ts = row['temperature_centi'], row['humidity_centi'], row['ts']
                    b = buckets.setdefault(day, dict(zip(BUCKET_FIELDS, (0,0,0,0,t,t,ts,ts))))
                    b['count'] += 1; b['temperature_sum'] += t; b['humidity_sum'] += h
                    b['alerts'] += int(t > 3200)
                    b['minimum'] = min(b['minimum'], t); b['maximum'] = max(b['maximum'], t)
                    b['first_ts'] = min(b['first_ts'], ts); b['last_ts'] = max(b['last_ts'], ts)
                    checked += 1
            base = f'{PREFIX}:sensor:{sid}'
            with rd.pipeline(transaction=False) as p:
                if full:
                    p.zadd(base+':full', full)
                for day, b in buckets.items():
                    p.hset(f'{base}:day:{day}', mapping=b)
                if buckets:
                    p.zadd(base+':days', {day: day for day in buckets})
                p.execute()
            # Confere também a representação que foi efetivamente gravada.
            assert dict(rd.zrange(base+':full', 0, -1, withscores=True)) == full
            with rd.pipeline(transaction=False) as p:
                for day in buckets:
                    p.hgetall(f'{base}:day:{day}')
                actual = p.execute()
            assert [{k: int(v) for k,v in b.items()} for b in actual] == list(buckets.values())
            buckets_total += len(buckets)
            if pos % 100 == 0:
                print(f'Índices: {pos}/{len(sensors)} sensores; {checked:,} leituras conferidas', flush=True)
        pg_count = pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n']
        rd_count = sum(1 for _ in rd.scan_iter('iot:reading:*', count=10000))
        assert checked == pg_count == rd_count, 'Há hashes órfãos ou leituras fora dos índices'
        report = {'executed_at': datetime.now(timezone.utc).isoformat(), 'state': 'ready',
                  'records': checked, 'sensors': len(sensors), 'daily_buckets': buckets_total,
                  'sha256_sensor_ts_id_order': digest.hexdigest(), 'all_records_compared_to_postgres': True,
                  'all_full_indexes_and_buckets_verified': True,
                  'seconds': time.perf_counter()-started, 'memory_before_bytes': before,
                  'memory_after_bytes': rd.info('memory')['used_memory'],
                  'scope': 'Índices adicionais; hashes e índices originais preservados'}
        directory = ROOT/'results/otimizacao'; directory.mkdir(exist_ok=True)
        (directory/'build.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
        with rd.pipeline(transaction=True) as p:
            p.set(PREFIX+':manifest', json.dumps(report))
            p.set(STATE, 'ready')
            p.execute()
        return report
    except BaseException:
        rd.set(STATE, 'failed')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry', action='store_true')
    args = parser.parse_args()
    with pg_connect() as pg, redis_connect() as rd:
        pg.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        print(json.dumps(build(pg, rd, args.retry), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
