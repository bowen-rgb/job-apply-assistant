import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import browser_control as control, db, queue_manager as queue
from app import browser
from fastapi.testclient import TestClient
from app.main import app


class BrowserControlTests(unittest.TestCase):
    def response(self, product='Chrome/143', agent='Chrome/143'):
        return io.StringIO(json.dumps({'Browser':product,'User-Agent':agent,'webSocketDebuggerUrl':'ws://127.0.0.1:9222/devtools/browser/example'}))

    def test_wrong_browser_and_nonlocal_configuration_are_not_ready(self):
        for product, agent in [('Edg/143','Edg/143'),('Chrome/143','Chrome/143 Edg/143'),('HeadlessChrome/143','HeadlessChrome/143')]:
            with patch.object(control,'urlopen',return_value=self.response(product,agent)):
                self.assertEqual(control.status({})['state'],'wrong_browser')
        for endpoint in ['http://example.org:9222','http://localhost:9222/private','https://localhost:9222','http://user:pass@localhost:9222']:
            with patch.object(control,'urlopen') as network:
                self.assertEqual(control.status({'chrome_cdp_endpoint':endpoint})['state'],'configuration')
                network.assert_not_called()

    def test_explicit_platform_start_uses_chrome_only_without_starting_workers(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(control,'ROOT',Path(folder)),patch.object(control,'chrome_executable',return_value=Path(folder)/'chrome.exe'),patch.object(control,'status',side_effect=[{'ready':False,'state':'disconnected'},{'ready':True,'state':'ready'}]),patch.object(control.subprocess,'Popen') as launch:
            self.assertTrue(control.start({})['ready'])
            args=launch.call_args.args[0]
            self.assertTrue(args[0].endswith('chrome.exe'))
            self.assertIn('--remote-debugging-address=127.0.0.1',args)
            self.assertIn('--remote-debugging-port=9222',args)
            self.assertFalse(any('edge' in arg.lower() or 'apply_worker' in arg for arg in args))

    def test_connected_browser_is_reused_and_missing_chrome_has_no_fallback(self):
        with patch.object(control,'status',return_value={'ready':True}),patch.object(control.subprocess,'Popen') as launch:
            self.assertTrue(control.start({})['ready']);launch.assert_not_called()
        with patch.object(control,'status',return_value={'ready':False,'state':'disconnected'}),patch.object(control,'chrome_executable',return_value=None),patch.object(control.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError):control.start({})
            launch.assert_not_called()

    def test_browser_api_does_not_launch_queue_or_apply_worker(self):
        ready={'ready':True,'state':'ready','browser':'Chrome/143'}
        with TestClient(app) as client, patch.object(control,'status',return_value=ready), patch.object(control,'start',return_value=ready) as start, patch('app.main.queue_status',return_value={'running':False}), patch('app.main.queue_start') as queue_start, patch.object(browser,'launch') as worker:
            self.assertEqual(client.get('/api/browser').json(),ready)
            start.assert_not_called()
            self.assertEqual(client.post('/api/browser/start').json(),ready)
            start.assert_called_once_with()
            queue_start.assert_not_called()
            worker.assert_not_called()
        with TestClient(app) as client, patch.object(control,'start',side_effect=ValueError('Chrome unavailable')), patch('app.main.queue_status',return_value={'running':False}):
            self.assertEqual(client.post('/api/browser/start').status_code,409)
        with TestClient(app) as client, patch('app.main.queue_start',side_effect=ValueError('Chrome unavailable')):
            response=client.post('/api/queue/start?mode=batch')
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()['detail'],'Chrome unavailable')

    def test_worker_cannot_launch_when_browser_preflight_fails(self):
        with patch.object(control,'require_connection',side_effect=ValueError('Chrome unavailable')),patch.object(browser,'launch') as launch:
            with self.assertRaises(ValueError):browser.launch_apply(1,privacy_confirmed=True)
            launch.assert_not_called()
        with patch.object(control,'require_connection',return_value={'ready':True}),patch.object(browser,'launch') as launch:
            browser.launch_apply(1,privacy_confirmed=True)
            launch.assert_called_once_with('app.apply_worker',1,'--privacy-confirmed')

    def test_disconnected_queue_does_not_claim_jobs_or_spawn_workers(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(db,'DB_PATH',Path(folder)/'jobs.db'):
            db.init_db()
            with db.connect() as connection:
                connection.execute("INSERT INTO jobs(id,url,title) VALUES(1,'https://example.test/job','Example')")
                connection.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'queued')")
            queue._set(running=False,paused=True)
            with patch.object(control,'require_connection',side_effect=ValueError('Chrome disconnected')),patch.object(queue.threading,'Thread') as thread:
                with self.assertRaises(ValueError):queue._start('batch')
                thread.assert_not_called()
            self.assertEqual(queue.status()['items'][0]['attempts'],0)
            self.assertEqual(queue.status()['items'][0]['status'],'queued')
            self.assertFalse(queue.status()['running'])
            self.assertTrue(queue.status()['paused'])
