import unittest
import tempfile
from pathlib import Path
import json
from unittest.mock import MagicMock,patch
from app import worker_runtime
from app.browser import launch_apply


class WindowOwnerTests(unittest.TestCase):
    def test_login_wait_never_collects_storage_or_navigates_again(self):
        from app import qr_login_worker as owner
        context=MagicMock();page=context.new_page.return_value
        page.url='https://example.test/login'
        page.is_closed.side_effect=[False,True]
        context.new_cdp_session.return_value.send.return_value={'targetInfo':{'targetId':'stable'}}
        row={'payload':json.dumps({'url':'https://example.test/login'}),'job_id':None}
        with patch.object(owner.qr,'get_request',return_value=row),patch.object(owner.qr,'validate_destination'), \
             patch.object(owner.qr,'connect'),patch.object(owner,'candidate_id',return_value='default'), \
             patch.object(owner,'active_id',return_value='default'),patch.object(owner,'runtime_profile',return_value={}), \
             patch.object(owner,'_open_browser',return_value=(MagicMock(),context,'cdp')),patch.object(owner,'sync_playwright'):
            owner.run('qr',owner_token='owner')
        context.storage_state.assert_not_called()
        page.goto.assert_called_once_with('https://example.test/login',wait_until='domcontentloaded',timeout=35000)
        page.reload.assert_not_called()

    def test_desktop_worker_does_not_inherit_control_input_pipe(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(worker_runtime,'data_dir',return_value=Path(folder)), \
             patch.object(worker_runtime,'_workers',{}),patch.object(worker_runtime.subprocess,'Popen') as spawn:
            worker_runtime._launch('app.qr_inspect_worker','test')
            self.assertEqual(spawn.call_args.kwargs['stdin'],worker_runtime.subprocess.DEVNULL)

    def test_passive_window_does_not_block_another_application(self):
        process=MagicMock();process.poll.return_value=None
        with patch.object(worker_runtime,'_workers',{('app.qr_login_worker','qr'):(process,None)}):
            self.assertTrue(worker_runtime.any_running())
            self.assertFalse(worker_runtime.any_running(include_handoffs=False))
        with patch.object(worker_runtime,'_workers',{('app.apply_worker',1):(process,None)}):
            self.assertTrue(worker_runtime.any_running(include_handoffs=False))

    def test_platform_retains_window_before_launching_application_worker(self):
        with patch('app.browser_control.require_connection'),patch('app.qr_application.ensure_application_window') as retain,patch('app.browser.launch') as launch:
            launch_apply(6,qr_request_id='a'*32)
            retain.assert_called_once_with('a'*32)
            launch.assert_called_once_with('app.apply_worker',6,'--qr-request','a'*32)
