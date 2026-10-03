import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, queue_manager
from app.repositories.jobs import JobRepository
from app.services.application_service import ApplicationService
from app.scoring import evaluate


class TrackingStatesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, 'DB_PATH', Path(self.folder.name) / 'jobs.db')
        self.patch.start()
        db.init_db()
        self.jobs = JobRepository()
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,url,title,decision,review_verdict) VALUES(1,'https://example.test/1','One','reject','SKIP')")

    def tearDown(self):
        self.patch.stop()
        self.folder.cleanup()

    def test_rejection_requires_submission_and_recruiter_evidence(self):
        with self.assertRaises(ValueError):
            self.jobs.track(1, 'rejected', 'Rejection email received', source='email')
        self.assertEqual(self.jobs.stage_events(1), [])
        self.jobs.set_application_status(1, 'submitted')
        for source, note in [('', 'Rejection email'), ('email', '  '), ('invented', 'Rejection email')]:
            with self.subTest(source=source, note=note), self.assertRaises(ValueError):
                self.jobs.track(1, 'rejected', note, source=source)
        self.jobs.track(1, 'rejected', '2026-10-03: recruiter email confirms rejection', source='email')
        event = self.jobs.stage_events(1)[0]
        self.assertEqual(event['source'], 'email')
        self.assertIn('2026-10-03', event['note'])
        self.assertTrue(event['created_at'])
        self.jobs.set_application_status(1, 'submitted')
        job = self.jobs.list()[0]
        self.assertEqual(job['tracker_stage'], 'rejected')
        self.assertEqual(job['tracker_source'], 'email')

    def test_pipeline_submission_updates_status_and_ignoring_preserves_history(self):
        self.jobs.track(1, 'submitted', 'Sent on portal', source='manual')
        self.assertEqual(self.jobs.list()[0]['application_status'], 'submitted')
        self.jobs.set_decision(1, 'skipped')
        self.assertEqual(len(self.jobs.pipeline()), 1)
        self.assertEqual(self.jobs.stats()['submitted_n'], 1)
        self.assertEqual(self.jobs.stats()['total'], 0)

    def test_queue_and_prepared_stages_cannot_invent_worker_results(self):
        for stage in ['queued', 'prepared', 'withdrawn']:
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                self.jobs.track(1, stage)
        queue_manager.enqueue([1])
        self.jobs.track(1, 'queued')
        self.jobs.set_application_status(1, 'prefilled')
        self.jobs.track(1, 'prepared')

    def test_api_records_provenance_and_rejects_unsubmitted_outcomes(self):
        from fastapi.testclient import TestClient
        from app.main import app
        # Skip the unrelated startup rescore; this test owns its isolated DB.
        client = TestClient(app)
        response = client.put('/api/jobs/1/track', json={'stage':'rejected','source':'email','note':'Rejection received'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(client.post('/api/jobs/1/application-status', json={'status':'submitted'}).status_code, 200)
        self.assertEqual(client.put('/api/jobs/1/track', json={'stage':'rejected','source':'AI','note':'SKIP'}).status_code, 422)
        self.assertEqual(client.put('/api/jobs/1/track', json={'stage':'rejected','source':'email','note':'2026-10-03 email confirms rejection'}).status_code, 200)
        event = client.get('/api/jobs/1/stage-events').json()[0]
        self.assertEqual(event['stage'], 'rejected')
        self.assertEqual(event['source'], 'email')
        self.assertEqual(client.post('/api/jobs/1/apply').status_code, 409)

    def test_closed_or_submitted_jobs_are_not_prepared_or_queued(self):
        service = ApplicationService(self.jobs)
        cases = [('application_status', 'submitted'), ('application_status', 'withdrawn'),
                 ('tracker_stage', 'rejected'), ('decision', 'expired'),
                 ('availability_status', 'expired'), ('user_action', 'skipped')]
        for column, value in cases:
            with self.subTest(column=column, value=value):
                with db.connect() as c:
                    c.execute("UPDATE jobs SET application_status='',tracker_stage='',decision='keep',availability_status='unknown',user_action='' WHERE id=1")
                    c.execute(f'UPDATE jobs SET {column}=? WHERE id=1', (value,))
                    c.execute('DELETE FROM application_queue')
                with patch('app.services.application_service.launch_apply') as launch:
                    with self.assertRaises(ValueError):
                        service.prefill(1)
                    launch.assert_not_called()
                self.assertEqual(queue_manager.enqueue([1])['items'], [])

    def test_expiration_is_independent_of_contract_mismatch(self):
        score, decision, reason, flags = evaluate(
            {'title': 'CDI receptionist', 'employment_type': 'CDI', 'valid_through': '2000-01-01'},
            {'contracts': ['CDD']})
        self.assertEqual(decision, 'expired')
        self.assertIn('2000-01-01', reason)
        self.assertEqual(evaluate({'title': 'Reception', 'body': 'Offre expirée'}, {})[1], 'expired')
