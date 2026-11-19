"""Diagnóstico reproduzível; preserva leituras e resultados dos ensaios anteriores.

Compara parsers, mede comandos internos e testa respostas prontas temporárias.
Execute sozinho: INFO commandstats é global e tráfego externo contamina deltas.
"""
import argparse
import hashlib
import json
import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis
from redis._parsers.resp2 import _RESP2Parser
from redis._parsers.hiredis import _HiredisParser

from app.store import ROOT, PostgresStore, RedisStore, pg_connect
from app.postgres_rollup import PostgresRollupStore, prepare


def measure_variants(variants, expected, repetitions, samples, case):
    for _ in range(3):
        for run in variants.values():
            assert run() == expected
    timings = {name: [] for name in variants}
    names = list(variants)
    for rep in range(repetitions):
        order = names[rep % len(names):] + names[:rep % len(names)]
        for position, name in enumerate(order):
            start = time.perf_counter_ns()
            value = variants[name]()
            elapsed = (time.perf_counter_ns() - start) / 1e6
            assert value == expected, (case, name)
            digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
            samples.append(dict(case=case, variant=name, repetition=rep+1,
                                position=position+1, elapsed_ms=elapsed, result_sha256=digest))
            timings[name].append(elapsed)
    result = {name: dict(median_ms=statistics.median(values), min_ms=min(values),
                        max_ms=max(values), samples=len(values)) for name, values in timings.items()}
    print(case, json.dumps(result), flush=True)
    return result


def command_profile(rd, run, repetitions=5):
    run()  # Script carregado antes do perfil.
    before = rd.info('commandstats')
    for _ in range(repetitions):
        run()
    after = rd.info('commandstats')
    changes = {}
    for command, stats in after.items():
        previous = before.get(command, {})
        calls = stats['calls'] - previous.get('calls', 0)
        if calls and command != 'cmdstat_info':
            changes[command.removeprefix('cmdstat_')] = dict(
                calls_per_query=calls/repetitions,
                server_ms_per_query=(stats['usec']-previous.get('usec', 0))/1000/repetitions)
    # EVALSHA já inclui seus comandos internos; os tempos não devem ser somados.
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=30)
    parser.add_argument('--output', default='results/diagnostico')
    args = parser.parse_args()
    if args.repetitions < 10:
        parser.error('Use pelo menos 10 repetições')
    directory = ROOT/args.output
    directory.mkdir(parents=True, exist_ok=True)
    load = json.loads((ROOT/'results/load.json').read_text())
    samples, results = [], {}
    clients = {name: redis.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True,
                parser_class=cls) for name, cls in [('python', _RESP2Parser), ('hiredis', _HiredisParser)]}
    snapshot_key = 'demo:diagnostico:'+uuid.uuid4().hex
    try:
        with pg_connect() as pg:
            pg.autocommit = True
            sql = PostgresStore(pg)
            ids = [r['id'] for r in sql.sensors()]
            fast = {name: RedisStore(rd, optimized=True) for name, rd in clients.items()}
            start, end = load['start'], load['end']
            assert sql.summary(ids,start,end) == fast['hiredis'].summary(ids,start,end)
            prepare(pg)  # Controle SQL atualizado, fora da cronometragem.
            rollup = PostgresRollupStore(pg)
            cases = {
                'Q1_ID': (lambda s:s.point(500001)),
                'Q2_200': (lambda s:s.history(501,start,end,200)),
                'Q3_10000': (lambda s:s.summary(ids,start,start+2700)),
                'Q3_total': (lambda s:s.summary(ids,start,end)),
                'Q3_sensor': (lambda s:s.summary([501],start,end)),
            }
            for name, run in cases.items():
                variants = {'postgres':lambda run=run:run(sql),
                            **{'redis_'+p:lambda s=s,run=run:run(s) for p,s in fast.items()}}
                if name.startswith('Q3'):
                    variants['postgres_preagregado'] = lambda run=run:run(rollup)
                results[name] = measure_variants(variants,run(sql),args.repetitions,samples,name)
            results['selecao_sensores'] = measure_variants(
                {'postgres':lambda:sql.sensors(), **{'redis_'+p:lambda s=s:s.sensors() for p,s in fast.items()}},
                sql.sensors(),args.repetitions,samples,'selecao_sensores')
            if hasattr(sql, 'sensor_ids'):
                results['selecao_somente_ids'] = measure_variants(
                    {'postgres':lambda:sql.sensor_ids(), **{'redis_'+p:lambda s=s:s.sensor_ids() for p,s in fast.items()}},
                    ids,args.repetitions,samples,'selecao_somente_ids')
            profiles = {name:command_profile(clients['hiredis'],lambda run=run:run(fast['hiredis']))
                        for name,run in cases.items()}
            profiles['selecao_sensores'] = command_profile(clients['hiredis'],fast['hiredis'].sensors)
            # Protótipo: mesma resposta de sete campos, pronta em AMBOS os bancos.
            # Não atende filtros arbitrários nem mantém CRUD: mede somente leitura.
            snapshot = sql.summary(ids,start,end)
            assert fast['hiredis'].summary(ids,start,end) == snapshot
            pg.execute('CREATE TEMP TABLE diagnostic_summary (payload jsonb NOT NULL)')
            pg.execute('INSERT INTO diagnostic_summary VALUES (%s::jsonb)',(json.dumps(snapshot),))
            clients['hiredis'].hset(snapshot_key,mapping=snapshot)
            clients['hiredis'].expire(snapshot_key,300)
            results['resposta_pronta'] = measure_variants({
                'postgres':lambda:pg.execute('SELECT payload FROM diagnostic_summary').fetchone()['payload'],
                'redis_hiredis':lambda:{k:int(v) for k,v in clients['hiredis'].hgetall(snapshot_key).items()},
            },snapshot,args.repetitions,samples,'resposta_pronta')
            plans = {'Q2':pg.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT * FROM readings WHERE sensor_id=501 AND ts BETWEEN %s AND %s ORDER BY ts,id LIMIT 200',(start,end)).fetchone()['QUERY PLAN']}
            rd = clients['hiredis']; info = rd.info()
            report = dict(executed_at=datetime.now(timezone.utc).isoformat(),records=load['records'],
                dataset_sha256=load['csv_sha256'],repetitions=args.repetitions,warmup=3,
                measurement='Cliente Python, conexões reutilizadas, ordem rotativa, respostas iguais, sem HTTP',
                results=results,command_profiles=profiles,plans=plans,
                environment={k:info[k] for k in ['redis_version','used_memory_human','evicted_keys','blocked_clients']},
                redis_config=rd.config_get('io-threads','appendfsync'),
                versions={'redis_py':redis.__version__,'hiredis':__import__('hiredis').__version__},
                code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                             ['app/store.py','app/redis_optimized.py','app/postgres_rollup.py']},
                limitations=['Diagnóstico atual somente com a base principal de 1 milhão.',
                    'INFO mede tempo interno acumulado, não rede, parser ou HTTP; EVALSHA inclui comandos internos.',
                    'Resposta pronta é protótipo estático e temporário em ambos; não implementa invalidação/CRUD.',
                    'Máquina compartilhada; medianas não são garantia geral de desempenho.'])
            (directory/'latency.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            (directory/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
    finally:
        clients['hiredis'].unlink(snapshot_key)
        for client in clients.values():
            client.close()
    print('Diagnóstico salvo em',directory)


if __name__ == '__main__':
    main()
