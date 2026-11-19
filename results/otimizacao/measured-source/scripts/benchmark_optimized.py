"""Novo ensaio, separado do histórico: dados brutos vs índices e pré-agregação."""
import argparse
import csv
import hashlib
import json
import platform
import statistics
import time
from datetime import datetime, timezone

from app.store import ROOT, PostgresStore, RedisStore, pg_connect, redis_connect
from app.postgres_rollup import PostgresRollupStore, prepare, SUMMARY
from scripts.benchmark import percentile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repetitions', type=int, default=30)
    parser.add_argument('--warmup', type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 10 or args.warmup < 1:
        parser.error('Use ao menos 10 repetições e 1 aquecimento')
    directory = ROOT/'results/otimizacao'; directory.mkdir(exist_ok=True)
    load = json.loads((ROOT/'results/load.json').read_text())
    start, end = load['start'], load['end']
    raw, queries = [], []
    with pg_connect() as pg, redis_connect() as rd:
        pg.autocommit = True
        build = json.loads(rd.get('iot:opt:v1:manifest') or '{}')
        assert build.get('all_records_compared_to_postgres') and build['records'] == load['records']
        assert pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n'] == load['records']
        t = time.perf_counter(); prepare(pg); preparation = time.perf_counter()-t
        stores = {'postgres_raw': PostgresStore(pg), 'redis_baseline': RedisStore(rd, optimized=False),
                  'redis_optimized': RedisStore(rd, optimized=True), 'postgres_materialized': PostgresRollupStore(pg)}
        ids = [s['id'] for s in stores['postgres_raw'].sensors()]
        sid = min(501, load['sensors'])
        # Inclui bordas inclusivas, dias parciais, vazio, local e sensor.
        validations = []
        cases = [(ids,start,end), (ids,start,min(end,start+2700)),
                 (ids,start+86301,min(end,start+86519)), (ids[::10],start+1,end-1),
                 ([sid],start,end), ([],start,end), (ids,1,2)]
        for selected, lo, hi in cases:
            if hi < lo:
                continue
            expected = stores['postgres_raw'].summary(selected,lo,hi)
            for source in ('redis_optimized','postgres_materialized'):
                assert stores[source].summary(selected,lo,hi) == expected, (source,lo,hi)
            validations.append({'sensor_count':len(selected),'start':lo,'end':hi,'count':expected['count'],'equivalent':True})
        operations = [
            ('Q1', lambda s: s.point(min(500001,load['records'])), {'id':min(500001,load['records'])}),
            ('Q2', lambda s: s.history(sid,start,end,200), {'sensor_id':sid,'start':start,'end':end,'limit':200}),
            ('Q3', lambda s: s.summary(ids,start,end), {'sensors':len(ids),'start':start,'end':end})]
        with (directory/'benchmark_raw.csv').open('w',newline='') as output:
            writer = csv.DictWriter(output, fieldnames=['query','repetition','position','source','elapsed_ms','result_sha256'])
            writer.writeheader()
            for code, run, filters in operations:
                sources = list(stores) if code == 'Q3' else list(stores)[:3]
                expected = run(stores['postgres_raw'])
                for _ in range(args.warmup):
                    for source in sources:
                        assert run(stores[source]) == expected
                metrics = {source:[] for source in sources}
                for rep in range(args.repetitions):
                    order = sources[rep % len(sources):]+sources[:rep % len(sources)]
                    for position, source in enumerate(order,1):
                        begin = time.perf_counter_ns(); value = run(stores[source]); ms = (time.perf_counter_ns()-begin)/1e6
                        assert value == expected, (code,source,rep)
                        digest = hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                        row = dict(query=code,repetition=rep+1,position=position,source=source,elapsed_ms=ms,result_sha256=digest)
                        writer.writerow(row); output.flush(); raw.append(row); metrics[source].append(ms)
                    if (rep+1)%5 == 0:
                        print(f'{code}: {rep+1}/{args.repetitions} repetições completas',flush=True)
                metrics = {source:dict(median_ms=statistics.median(v),p95_ms=percentile(v,.95),min_ms=min(v),max_ms=max(v),samples=len(v)) for source,v in metrics.items()}
                queries.append(dict(query=code,filters=filters,metrics=metrics,equivalent=True))
                print(json.dumps(queries[-1]),flush=True)
        plans = {'Q3_materialized':pg.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+SUMMARY,
                    (ids,start,end,start,end,start,end,start,end)).fetchone()['QUERY PLAN'],
                 'Q2_postgres':pg.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT * FROM readings WHERE sensor_id=%s AND ts BETWEEN %s AND %s ORDER BY ts,id LIMIT 200',(sid,start,end)).fetchone()['QUERY PLAN']}
        (directory/'plans.json').write_text(json.dumps(plans,indent=2)+'\n')
        report = dict(executed_at=datetime.now(timezone.utc).isoformat(),records=load['records'],
            dataset_sha256=load['csv_sha256'],repetitions=args.repetitions,warmup=args.warmup,
            concurrency=1,measurement='Cliente Python: execução, rede e desserialização; conexões reutilizadas; sem HTTP',
            order='Rotação da ordem a cada repetição',cache='Aquecido; nenhum cache de respostas',
            equivalent=True,queries=queries,filtered_validations=validations,redis_build=build,
            postgres_materialization_seconds=preparation,
            postgres_materialized_bytes=pg.execute("SELECT pg_total_relation_size('readings_daily_experiment') AS n").fetchone()['n'],
            versions=dict(postgres=pg.execute('SHOW server_version').fetchone()['server_version'],redis=rd.info('server')['redis_version'],python=platform.python_version()),
            cpu=next((line.split(':',1)[1].strip() for line in open('/proc/cpuinfo') if line.startswith('model name')),''),
            code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'app/store.py',ROOT/'app/redis_optimized.py',ROOT/'app/postgres_rollup.py',ROOT/'scripts/benchmark_optimized.py']},
            limitations=['Ensaio de consulta com um cliente, não teste de saturação HTTP.',
                        'Redis mantém agregados no CRUD; view PostgreSQL é atualizada antes do ensaio e não é usada na API.',
                        'Comparação pré-agregada mede leitura; não iguala custo/frescor de manutenção nem durabilidade.',
                        'Máquina compartilhada; resultados não garantem vitória em outras cargas.'])
        (directory/'benchmark.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(f'{len(raw)} amostras reais salvas em {directory}',flush=True)


if __name__ == '__main__':
    main()
