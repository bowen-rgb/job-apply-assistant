import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app import dashboard_entry as entry


class DashboardEntryTests(unittest.TestCase):
    def fixture(self, root, **changes):
        logs=root/'data/server-logs';logs.mkdir(parents=True)
        state={'pid':123,'instance':'test','control':str(logs/'test.stop')}
        (logs/'latest.json').write_text(json.dumps(state))
        live={'application':'job-apply-assistant','pid':123,
              'dashboard_owned':True,'host_instance':'test',**changes}
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(live).encode()
        return logs,response

    def test_stop_rejects_other_process_without_creating_control_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);logs,response=self.fixture(root,pid=999)
            with patch.object(entry,'ROOT',root),patch.object(entry.urllib.request,'urlopen',return_value=response):
                with self.assertRaises(ValueError):entry.stop()
            self.assertFalse((logs/'test.stop').exists())

    def test_stop_signals_owned_instance_and_observes_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);logs,response=self.fixture(root)
            with patch.object(entry,'ROOT',root),patch.object(entry.urllib.request,'urlopen',side_effect=[response,OSError()]):
                entry.stop()
            self.assertTrue((logs/'test.stop').exists())

    def test_invalid_control_path_cannot_write_outside_launcher_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);logs,response=self.fixture(root)
            (logs/'latest.json').write_text(json.dumps({'pid':123,'instance':'test','control':str(root/'other.stop')}))
            with patch.object(entry,'ROOT',root),patch.object(entry.urllib.request,'urlopen',return_value=response):
                with self.assertRaises(ValueError):entry.stop()
            self.assertFalse((root/'other.stop').exists())
