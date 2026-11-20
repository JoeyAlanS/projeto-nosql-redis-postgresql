"""Inicializa a central uma vez a partir da última leitura histórica por sensor."""
import json,time
from datetime import datetime,timezone
from app.store import ROOT,pg_connect,redis_connect
from app.live import PREFIX,STATE,scope,EMPTY,PostgresLive,RedisLive


def main():
    begin=time.perf_counter()
    with pg_connect() as pg,redis_connect() as rd:
        if rd.get(STATE)=='ready':
            PostgresLive(pg)
            print('Central existente preservada.');return
        if not rd.set(STATE,'building',nx=True):raise RuntimeError('Preparação anterior incompleta; consulte logs antes de recuperar')
        try:
            pg.execute((ROOT/'sql/live.sql').read_text())
            pg.execute('SELECT pg_advisory_xact_lock(761193)')
            if pg.execute('SELECT count(*) AS n FROM live_states').fetchone()['n']:
                raise RuntimeError('Estados SQL já existentes; recuperação precisa preservar dados operacionais')
            rows=pg.execute('''SELECT s.id AS sensor_id,r.ts,r.temperature_centi,r.humidity_centi,s.location
              FROM sensors s CROSS JOIN LATERAL (SELECT ts,temperature_centi,humidity_centi FROM readings
              WHERE sensor_id=s.id ORDER BY ts DESC,id DESC LIMIT 1) r ORDER BY s.id''').fetchall()
            assert rows
            groups={}
            for row in rows:
                # Confere a origem em Redis, sem mudar hashes ou índices históricos.
                rid=rd.zrevrange(f'iot:sensor:{row["sensor_id"]}:readings',0,0)[0]
                original=rd.hgetall('iot:reading:'+rid)
                assert all(int(original[k])==row[k] for k in ['sensor_id','ts','temperature_centi','humidity_centi'])
                assert rd.hget(f'iot:sensor:{row["sensor_id"]}','location')==row['location']
                rd.hset(f'{PREFIX}:sensor:{row["sensor_id"]}',mapping=row)
                pg.execute('INSERT INTO live_states VALUES(%s,%s,%s,%s,%s)',tuple(row[k] for k in ['sensor_id','ts','temperature_centi','humidity_centi','location']))
                for group in ['all',scope(row['location'])]:
                    groups.setdefault(group,[]).append(row)
            for group,values in groups.items():
                temperatures=[r['temperature_centi'] for r in values]
                summary=dict(count=len(values),temperature_sum=sum(temperatures),humidity_sum=sum(r['humidity_centi'] for r in values),
                             alerts=sum(t>3200 for t in temperatures),minimum=min(temperatures),maximum=max(temperatures))
                rd.hset(f'{PREFIX}:group:{group}:summary',mapping=summary)
                rd.zadd(f'{PREFIX}:group:{group}:temperatures',{f'{r["sensor_id"]:010}':r['temperature_centi'] for r in values})
                pg.execute('INSERT INTO live_summaries VALUES(%s,%s,%s,%s,%s,%s,%s)',(group,*summary.values()))
            pg.execute('ANALYZE live_states');pg.execute('ANALYZE live_summaries')
            pg.execute('INSERT INTO live_metadata VALUES(true,true) ON CONFLICT(singleton) DO UPDATE SET ready=true')
            pg.commit()
            rd.set(STATE,'ready')
            sql,fast=PostgresLive(pg),RedisLive(rd)
            for row in rows:assert sql.latest(row['sensor_id'])==fast.latest(row['sensor_id'])==row
            for loc in [None,*{r['location'] for r in rows}]:
                assert sql.summary(loc)==fast.summary(loc)
                assert sql.alerts(loc,1000)==fast.alerts(loc,1000)
            report=dict(executed_at=datetime.now(timezone.utc).isoformat(),states=len(rows),scopes=len(groups),
                historical_readings=pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n'],
                seconds=time.perf_counter()-begin,all_states_and_summaries_equal=True,
                source='Última leitura histórica de cada sensor; central passa a evoluir independentemente via /api/live')
            path=ROOT/'results/live';path.mkdir(exist_ok=True)
            (path/'build.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
            print(json.dumps(report,indent=2,ensure_ascii=False))
        except BaseException:
            rd.set(STATE,'failed');raise


if __name__=='__main__':main()
