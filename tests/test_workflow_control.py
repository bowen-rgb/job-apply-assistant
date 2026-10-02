import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import db, queue_manager as queue, review_worker, apply_worker
from app.form_engine import generic_fill
from playwright.sync_api import sync_playwright


class QueueControlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', Path(self.folder.name) / 'test.db')
        self.db_patch.start()
        db.init_db()
        queue._stop.clear()
        queue._set(running=False, current_job_id=None, paused=False)
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,url,title) VALUES(1,'https://example.test/1','One'),(2,'https://example.test/2','Two')")

    def tearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()
        queue._stop.clear()
        queue._set(running=False, current_job_id=None, paused=False)

    def test_one_application_then_wait_for_user(self):
        queue.enqueue([1, 2])
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', return_value='prefilled'):
            queue._worker()
        launch.assert_called_once_with(1)
        items = {x['job_id']: x for x in queue.status()['items']}
        self.assertEqual(items[1]['status'], 'waiting_user')
        self.assertEqual(items[2]['status'], 'queued')
        self.assertFalse(queue.status()['running'])

    def test_stop_cancels_active_job_and_completion_cannot_overwrite_cancel(self):
        queue.enqueue([1, 2])
        entered, release = threading.Event(), threading.Event()
        def wait(*args, **kwargs):
            entered.set()
            release.wait(3)
            return 'prefilled'  # A result that arrives after cancellation.
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', side_effect=wait), patch.object(queue, 'cancel') as cancel:
            worker = threading.Thread(target=queue._worker)
            worker.start()
            self.assertTrue(entered.wait(3))
            queue.stop()
            release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            cancel.assert_called_with('app.apply_worker', 1)
            launch.assert_called_once()
        items = {x['job_id']: x for x in queue.status()['items']}
        self.assertEqual(items[1]['status'], 'cancelled')
        self.assertEqual(items[2]['status'], 'queued')

    def test_skipped_jobs_cannot_be_queued(self):
        with db.connect() as c:
            c.execute("UPDATE jobs SET user_action='skipped' WHERE id=1")
        queue.enqueue([1, 2, 2])
        self.assertEqual([x['job_id'] for x in queue.status()['items']], [2])

    def test_letter_failure_does_not_open_application_form(self):
        context = MagicMock()
        with patch.object(apply_worker, '_open_browser', return_value=(None, context, 'cdp')), \
             patch.object(apply_worker, 'select_resume_for_job', return_value=(Path(__file__), {})), \
             patch.object(apply_worker, 'generate_letter', side_effect=RuntimeError('ChatGPT unavailable')):
            with self.assertRaises(RuntimeError):
                apply_worker.main(1)
        context.new_page.assert_not_called()
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT application_status FROM jobs WHERE id=1').fetchone()[0], 'error')


class DocumentBrowserTests(unittest.TestCase):
    def test_hidden_dropzone_inputs_receive_distinct_documents_and_no_submit(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as p:
            cv, letter = Path(folder) / 'cv.pdf', Path(folder) / 'lettre.pdf'
            cv.write_bytes(b'%PDF-CV')
            letter.write_bytes(b'%PDF-Letter')
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<form onsubmit="window.submitted=true;return false">
                  <input type="email" required>
                  <div class="upload"><p>Déposez votre lettre de motivation</p><input type="file" style="display:none" accept=".pdf"></div>
                  <div class="upload"><p>Déposez votre CV ou cliquez ici</p><input type="file" style="display:none" required accept=".pdf"></div>
                  <button type="submit">Envoyer ma candidature</button></form>''')
                report = generic_fill(page, {'email': 'test@example.test', 'cover_letter_path': str(letter)}, cv)
                names = page.locator('input[type=file]').evaluate_all('(xs)=>xs.map(e=>e.files[0]?.name)')
                self.assertEqual(names, ['lettre.pdf', 'cv.pdf'])
                self.assertIn('resume', report['filled'])
                self.assertIn('cover_letter_file', report['filled'])
                self.assertFalse(page.evaluate('Boolean(window.submitted)'))
            finally:
                browser.close()

    def test_successful_review_can_be_printed_to_gbk_console(self):
        output = io.BytesIO()
        console = io.TextIOWrapper(output, encoding='gbk')
        with patch.object(review_worker, 'review_via_chatgpt_web', return_value={'verdict': 'APPLY', 'summary': 'Noël, déjà reçu'}), \
             patch.object(review_worker, 'connect') as connect, patch('sys.stdout', console):
            review_worker.main(1)
            console.flush()
        self.assertEqual(json.loads(output.getvalue().decode('gbk'))['summary'], 'Noël, déjà reçu')
        connect.assert_not_called()
