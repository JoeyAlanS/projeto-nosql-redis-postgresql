import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from scripts.compare_scales import command
from scripts.concurrent_load import reading_id, request_reading, run_group
from scripts.load import generate_row


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        source = parse_qs(url.query).get('source', [''])[0]
        identifier = int(url.path.rsplit('/', 1)[1])
        self.send_response(503 if source == 'redis' else 200)
        self.end_headers()
        row = generate_row(identifier, 10, 42)
        if source == 'wrong':
            row['temperature_centi'] += 1
        self.wfile.write(json.dumps(row).encode())

    def log_message(self, *args):
        pass


class ScaleTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def test_sequence_covers_first_and_last_id_without_duplicates(self):
        for records in (1_000_000, 5_000_000):
            identifiers = [reading_id(i, 240, records) for i in range(240)]
            self.assertEqual((identifiers[0], identifiers[-1]), (1, records))
            self.assertEqual(len(set(identifiers)), 240)

    def test_http_success_does_not_hide_wrong_fields(self):
        expected = generate_row(1, 10, 42)
        self.assertTrue(request_reading(self.url, 'postgres', 1, expected)['valid'])
        result = request_reading(self.url, 'wrong', 1, expected)
        self.assertEqual(result['status'], 200)
        self.assertFalse(result['valid'])

    def test_workers_execute_every_request_exactly_once(self):
        metrics, samples = run_group(self.url, 'postgres', 4, 13, {'records': 1000, 'sensors': 10, 'seed': 42})
        self.assertEqual(sorted(s['request_index'] for s in samples), list(range(13)))
        self.assertEqual((metrics['successes'], metrics['errors']), (13, 0))
        self.assertGreater(metrics['successful_requests_per_second'], 0)

    def test_http_errors_count_as_failures_and_not_fast_successes(self):
        metrics, samples = run_group(self.url, 'redis', 2, 6, {'records': 1000, 'sensors': 10, 'seed': 42})
        self.assertEqual((metrics['successes'], metrics['errors']), (0, 6))
        self.assertIsNone(metrics['p95_ms'])
        self.assertTrue(all(s['status'] == 503 for s in samples))

    def test_projects_and_subnets_are_different_from_main_and_each_other(self):
        first, first_env = command(1_000_000, 'up', '-d')
        second, second_env = command(5_000_000, 'up', '-d')
        self.assertIn('iot-escala-1000000', first)
        self.assertIn('iot-escala-5000000', second)
        self.assertNotEqual(first_env['ESCALA_SUBNET'], second_env['ESCALA_SUBNET'])
        self.assertEqual(second_env['ESCALA_REGISTROS'], '5000000')
        with self.assertRaises(ValueError):
            command(10000, 'up')


if __name__ == '__main__':
    unittest.main()
