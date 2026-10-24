"""Regression tests for anonymous access, authenticated callers and upload limits."""
import base64
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from app import app, config


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'QUOTE_ENGINE_AUTH_TOKEN': 'unit-test-only-token'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = app.test_client()
        self.header = {'X-Quote-Engine-Token': 'unit-test-only-token'}
        self.basic = {'Authorization': 'Basic ' + base64.b64encode(b'admin:unit-test-only-token').decode()}

    def test_anonymous_read_and_write_routes_are_blocked(self):
        for path in ('/', '/settings', '/api/settings', '/api/config', '/api/materials'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        for path in ('/api/settings', '/api/slice', '/api/calculate-quote'):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={}).status_code, 401)

    def test_missing_token_fails_closed_and_health_stays_public(self):
        with patch.dict(os.environ, {'QUOTE_ENGINE_AUTH_TOKEN': ''}):
            self.assertEqual(self.client.get('/api/config', headers=self.header).status_code, 503)
            self.assertEqual(self.client.get('/health').json, {'status': 'ok'})
            self.assertNotEqual(self.client.post('/health').status_code, 200)

    def test_invalid_and_query_tokens_do_not_authenticate(self):
        self.assertEqual(self.client.get('/api/config?token=unit-test-only-token').status_code, 401)
        self.assertEqual(self.client.get('/api/config', headers={'X-Quote-Engine-Token': 'wrong'}).status_code, 401)

    def test_browser_and_api_read_access(self):
        for headers in (self.header, self.basic):
            for path in ('/', '/settings', '/api/settings', '/api/config'):
                with self.subTest(path=path, method=list(headers)[0]):
                    response = self.client.get(path, headers=headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_cross_site_basic_writes_blocked(self):
        for extra in ({'Origin': 'https://other.example'}, {'Sec-Fetch-Site': 'cross-site'}, {'Origin': 'null'}):
            self.assertEqual(self.client.post('/api/settings', json={}, headers={**self.basic, **extra}).status_code, 403)

    def test_authenticated_settings_save_uses_temporary_file(self):
        from config import Config
        with tempfile.TemporaryDirectory() as folder:
            temporary_config = Config(os.path.join(folder, 'config.json'))
            with patch('app.config', temporary_config):
                data = temporary_config.config_data
                response = self.client.post('/api/settings', json=data, headers={**self.basic, 'Origin': 'http://localhost'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get('/api/settings', headers=self.header).json['settings'], data)

    def test_authenticated_upload_rejects_oversize_before_slicing(self):
        with patch('app.convert_stl_to_gcode') as slicer:
            response = self.client.post('/api/slice', headers=self.header,
                data={'file': (io.BytesIO(b'x' * (20 * 1024 * 1024 + 1)), 'large.stl')})
            self.assertEqual(response.status_code, 413)
            self.assertIn('20MB', response.json['error'])
            slicer.assert_not_called()

    def test_authenticated_upload_reaches_validation(self):
        self.assertEqual(self.client.post('/api/slice', headers=self.header).status_code, 400)


if __name__ == '__main__':
    unittest.main()
