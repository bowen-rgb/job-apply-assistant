import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from fastapi.testclient import TestClient
from app import server_launcher as launcher
from app.main import app

class ServerLauncherTests(unittest.TestCase):
    def test_runtime_identifies_shared_workspace_without_sensitive_profile(self):
        response=TestClient(app).get('/api/runtime')
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data['application'],'job-apply-assistant')
        self.assertTrue(Path(data['workspace']).is_absolute())
        self.assertNotIn('identity',data)

    def test_existing_server_is_reused_without_spawning(self):
        with patch.object(launcher,'ready',return_value=True),patch.object(launcher.subprocess,'Popen') as spawn:
            self.assertEqual(launcher.main(),0);spawn.assert_not_called()

    def test_hidden_process_logs_and_waits_for_readiness(self):
        with tempfile.TemporaryDirectory() as temp:
            process=MagicMock(pid=123);process.poll.return_value=None
            with patch.object(launcher,'ROOT',Path(temp)),patch.object(launcher,'ready',side_effect=[False,False,True]),patch.object(launcher.subprocess,'Popen',return_value=process) as spawn,patch.object(launcher.time,'sleep'):
                self.assertEqual(launcher.main(),0)
                options=spawn.call_args.kwargs
                self.assertEqual(options['creationflags'],launcher.subprocess.CREATE_NO_WINDOW)
                self.assertEqual(options['stdout'],options['stderr'])
                self.assertEqual(options['stdin'],launcher.subprocess.DEVNULL)
                self.assertEqual(json.loads((Path(temp)/'data/server-logs/latest.json').read_text())['pid'],123)
                process.kill.assert_not_called()

    def test_failed_child_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            process=MagicMock(pid=123);process.poll.return_value=1
            with patch.object(launcher,'ROOT',Path(temp)),patch.object(launcher,'ready',return_value=False),patch.object(launcher.subprocess,'Popen',return_value=process),patch('builtins.print') as message:
                self.assertEqual(launcher.main(),1)
                self.assertIn('.log',message.call_args.args[0])

    def test_favicon_and_html_reference(self):
        client=TestClient(app)
        icon=client.get('/favicon.ico');self.assertEqual(icon.status_code,200)
        self.assertIn('image/svg+xml',icon.headers['content-type'])
        self.assertIn('favicon.svg',client.get('/').text)

if __name__=='__main__':unittest.main()
