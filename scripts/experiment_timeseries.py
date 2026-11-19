"""Prova isolada de RedisTimeSeries com 10 mil leituras reais (não é a API).

Cria séries temporárias por sensor/métrica, testa agregação, alteração,
exclusão e compactação; apaga somente as próprias chaves ao terminar.
"""
import json
import statistics
import time
import uuid
from datetime import datetime, timezone

from app.store import ROOT, PostgresStore, RedisStore, pg_connect, redis_connect


def summary(rd, run, start, end):
    specs = [('temperature','count'),('temperature','sum'),('humidity','sum'),
             ('alert','sum'),('temperature','min'),('temperature','max')]
    with rd.pipeline(transaction=True) as p:
        for metric, aggregation in specs:
            p.execute_command('TS.MRANGE',start*1000,end*1000,'ALIGN',start*1000,
                              'AGGREGATION',aggregation,(end-start+1)*1000,
                              'FILTER',f'run={run}',f'metric={metric}')
        replies = p.execute()
    values = [[int(float(sample[1])) for series in reply for sample in series[2]] for reply in replies]
    count,tsum,hsum,alerts,lows,highs = values
    return dict(count=sum(count),sensors=sum(v>0 for v in count),temperature_sum=sum(tsum),
                humidity_sum=sum(hsum),alerts=sum(alerts),minimum=min(lows,default=None),maximum=max(highs,default=None))


def main():
    run = uuid.uuid4().hex
    keys = []
    with pg_connect() as pg, redis_connect() as rd:
        rows = pg.execute('SELECT * FROM readings ORDER BY ts,id LIMIT 10000').fetchall()
        if len(rows) != 10000:
            raise SystemExit('Este exemplo requer ao menos 10 mil leituras')
        start,end = rows[0]['ts'], rows[-1]['ts']
        ids = sorted({r['sensor_id'] for r in rows})
        def key(sid,metric): return f'demo:timeseries:{run}:{sid}:{metric}'
        try:
            with rd.pipeline(transaction=False) as p:
                for sid in ids:
                    for metric in ('temperature','humidity','alert'):
                        k=key(sid,metric); keys.append(k)
                        p.execute_command('TS.CREATE',k,'DUPLICATE_POLICY','LAST','LABELS','run',run,'metric',metric,'sensor',sid)
                compact=key(ids[0],'hour_count'); keys.append(compact)
                p.execute_command('TS.CREATE',compact)
                p.execute_command('TS.CREATERULE',key(ids[0],'temperature'),compact,'AGGREGATION','count',3600000)
                p.execute()
                for i,row in enumerate(rows,1):
                    args=[]
                    for metric,value in [('temperature',row['temperature_centi']),('humidity',row['humidity_centi']),('alert',int(row['temperature_centi']>3200))]:
                        args.extend([key(row['sensor_id'],metric),row['ts']*1000,value])
                    p.execute_command('TS.MADD',*args)
                    if i%1000==0: p.execute()
                p.execute()
            expected = PostgresStore(pg).summary(ids,start,end)
            assert expected['count']==10000, 'O intervalo selecionado contém registros adicionais'
            methods={'postgres_raw':lambda:PostgresStore(pg).summary(ids,start,end),
                     'redis_optimized':lambda:RedisStore(rd).summary(ids,start,end),
                     'redis_timeseries':lambda:summary(rd,run,start,end)}
            for _ in range(2):
                for fn in methods.values(): assert fn()==expected
            samples=[]
            for rep in range(10):
                sources=list(methods); sources=sources[rep%3:]+sources[:rep%3]
                for source in sources:
                    begin=time.perf_counter_ns(); actual=methods[source](); ms=(time.perf_counter_ns()-begin)/1e6
                    assert actual==expected
                    samples.append(dict(repetition=rep+1,source=source,elapsed_ms=ms))
            compact_before=rd.execute_command('TS.RANGE',compact,'-','+','LATEST')
            first=rows[0]; ts=first['ts']*1000; sid=first['sensor_id']
            with rd.pipeline(transaction=True) as p:
                p.execute_command('TS.ADD',key(sid,'temperature'),ts,10000)
                p.execute_command('TS.ADD',key(sid,'alert'),ts,1)
                p.execute()
            updated=summary(rd,run,start,end)
            assert updated==dict(expected,temperature_sum=expected['temperature_sum']-first['temperature_centi']+10000,
                                 alerts=expected['alerts']-int(first['temperature_centi']>3200)+1,maximum=10000)
            with rd.pipeline(transaction=True) as p:
                for metric in ('temperature','humidity','alert'): p.execute_command('TS.DEL',key(sid,metric),ts,ts)
                p.execute()
            remaining=rows[1:]
            wanted=dict(count=9999,sensors=len({r['sensor_id'] for r in remaining}),
                        temperature_sum=sum(r['temperature_centi'] for r in remaining),humidity_sum=sum(r['humidity_centi'] for r in remaining),
                        alerts=sum(r['temperature_centi']>3200 for r in remaining),minimum=min(r['temperature_centi'] for r in remaining),maximum=max(r['temperature_centi'] for r in remaining))
            assert summary(rd,run,start,end)==wanted
            compact_after=rd.execute_command('TS.RANGE',compact,'-','+','LATEST')
            assert sum(float(v) for _,v in compact_before)-sum(float(v) for _,v in compact_after)==1
            result=dict(executed_at=datetime.now(timezone.utc).isoformat(),records=10000,sensors=len(ids),
                        redis_version=rd.info('server')['redis_version'],equivalent=True,repetitions=10,warmup=2,
                        median_ms={s:statistics.median(r['elapsed_ms'] for r in samples if r['source']==s) for s in methods},
                        samples=samples,update_verified=True,delete_verified=True,compaction_verified=True,
                        compact_before=compact_before,compact_after=compact_after,
                        scope='Experimento isolado de 10 mil leituras. Não substitui os índices/CRUD da API nem representa ensaio de 1M/5M.')
        finally:
            for offset in range(0,len(keys),500):
                rd.unlink(*keys[offset:offset+500])
        result['temporary_keys_removed']=not any(rd.exists(k) for k in keys)
        directory=ROOT/'results/otimizacao'; directory.mkdir(exist_ok=True)
        (directory/'timeseries.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='samples'},indent=2,ensure_ascii=False))


if __name__=='__main__': main()
