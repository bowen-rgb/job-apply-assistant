import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, queue_manager as queue, apply_worker
from app.human_review import confirmation_status, review_token
from app.repositories.jobs import JobRepository
from app.services.application_service import ApplicationService


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(db,'DB_PATH',Path(self.folder.name)/'test.db')
        self.db_patch.start()
        db.init_db()
        self.jobs=JobRepository()
        queue._stop.clear()
        queue._set(running=False,paused=False,current_job_id=None)
        with db.connect() as c:
            c.execute("""INSERT INTO jobs(id,url,title,body,decision,review_verdict,review_revision)
                        VALUES(1,'https://example.test/1','Green','CDD reception','keep','APPLY','first'),
                              (2,'https://example.test/2','Orange','Dates to check','review','HUMAN_REVIEW','first')""")

    def tearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()
        queue._stop.clear()
        queue._set(running=False,paused=False,current_job_id=None)

    def job(self,id):
        return next(j for j in self.jobs.list() if j['id']==id)

    def confirm(self,id,status='approved'):
        self.jobs.confirm_review(id,status,self.job(id)['human_review_token'])

    def test_green_and_orange_require_confirmation_for_individual_and_queue_preparation(self):
        self.assertEqual(self.jobs.stats()['human_n'],2)
        for id in [1,2]:
            self.assertEqual(self.job(id)['human_review_status'],'pending')
            self.assertEqual(queue.enqueue([id])['items'],[])
            with patch('app.services.application_service.launch_apply') as launch:
                with self.assertRaises(ValueError):ApplicationService(self.jobs).prefill(id)
                launch.assert_not_called()
            self.confirm(id)
            with patch('app.services.application_service.launch_apply') as launch:
                ApplicationService(self.jobs).prefill(id)
                launch.assert_called_once_with(id)
        self.assertEqual(self.jobs.stats()['human_n'],0)
        self.assertEqual(len(queue.enqueue([1,2])['items']),2)
        self.assertEqual(self.job(1)['review_verdict'],'APPLY')
        self.assertEqual(self.job(2)['review_verdict'],'HUMAN_REVIEW')

    def test_changed_review_or_job_invalidates_confirmation_and_stale_requests(self):
        for field,value in [('review_revision','second'),('body','New hours'),('valid_through','2030-01-01')]:
            with self.subTest(field=field):
                self.confirm(1)
                old=self.job(1)['human_review_token']
                with db.connect() as c:c.execute(f'UPDATE jobs SET {field}=? WHERE id=1',(value,))
                self.assertEqual(self.job(1)['human_review_status'],'pending')
                with self.assertRaises(ValueError):self.jobs.confirm_review(1,'approved',old)
                with self.assertRaises(ValueError):self.jobs.assert_preparable(1)
        self.confirm(1)
        with db.connect() as c:c.execute("UPDATE jobs SET last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=1")
        self.assertEqual(self.job(1)['human_review_status'],'approved')

    def test_declining_or_undoing_does_not_become_recruiter_rejection(self):
        self.confirm(1)
        queue.enqueue([1])
        self.confirm(1,'declined')
        job=self.job(1)
        self.assertEqual(job['human_review_status'],'declined')
        self.assertEqual(job['review_verdict'],'APPLY')
        self.assertNotEqual(job['tracker_stage'],'rejected')
        self.assertEqual(queue.status()['items'][0]['status'],'cancelled')
        with self.assertRaises(ValueError):queue.retry(1)
        self.confirm(1,'pending')
        self.assertEqual(self.jobs.stats()['human_n'],2)
        self.assertEqual([e['status'] for e in self.jobs.human_review_history(1)],['pending','declined','approved'])

    def test_legacy_queue_pauses_until_confirmation_and_retry_rechecks(self):
        with db.connect() as c:c.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'queued')")
        with patch.object(queue,'launch_apply') as launch:
            queue._worker('batch')
            launch.assert_not_called()
        self.assertTrue(queue.status()['paused'])
        self.assertEqual(queue.status()['items'][0]['status'],'queued')
        self.confirm(1)
        with patch.object(queue,'launch_apply') as launch,patch.object(queue,'_wait_until_prepared',return_value='prefilled'):
            queue._worker('batch')
            launch.assert_called_once_with(1)
        with db.connect() as c:c.execute("UPDATE jobs SET review_revision='new' WHERE id=1")
        with self.assertRaises(ValueError):queue.retry(1)

    def test_api_rejects_invalid_or_stale_confirmation(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client=TestClient(app)
        token=self.job(1)['human_review_token']
        self.assertEqual(client.post('/api/jobs/1/human-review',json={'status':'approved','review_token':token}).status_code,200)
        self.assertEqual(client.post('/api/jobs/1/human-review',json={'status':'APPLY','review_token':token}).status_code,422)
        with db.connect() as c:c.execute("UPDATE jobs SET review_revision='new' WHERE id=1")
        self.assertEqual(client.post('/api/jobs/1/human-review',json={'status':'approved','review_token':token}).status_code,409)
        self.assertEqual(client.get('/api/jobs/1/human-review-events').json()[0]['status'],'approved')

    def test_worker_rechecks_confirmation_before_browser_or_letter_generation(self):
        with patch.object(apply_worker,'_open_browser') as browser,patch.object(apply_worker,'generate_letter') as letter:
            with self.assertRaises(ValueError):apply_worker.main(1)
            browser.assert_not_called()
            letter.assert_not_called()
        self.assertEqual(self.job(1)['application_status'],'error')
        self.assertEqual(self.jobs.history(1)[0]['note'],'Human confirmation required')
