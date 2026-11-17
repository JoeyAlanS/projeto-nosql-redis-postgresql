"""Demonstra EXPLAIN real do PostgreSQL e o algoritmo Redis do mesmo contrato."""
import argparse
import json

from app.store import ROOT, pg_connect, redis_connect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', choices=('Q1', 'Q2', 'Q3', 'all'), default='all')
    args = parser.parse_args()
    load = json.loads((ROOT / 'results/load.json').read_text())
    identifier, sid = min(500001, load['records']), min(501, load['sensors'])
    selected = list(range(1, min(load['sensors'], 1000) + 1))
    queries = {
        'Q1': ('SELECT * FROM readings WHERE id=%s', (identifier,)),
        'Q2': ('SELECT * FROM readings WHERE sensor_id=%s AND ts BETWEEN %s AND %s ORDER BY ts,id LIMIT 200',
               (sid, load['start'], load['end'])),
        'Q3': ('SELECT count(*),count(DISTINCT sensor_id),COALESCE(sum(temperature_centi),0),COALESCE(sum(humidity_centi),0),count(*) FILTER (WHERE temperature_centi > 3200),min(temperature_centi),max(temperature_centi) FROM readings WHERE sensor_id=ANY(%s) AND ts BETWEEN %s AND %s',
               (selected, load['start'], load['end'])),
    }
    with pg_connect() as pg, redis_connect() as rd:
        pg.autocommit = True
        for code, (sql, params) in queries.items():
            if args.query not in ('all', code):
                continue
            print(f'\n{code} / {load["records"]:,} leituras / PostgreSQL', flush=True)
            for row in pg.execute('EXPLAIN (ANALYZE,BUFFERS) ' + sql, params):
                print(row['QUERY PLAN'])
            print('Redis: caminho do código, sem otimizador SQL:')
            if code == 'Q1':
                print(f'HGETALL iot:reading:{identifier}: {rd.hlen(f"iot:reading:{identifier}")} campos existentes')
            elif code == 'Q2':
                key = f'iot:sensor:{sid}:readings'
                print(f'EVALSHA HISTORY_LUA -> ZRANGEBYSCORE {key} {load["start"]} {load["end"]} LIMIT 0 200 -> HMGET por leitura')
                print(f'Membros no período: {rd.zcount(key, load["start"], load["end"])}; retorno limitado a 200 leituras')
            else:
                with rd.pipeline(transaction=False) as pipe:
                    for sensor in selected:
                        pipe.zcount(f'iot:sensor:{sensor}:readings', load['start'], load['end'])
                    count = sum(pipe.execute())
                print(f'EVALSHA SUMMARY_LUA -> {len(selected)} ZRANGEBYSCORE -> {count:,} HMGET de temperatura/umidade -> resumo Lua')
                print('A contagem acima foi consultada nos índices. O resumo Redis completo é medido pelo benchmark; este comando não o repete.')


if __name__ == '__main__':
    main()
