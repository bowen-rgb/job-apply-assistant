import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app import workspaces, worker_runtime
import socket
import subprocess
import sys
import time
import urllib.request
import json


class DashboardLifecycleTests(unittest.TestCase):
    def test_real_backend_has_fast_probe_and_stops_on_owned_control_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0));port = sock.getsockname()[1]
            env = {**os.environ, 'JAA_WORKSPACE_HOME': folder, 'JAA_DASHBOARD_INSTANCE': 'test-instance',
                   'JAA_DASHBOARD_PORT': str(port), 'JAA_DASHBOARD_CONTROL':str(Path(folder)/'stop')}
            process = subprocess.Popen([sys.executable, '-m', 'app.dashboard_host'], env=env,
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic()+25
                while True:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/runtime', timeout=.8) as response:
                            # A Windows venv executable may redirect to its base interpreter.
                            self.assertGreater(json.load(response)['pid'], 0)
                        break
                    except OSError:
                        if process.poll() is not None or time.monotonic()>deadline:
                            if process.poll() is None:process.kill();process.wait()
                            self.fail('Backend failed startup: '+process.stderr.read().decode('utf-8',errors='replace'))
                        time.sleep(.2)
                process.stdin.close();(Path(folder)/'stop').touch()
                self.assertEqual(process.wait(timeout=12), 0)
                with socket.socket() as sock:self.assertNotEqual(sock.connect_ex(('127.0.0.1',port)), 0)
            finally:
                if process.poll() is None:process.kill();process.wait()
                process.stderr.close()

    @unittest.skipUnless(os.name == 'nt', 'Windows process job test')
    def test_forced_host_exit_reaps_descendant(self):
        script = ('from app.process_ownership import own_process_tree; import subprocess,sys; '
                  'handle=own_process_tree(); '
                  'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                  'print(child.pid,flush=True); sys.stdin.read()')
        parent = subprocess.Popen([sys.executable,'-c',script],stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            child_pid = int(parent.stdout.readline())
            import ctypes
            kernel = ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
            kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=kernel.OpenProcess(0x100000,False,child_pid)
            self.assertTrue(handle)
            try:
                parent.kill();parent.wait(timeout=5)
                self.assertEqual(kernel.WaitForSingleObject(handle,5000),0)
            finally:kernel.CloseHandle(handle)
        finally:
            if parent.poll() is None:parent.kill();parent.wait()
            parent.stdin.close();parent.stdout.close();parent.stderr.close()

    def test_installed_data_is_writable_and_separate_from_code(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'JAA_WORKSPACE_HOME': folder}):
            self.assertEqual(workspaces.profile_path('default'), Path(folder)/'profile.json')
            self.assertEqual(workspaces.data_dir('abcdef123456'), Path(folder)/'data'/'candidates'/'abcdef123456')
            self.assertEqual(workspaces.active_id(), 'default')
            identifier = workspaces.create('New person')
            self.assertTrue(workspaces.profile_path(identifier).is_file())
            self.assertEqual(workspaces.candidates()[-1]['name'], 'New person')

    def test_exit_cancels_and_reaps_only_managed_workers(self):
        import subprocess
        process = MagicMock(pid=2468)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('worker', 0)
        with tempfile.TemporaryDirectory() as folder:
            token = Path(folder)/'cancel'
            with patch.object(worker_runtime, '_workers', {('app.apply_worker', 1): (process, token)}), \
                 patch.object(worker_runtime.subprocess, 'run') as run:
                worker_runtime.terminate_all(timeout=0)
                self.assertTrue(token.exists())
                self.assertEqual(run.call_args.args[0], ['taskkill', '/PID', '2468', '/T', '/F'])
