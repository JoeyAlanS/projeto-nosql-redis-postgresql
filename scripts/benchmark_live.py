"""Estado atual vs estado atual; resumos mantidos em cada escrita nos dois bancos."""
import json,statistics,time,hashlib
from datetime import datetime,timezone
from app.store import ROOT,pg_connect,redis_connect
from app.live import PostgresLive,RedisLive


def main():
    raw=[];results={}
    with pg_connect() as pg,redis_connect() as rd:
        pg.autocommit=True
        stores={'postgres':PostgresLive(pg),'redis':RedisLive(rd)}
        original={src:s.latest(501) for src,s in stores.items()}
        assert original['postgres']==original['redis']
        cases={
            'estado_sensor':lambda s:s.latest(501),
            'resumo_global':lambda s:s.summary(),
            'resumo_local':lambda s:s.summary('Laboratório'),
            'top_20_alertas':lambda s:s.alerts(limit=20),
            'atualizar_estado_e_indicadores':lambda s:s.write(501,1900000000,3350,5100),
        }
        try:
            for name,run in cases.items():
                for _ in range(3):
                    values=[run(s) for s in stores.values()];assert values[0]==values[1]
                timings={src:[] for src in stores}
                for rep in range(30):
                    order=['postgres','redis'] if rep%2==0 else ['redis','postgres']
                    pair=[]
                    for position,src in enumerate(order):
                        start=time.perf_counter_ns();data=run(stores[src]);ms=(time.perf_counter_ns()-start)/1e6
                        timings[src].append(ms);pair.append(data)
                        raw.append(dict(case=name,repetition=rep+1,position=position+1,source=src,elapsed_ms=ms,
                                        result_sha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()))
                    assert pair[0]==pair[1]
                results[name]={src:dict(median_ms=statistics.median(v),p95_ms=statistics.quantiles(v,n=100,method='inclusive')[94],samples=len(v)) for src,v in timings.items()}
                print(name,json.dumps(results[name]),flush=True)
        finally:
            for src,s in stores.items():
                row=original[src]
                if row:s.write(501,row['ts'],row['temperature_centi'],row['humidity_centi'])
                else:s.write(501,remove=True)
        assert stores['postgres'].summary()==stores['redis'].summary()
        before=rd.info('commandstats')
        for _ in range(10):
            stores['redis'].latest(501);stores['redis'].summary();stores['redis'].alerts(limit=20)
        after=rd.info('commandstats')
        commands={k.removeprefix('cmdstat_'):(v['calls']-before.get(k,{}).get('calls',0))/10 for k,v in after.items()
                  if v['calls']>before.get(k,{}).get('calls',0) and k!='cmdstat_info'}
        plans={name:pg.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql).fetchone()['QUERY PLAN'] for name,sql in {
            'state':'SELECT * FROM live_states WHERE sensor_id=501',
            'summary':"SELECT * FROM live_summaries WHERE scope='all'",
            'alerts':'SELECT sensor_id,temperature_centi FROM live_states WHERE temperature_centi>3200 ORDER BY temperature_centi DESC,sensor_id DESC LIMIT 20'}.items()}
        states=pg.execute('SELECT count(*) AS n FROM live_states').fetchone()['n']
        report=dict(executed_at=datetime.now(timezone.utc).isoformat(),model='Central de estado atual e alertas',
            operational_states=states,historical_readings=pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n'],
            repetitions=30,warmup=3,concurrency=1,results=results,responses_equal=True,
            measurement='Cliente, rede e desserialização; conexões reutilizadas; escrita SQL inclui COMMIT autocommit',
            maintenance='Ambos mantêm resumo global/local e índice de temperatura em cada escrita',
            limitations=['Redis AOF everysec e PostgreSQL synchronous_commit: durabilidade de confirmação diferente.',
                'Um cliente, máquina compartilhada, cache aquecido; não mede saturação.',
                'Estado atual de 1000 sensores; não equivale a resumir 1M/5M leituras históricas.',
                'Escritas atualizam repetidamente o sensor 501 e seus índices/resumos; não representam distribuição multi-sensor.'],
            redis_read_commands_per_three_queries=commands,postgres_plans=plans,
            code_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app/live.py','sql/live.sql','scripts/benchmark_live.py']})
        path=ROOT/'results/live';path.mkdir(exist_ok=True)
        (path/'benchmark.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        (path/'samples.json').write_text(json.dumps(raw,indent=2)+'\n')


if __name__=='__main__':main()
