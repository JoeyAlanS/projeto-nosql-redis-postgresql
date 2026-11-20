import json,random,unittest,urllib.request,urllib.error,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from app.live import RedisLive,PostgresLive,live_store,EMPTY,PREFIX
from app.store import pg_connect,redis_connect,Invalid

class LiveContracts(unittest.TestCase):
    def setUp(self):
        self.pg=pg_connect();self.pg.autocommit=True;self.rd=redis_connect()
        self.sql=PostgresLive(self.pg);self.fast=RedisLive(self.rd)
        self.saved={s:{i:store.latest(i) for i in [1,2,501]} for s,store in [('postgres',self.sql),('redis',self.fast)]}
    def tearDown(self):
        for source,store in [('postgres',self.sql),('redis',self.fast)]:
            for sid,row in self.saved[source].items():
                if row:store.write(sid,row['ts'],row['temperature_centi'],row['humidity_centi'])
                else:store.write(sid,remove=True)
        self.pg.close();self.rd.close()
    def compare(self):
        rows=self.pg.execute('SELECT * FROM live_states').fetchall()
        for loc in [None,'Laboratório','Biblioteca','inexistente']:
            subset=[r for r in rows if loc is None or r['location']==loc]
            temps=[r['temperature_centi'] for r in subset]
            expected=dict(count=len(subset),temperature_sum=sum(temps),humidity_sum=sum(r['humidity_centi'] for r in subset),
                          alerts=sum(t>3200 for t in temps),minimum=min(temps) if temps else None,maximum=max(temps) if temps else None)
            self.assertEqual(self.sql.summary(loc),expected);self.assertEqual(self.fast.summary(loc),expected)
            self.assertEqual(self.sql.alerts(loc,100),self.fast.alerts(loc,100))
    def both(self,sid,t=1,h=0,remove=False):
        for store in [self.sql,self.fast]:store.write(sid,1900000000,t,h,remove)
    def test_exact_summaries_and_rankings(self):self.compare()
    def test_duplicate_extremes_remove_and_recreate(self):
        self.both(1,10000);self.both(2,10000);self.compare()
        self.both(1,remove=True);self.compare()
        self.both(2,-5000);self.compare()
        self.both(1,-5000);self.compare()
        self.both(2,remove=True);self.compare()
    def test_repeated_replace_no_double_count_and_location_scopes(self):
        for t in [3200,3201,3300,3300,0]:self.both(501,t,10000);self.compare()
    def test_delete_absent_idempotent(self):
        self.both(501,remove=True);self.both(501,remove=True);self.compare()
    def test_empty_location_and_recreate(self):
        rows=self.pg.execute("SELECT * FROM live_states WHERE location='Laboratório'").fetchall()
        for row in rows:
            sid=row['sensor_id']
            for source,store in [('postgres',self.sql),('redis',self.fast)]:
                self.saved[source][sid]=store.latest(sid)
        for row in rows:self.both(row['sensor_id'],remove=True)
        self.assertEqual(self.fast.summary('Laboratório'),EMPTY)
        self.assertEqual(self.sql.summary('Laboratório'),EMPTY)
        self.compare()
        self.both(rows[0]['sensor_id'],3300,6000);self.compare()
    def test_history_reload_protects_operational_states(self):
        before=self.sql.summary()
        count=self.pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n']
        result=subprocess.run([sys.executable,'-m','scripts.load','--records','1000','--replace'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Central operacional preservada',result.stderr)
        self.assertEqual(self.sql.summary(),before)
        self.assertEqual(self.fast.summary(),before)
        self.assertEqual(self.pg.execute('SELECT count(*) AS n FROM readings').fetchone()['n'],count)
    def test_random_updates(self):
        rng=random.Random(17)
        for _ in range(25):
            self.both(rng.choice([1,2,501]),rng.randint(-5000,10000),rng.randint(0,10000));self.compare()
    def test_concurrent_updates_match_full_recompute(self):
        for source in ['postgres','redis']:
            def update(i):
                with live_store(source) as s:s.write([1,2,501][i%3],1900000000,3000+i,5000)
            with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(update,range(24)))
        # A ordem de chegada pode diferir; sincroniza os três estados finais.
        for sid in [1,2,501]:
            row=self.sql.latest(sid);self.fast.write(sid,row['ts'],row['temperature_centi'],row['humidity_centi'])
        self.compare()
    def test_invalid_sensor_does_not_change_summaries(self):
        for store in [self.sql,self.fast]:
            old=store.summary()
            with self.assertRaises(Invalid):store.write(2147483647,1900000000,3000,4000)
            with self.assertRaises(Invalid):store.write(1,1900000000,10001,4000)
            self.assertEqual(store.summary(),old)
    def test_queries_do_not_execute_lua_or_scan(self):
        before=self.rd.info('commandstats')
        self.fast.summary();self.fast.latest(1);self.fast.alerts(limit=20)
        after=self.rd.info('commandstats')
        for command in ['cmdstat_evalsha','cmdstat_scan','cmdstat_keys']:
            self.assertEqual(before.get(command,{}).get('calls',0),after.get(command,{}).get('calls',0))
    def test_http_crud_and_validation(self):
        for source in ['postgres','redis']:
            url=f'http://localhost:8000/api/live/sensors/501?source={source}'
            body=dict(ts=1900000000,temperature_centi=3301,humidity_centi=4500)
            with urllib.request.urlopen(urllib.request.Request(url,json.dumps(body).encode(),{'Content-Type':'application/json'},method='PUT')) as response:self.assertEqual(response.status,200)
            with urllib.request.urlopen(f'http://localhost:8000/api/live?source={source}&operation=state&sensor_id=501') as response:self.assertEqual(json.load(response)['data']['temperature_centi'],3301)
            with urllib.request.urlopen(urllib.request.Request(url,method='DELETE')) as response:self.assertEqual(response.status,200)
            with urllib.request.urlopen(f'http://localhost:8000/api/live?source={source}&operation=state&sensor_id=501') as response:self.assertIsNone(json.load(response)['data'])
        self.compare()
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen('http://localhost:8000/api/live?limit=10000')
        self.assertEqual(caught.exception.code,422)

if __name__=='__main__':unittest.main()
