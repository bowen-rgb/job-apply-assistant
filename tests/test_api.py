import unittest
from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def test_health_is_local_and_lists_adapters(self):
        with TestClient(app) as c:
            r = c.get('/api/health')
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertTrue(data['local_only'])
            self.assertGreaterEqual(len(data['ats_adapters']), 8)

    def test_profile_schema_is_v8(self):
        with TestClient(app) as c:
            r = c.get('/api/profile')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['schema_version'], 8)

    def test_queue_pipeline_and_analytics_endpoints(self):
        with TestClient(app) as c:
            self.assertEqual(c.get('/api/queue').status_code, 200)
            self.assertEqual(c.get('/api/pipeline').status_code, 200)
            r = c.get('/api/analytics')
            self.assertEqual(r.status_code, 200)
            self.assertIn('totals', r.json())
            h = c.get('/api/health').json()
            self.assertIn('jobspy_ok', h)
            self.assertIn('scheduler', h)


if __name__ == '__main__':
    unittest.main()
