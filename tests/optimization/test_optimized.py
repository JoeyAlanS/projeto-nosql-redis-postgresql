"""Regressões em bancos reais: limites, extremos e consistência após escritas."""
import random
import json
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from app.store import Busy, Conflict, PostgresStore, RedisStore, pg_connect, redis_connect
from app.redis_optimized import PREFIX, STATE
from app.postgres_rollup import PostgresRollupStore, prepare


class OptimizedContracts(unittest.TestCase):
    def setUp(self):
        self.pg, self.rd = pg_connect(), redis_connect()
        self.pg.autocommit = True
        self.sql = PostgresStore(self.pg)
        self.fast = RedisStore(self.rd, optimized=True)
        self.slow = RedisStore(self.rd, optimized=False)
        self.materialized = False
        self.ids = list(range(9_000_001_001,9_000_001_031))
        self.start = 1_900_022_400  # Um intervalo externo à massa do projeto.
        self.start = self.start//86400*86400

    def tearDown(self):
        for rid in self.ids:
            for store in (self.sql,self.fast):
                if store.point(rid): store.delete(rid)
        if self.materialized:
            prepare(self.pg)
        self.pg.close(); self.rd.close()

    def row(self,i,**kwargs):
        return dict(id=self.ids[i],sensor_id=1,ts=self.start+i*300,temperature_centi=2000+i*100,humidity_centi=4000,**kwargs)

    def create(self,row):
        self.sql.create(row); self.fast.create(row)

    def equivalent(self,start=None,end=None):
        lo = self.start if start is None else start
        hi = self.start+3*86400 if end is None else end
        expected = self.sql.summary([1,2],lo,hi)
        self.assertEqual(expected,self.slow.summary([1,2],lo,hi))
        self.assertEqual(expected,self.fast.summary([1,2,1],lo,hi))
        for sid in (1,2):
            self.assertEqual(self.sql.history(sid,lo,hi,1000),self.fast.history(sid,lo,hi,1000))
        return expected

    def test_create_update_move_delete_extremes_and_empty_bucket(self):
        for i,t in enumerate([-5000,-5000,3200,3201,10000]):
            self.create(dict(self.row(i),temperature_centi=t))
        self.assertEqual(self.equivalent()['alerts'],2)
        # Um dos mínimos duplicados é removido; o outro deve permanecer.
        for i in (0,4):
            self.sql.delete(self.ids[i]); self.fast.delete(self.ids[i]); self.equivalent()
        moved = dict(self.row(1),sensor_id=2,ts=self.start+86400,temperature_centi=0)
        self.sql.update(moved['id'],moved); self.fast.update(moved['id'],moved); self.equivalent()
        for i in (1,2,3):
            self.sql.delete(self.ids[i]); self.fast.delete(self.ids[i]); self.equivalent()
        self.assertEqual(self.equivalent()['count'],0)
        self.assertFalse(self.rd.exists(f'{PREFIX}:sensor:1:day:{self.start}'))

    def test_inclusive_partial_midnight_empty_and_materialized(self):
        for i,dt in enumerate((0,1,86399,86400,86401,172800)):
            self.create(dict(self.row(i),ts=self.start+dt))
        prepare(self.pg)
        self.materialized = True
        rollup = PostgresRollupStore(self.pg)
        for lo,hi in ((0,0),(1,86399),(86399,86400),(2,86398),(0,172800),(1,172799)):
            expected = self.equivalent(self.start+lo,self.start+hi)
            self.assertEqual(expected,rollup.summary([1,2],self.start+lo,self.start+hi))
        self.assertEqual(self.fast.summary([],1,2)['count'],0)

    def test_conflicting_update_does_not_change_derived_indexes(self):
        self.create(self.row(0)); self.create(self.row(1))
        before = self.equivalent()
        with self.assertRaises(Conflict):
            self.fast.update(self.ids[1],dict(self.row(1),ts=self.start))
        self.assertEqual(before,self.equivalent())

    def test_random_updates_and_deletes_match_sql(self):
        rng = random.Random(42)
        for i in range(20): self.create(self.row(i))
        for i in range(20):
            row = dict(self.row(i),sensor_id=1+i%2,ts=self.start+86400*(i%3)+i,
                       temperature_centi=rng.randint(-5000,10000),humidity_centi=rng.randint(0,10000))
            self.sql.update(row['id'],row); self.fast.update(row['id'],row)
            self.equivalent()
        for rid in rng.sample(self.ids[:20],20):
            self.sql.delete(rid); self.fast.delete(rid); self.equivalent()

    def test_concurrent_writers_keep_hash_and_rollups_equivalent(self):
        def insert(i):
            with redis_connect() as r: RedisStore(r).create(self.row(i))
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(insert,range(20)))
        for i in range(20): self.sql.create(self.row(i))
        self.equivalent()

    def test_full_index_keeps_large_id_exact(self):
        rid = 8_999_999_999_999_999
        row = dict(self.row(0),id=rid)
        try:
            self.create(row)
            self.assertEqual(self.fast.history(1,self.start,self.start),[row])
            self.fast.update(rid,dict(row,temperature_centi=-1))
            self.assertEqual(self.fast.delete(rid)['id'],rid)
        finally:
            for s in (self.sql,self.fast):
                if s.point(rid): s.delete(rid)

    def test_building_blocks_writes_before_mutation(self):
        # Muda apenas a sinalização e restaura mesmo em falha; sem apagar dados.
        self.rd.set(STATE,'building')
        try:
            with self.assertRaises(Busy): self.fast.create(self.row(0))
            with self.assertRaises(Busy): self.fast.delete(self.ids[0])
            self.assertIsNone(self.fast.point(self.ids[0]))
        finally:
            self.rd.set(STATE,'ready')

    def test_api_strategy_selector_and_unavailable_optimization(self):
        root='http://127.0.0.1:8000/api/query?source=redis&operation=history&sensor_id=1&limit=3'
        outputs=[]
        for mode in ('baseline','optimized'):
            with urllib.request.urlopen(root+'&redis_mode='+mode) as response:
                value=json.load(response)
            self.assertEqual(value['strategy'],'redis_'+mode)
            outputs.append(value['data'])
        self.assertEqual(*outputs)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(root+'&redis_mode=invalid')
        self.assertEqual(caught.exception.code,422)
        self.rd.set(STATE,'building')
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(root+'&redis_mode=optimized')
            self.assertEqual(caught.exception.code,503)
            with urllib.request.urlopen(root) as response:
                self.assertEqual(json.load(response)['strategy'],'redis_baseline')
        finally:
            self.rd.set(STATE,'ready')


if __name__ == '__main__': unittest.main()
