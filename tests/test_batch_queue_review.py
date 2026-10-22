import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, batch_review_worker
from app.services.application_service import ApplicationService


class BatchQueueReviewTests(unittest.TestCase):
    def test_queue_scope_excludes_unqueued_finished_and_already_reviewed_jobs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(db, 'DB_PATH', Path(folder)/'jobs.db'):
            db.init_db()
            with db.connect() as c:
                for i in range(1, 7):
                    c.execute('INSERT INTO jobs(id,url,title) VALUES(?,?,?)',(i,f'https://example.test/{i}',str(i)))
                for i, status in [(1,'queued'),(2,'waiting_user'),(3,'done'),(4,'queued'),(5,'queued')]:
                    c.execute('INSERT INTO application_queue(job_id,status) VALUES(?,?)',(i,status))
                c.execute("UPDATE jobs SET application_status='submitted' WHERE id=4")
                c.execute("UPDATE jobs SET review_verdict='APPLY' WHERE id=5")
            with patch.object(batch_review_worker, 'review_via_chatgpt_web', return_value={'verdict':'HUMAN_REVIEW'}) as review, patch('builtins.print'):
                batch_review_worker.main('queued')
                self.assertEqual([call.args[0] for call in review.call_args_list],[1,2])

    def test_review_scope_validation_and_no_concurrent_browser_worker(self):
        with patch('app.services.application_service.launch_batch_review') as launch, patch('app.worker_runtime.any_running',return_value=False):
            ApplicationService().queue_batch_review('queued')
            launch.assert_called_once_with('queued')
        with patch('app.worker_runtime.any_running',return_value=True), patch('app.services.application_service.launch_batch_review') as launch:
            with self.assertRaises(ValueError):ApplicationService().queue_batch_review('queued')
            launch.assert_not_called()
