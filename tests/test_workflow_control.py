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

    def test_batch_prepares_each_job_once_and_leaves_manual_submission(self):
        queue.enqueue([1, 2, 2])
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', return_value='prefilled'):
            queue._worker('batch')
        self.assertEqual([call.args[0] for call in launch.call_args_list], [1, 2])
        self.assertEqual(queue.status()['counts'], {'waiting_user': 2})
        self.assertFalse(queue.status()['running'])
        with patch.object(queue, 'launch_apply') as launch:
            queue._worker('batch')
        launch.assert_not_called()

    def test_batch_pauses_on_missing_input_or_failure(self):
        for result, expected in [('needs_human', 'waiting_user'), ('error', 'error')]:
            with self.subTest(result=result):
                with db.connect() as c:
                    c.execute('DELETE FROM application_queue')
                queue.enqueue([1, 2])
                with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', return_value=result):
                    queue._worker('batch')
                launch.assert_called_once_with(1)
                items = {x['job_id']: x for x in queue.status()['items']}
                self.assertEqual(items[1]['status'], expected)
                self.assertEqual(items[2]['status'], 'queued')
                self.assertTrue(queue.status()['paused'])

    def test_batch_snapshot_leaves_new_arrivals_for_the_next_start(self):
        queue.enqueue([1])
        def complete(*args, **kwargs):
            queue.enqueue([2])
            return 'prefilled'
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', side_effect=complete):
            queue._worker('batch')
        launch.assert_called_once_with(1)
        self.assertEqual(queue.status()['counts'], {'queued': 1, 'waiting_user': 1})

    def test_bulk_enqueue_does_not_retry_failed_entries(self):
        queue.enqueue([1])
        with db.connect() as c:
            c.execute("UPDATE application_queue SET status='error' WHERE job_id=1")
        queue.enqueue([1, 2])
        items = {x['job_id']: x for x in queue.status()['items']}
        self.assertEqual(items[1]['status'], 'error')
        self.assertEqual(items[2]['status'], 'queued')

    def test_batch_launch_exception_does_not_advance(self):
        queue.enqueue([1, 2])
        with patch.object(queue, 'launch_apply', side_effect=RuntimeError('Browser unavailable')):
            queue._worker('batch')
        items = {x['job_id']: x for x in queue.status()['items']}
        self.assertEqual(items[1]['status'], 'error')
        self.assertEqual(items[2]['status'], 'queued')

    def test_removing_active_batch_job_pauses_even_when_completion_arrives_late(self):
        queue.enqueue([1, 2])
        def complete_after_removal(*args, **kwargs):
            queue.remove(1)
            return 'prefilled'
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', side_effect=complete_after_removal), patch.object(queue, 'cancel'):
            queue._worker('batch')
        launch.assert_called_once_with(1)
        items = {x['job_id']: x for x in queue.status()['items']}
        self.assertEqual(items[1]['status'], 'cancelled')
        self.assertEqual(items[2]['status'], 'queued')

    def test_explicit_retry_of_handoff_does_not_reuse_stale_terminal_state(self):
        queue.enqueue([1])
        with db.connect() as c:
            c.execute("UPDATE application_queue SET status='waiting_user' WHERE job_id=1")
            c.execute("UPDATE jobs SET application_status='needs_human' WHERE id=1")
        queue.enqueue([1])  # Adding the same job is not an implicit retry.
        self.assertEqual(queue.status()['items'][0]['status'], 'waiting_user')
        queue.retry(1)
        with patch.object(queue, 'launch_apply') as launch, patch.object(queue, '_wait_until_prepared', return_value='prefilled'):
            queue._worker()
        launch.assert_called_once_with(1)

    def test_mark_submitted_finishes_queue_and_cannot_be_requeued_or_retried(self):
        from app.repositories import JobRepository
        queue.enqueue([1])
        with db.connect() as c:
            c.execute("UPDATE application_queue SET status='waiting_user' WHERE job_id=1")
        JobRepository().set_application_status(1, 'submitted')
        self.assertEqual(queue.status()['items'][0]['status'], 'done')
        queue.enqueue([1])
        self.assertEqual(queue.status()['items'][0]['status'], 'done')
        with self.assertRaises(ValueError):
            queue.retry(1)
        queue.clear_finished()
        queue.enqueue([1])
        self.assertEqual(queue.status()['items'], [])

    def test_active_queue_item_cannot_be_retried(self):
        queue.enqueue([1])
        with db.connect() as c:
            c.execute("UPDATE application_queue SET status='running' WHERE job_id=1")
        with self.assertRaises(ValueError):
            queue.retry(1)

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
