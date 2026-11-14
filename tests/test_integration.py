"""Testes de contratos nos bancos reais, incluindo índices após mutações."""
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from app.store import (Conflict, Invalid, Missing, ROOT, MAX_READING_ID,
                       MAX_SENSOR_ID, MAX_TIMESTAMP, store)


class DatabaseContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.load = json.loads((ROOT / "results/load.json").read_text())
        cls.row = dict(id=9_000_000_001, sensor_id=1, ts=cls.load["end"]+86400,
                       temperature_centi=2800, humidity_centi=6500)

    def tearDown(self):
        for source in ("postgres", "redis"):
            with store(source) as s:
                if s.point(self.row["id"]):
                    s.delete(self.row["id"])

    def test_equivalent_reads_and_empty_ranges(self):
        outputs = []
        for source in ("postgres", "redis"):
            with store(source) as s:
                outputs.append((s.point(1), s.history(1,self.load["start"],self.load["end"],200),
                                s.summary([1,2],self.load["start"],self.load["end"]),
                                s.summary([1],1,2),s.history(1,1,2)))
        self.assertEqual(*outputs)
        self.assertEqual(outputs[0][3]["count"],0)
        self.assertIsNone(outputs[0][3]["minimum"])

    def test_crud_maintains_temporal_and_unique_indexes(self):
        for source in ("postgres", "redis"):
            with self.subTest(source=source), store(source) as s:
                self.assertEqual(s.create(self.row), self.row)
                self.assertEqual(s.point(self.row["id"]), self.row)
                self.assertEqual(s.history(1,self.row["ts"],self.row["ts"]),[self.row])
                updated = dict(self.row,sensor_id=2,ts=self.row["ts"]+300,temperature_centi=3300)
                s.update(self.row["id"], updated)
                self.assertEqual(s.history(1,self.row["ts"],self.row["ts"]),[])
                self.assertEqual(s.history(2,updated["ts"],updated["ts"]),[updated])
                self.assertEqual(s.summary([2],updated["ts"],updated["ts"])["alerts"],1)
                self.assertEqual(s.delete(self.row["id"]),updated)
                self.assertIsNone(s.point(self.row["id"]))
                self.assertEqual(s.history(2,updated["ts"],updated["ts"]),[])

    def test_duplicate_and_foreign_key_rejected(self):
        for source in ("postgres", "redis"):
            with self.subTest(source=source):
                with store(source) as s:
                    row = s.point(1)
                with self.assertRaises(Conflict), store(source) as s:
                    s.create(row)
                with self.assertRaises(Conflict), store(source) as s:
                    s.create(dict(row,id=self.row["id"]))
                with self.assertRaises(Invalid), store(source) as s:
                    s.create(dict(self.row,sensor_id=self.load["sensors"]+1))

    def test_http_filters_comparison_and_validation(self):
        base = "http://127.0.0.1:8000"
        def get(path):
            with urllib.request.urlopen(base+path) as response:
                return json.load(response)
        self.assertEqual(get('/api/health'), {'postgres':'ok','redis':'ok'})
        for op in ('point','history','summary'):
            self.assertTrue(get(f'/api/compare?operation={op}&sensor_id=1')["equivalent"])
        for path in ('/api/query?start=100&end=10','/api/query?source=invalid','/api/query?operation=history',
                     '/api/query?limit=1001'):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                get(path)
            self.assertEqual(caught.exception.code,422)

    def test_http_crud_roundtrip(self):
        base = 'http://127.0.0.1:8000/api/readings'
        for source in ('postgres','redis'):
            path=f'{base}?source={source}'
            req=urllib.request.Request(path,json.dumps(self.row).encode(),{'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status,201)
            updated=dict(self.row,temperature_centi=3400)
            path=f'{base}/{self.row["id"]}?source={source}'
            req=urllib.request.Request(path,json.dumps(updated).encode(),{'Content-Type':'application/json'},method='PUT')
            with urllib.request.urlopen(req) as response:
                self.assertEqual(json.load(response),updated)
            with urllib.request.urlopen(path) as response:
                self.assertEqual(json.load(response),updated)
            with urllib.request.urlopen(urllib.request.Request(path,method='DELETE')) as response:
                self.assertEqual(response.status,200)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(path)
            self.assertEqual(caught.exception.code,404)

    def test_invalid_numbers_rejected_without_writing(self):
        invalid = [('id', 0), ('id', MAX_READING_ID + 1),
                   ('sensor_id', MAX_SENSOR_ID + 1), ('ts', MAX_TIMESTAMP + 1),
                   ('temperature_centi', -5001), ('humidity_centi', 10001)]
        for source in ('postgres', 'redis'):
            for field, value in invalid:
                row = dict(self.row, **{field: value})
                with self.subTest(source=source, field=field):
                    with self.assertRaises(Invalid), store(source) as s:
                        s.create(row)
                    req = urllib.request.Request(
                        f'http://127.0.0.1:8000/api/readings?source={source}',
                        json.dumps(row).encode(), {'Content-Type': 'application/json'}, method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(req)
                    self.assertEqual(caught.exception.code, 422)
            with store(source) as s:
                self.assertIsNone(s.point(self.row['id']))

    def test_query_and_path_integer_boundaries(self):
        paths = ['/api/query?reading_id=9000000000000001',
                 '/api/query?sensor_id=2147483648', '/api/query?start=253402300800',
                 '/api/compare?end=253402300800', '/api/compare?reading_id=0']
        for source in ('postgres', 'redis'):
            paths.extend(f'/api/readings/{rid}?source={source}'
                         for rid in (0, -1, MAX_READING_ID + 1))
        for path in paths:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen('http://127.0.0.1:8000' + path)
            self.assertEqual(caught.exception.code, 422)

    def test_conflicting_update_keeps_original_record_and_indexes(self):
        for source in ('postgres', 'redis'):
            with self.subTest(source=source):
                with store(source) as s:
                    s.create(self.row)
                    occupied = s.point(1)
                conflicting = dict(self.row, sensor_id=occupied['sensor_id'], ts=occupied['ts'])
                with self.assertRaises(Conflict), store(source) as s:
                    s.update(self.row['id'], conflicting)
                with store(source) as s:
                    self.assertEqual(s.point(self.row['id']), self.row)
                    self.assertEqual(s.history(1, self.row['ts'], self.row['ts']), [self.row])
                    self.assertEqual(s.point(1), occupied)

    def test_missing_update_and_delete(self):
        for source in ('postgres', 'redis'):
            for operation in ('update', 'delete'):
                with self.subTest(source=source, operation=operation):
                    with self.assertRaises(Missing), store(source) as s:
                        if operation == 'update':
                            s.update(self.row['id'], self.row)
                        else:
                            s.delete(self.row['id'])

    def test_redis_delete_returns_version_deleted_under_interleaved_update(self):
        updated = dict(self.row, sensor_id=2, temperature_centi=3400)
        with store('redis') as s:
            s.create(self.row)
            original_script = s._write

            def concurrent_update_then_delete(*args, **kwargs):
                # Outra conexão grava imediatamente antes da exclusão atômica.
                with store('redis') as writer:
                    writer.update(self.row['id'], updated)
                return original_script(*args, **kwargs)

            with patch.object(s, '_write', side_effect=concurrent_update_then_delete):
                self.assertEqual(s.delete(self.row['id']), updated)
            self.assertIsNone(s.point(self.row['id']))
            self.assertEqual(s.history(2, updated['ts'], updated['ts']), [])

    def test_empty_and_unknown_location_return_equivalent_empty_results(self):
        for location in ('', 'Local inexistente'):
            results = []
            for source in ('postgres', 'redis'):
                with store(source) as s:
                    ids = [r['id'] for r in s.sensors(location)]
                    self.assertEqual(ids, [])
                    results.append(s.summary(ids, self.load['start'], self.load['end']))
            self.assertEqual(*results)
            self.assertEqual(results[0]['count'], 0)


if __name__ == '__main__':
    unittest.main()
