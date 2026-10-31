import unittest
from tests import test_automatic_review as fixture
from app import db
from app.review_inventory import snapshot


class InventoryTests(unittest.TestCase):
    setUp=fixture.AutomaticReviewTests.setUp

    def test_queue_membership_changes_refresh_even_when_counts_stay_equal(self):
        with db.connect() as c:
            for identifier in (2,3):
                c.execute('INSERT INTO jobs(id,url,decision) VALUES(?,?,?)',(identifier,f'https://fixture.test/{identifier}','low'))
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(2,'queued')")
        first=snapshot()
        with db.connect() as c:
            c.execute('DELETE FROM application_queue WHERE job_id=2')
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(3,'queued')")
        second=snapshot()
        self.assertEqual(first['queue_counts'],second['queue_counts'])
        self.assertEqual(first['counts'],second['counts'])
        self.assertNotEqual(first['queue_revision'],second['queue_revision'])

    def test_cumulative_reviews_survive_rereview_and_queue_mapping_changes_live(self):
        with db.connect() as c:
            c.execute("UPDATE jobs SET reviewed_at='2026-10-31',review_json='{\"verdict\":\"HUMAN_REVIEW\"}' WHERE id=1")
            c.execute("INSERT INTO applications(job_id,status,note) VALUES(1,'chatgpt_review','HUMAN_REVIEW')")
        first=snapshot()
        self.assertEqual(first['cumulative']['reviewed'],1)
        with db.connect() as c:
            c.execute("UPDATE jobs SET review_verdict='RUNNING' WHERE id=1")
        self.assertEqual(snapshot()['cumulative']['reviewed'],1)
        with db.connect() as c:
            c.execute("UPDATE jobs SET review_verdict='APPLY' WHERE id=1")
            c.execute("INSERT INTO applications(job_id,status,note) VALUES(1,'chatgpt_review','APPLY')")
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'queued')")
        queued=snapshot()
        self.assertEqual(queued['cumulative']['reviewed'],1)
        self.assertEqual(queued['cumulative']['queued'],1)
        self.assertEqual(queued['job_ids']['queued'],[1])
        with db.connect() as c:c.execute('DELETE FROM application_queue WHERE job_id=1')
        self.assertEqual(snapshot()['cumulative']['queued'],0)
        # Rescoring is not a reason to forget an already completed review.
        with db.connect() as c:c.execute("UPDATE jobs SET decision='low' WHERE id=1")
        self.assertEqual(snapshot()['cumulative']['reviewed'],1)
        self.assertEqual(snapshot()['cumulative']['reviewed_job_ids'],[1])

    def test_every_strong_match_has_one_current_stage_and_counts_reconcile(self):
        with db.connect() as c:
            for identifier,verdict,status in [(2,'',''),(3,'RUNNING',''),(4,'APPLY',''),(5,'SKIP',''),(6,'ERROR',''),(7,'APPLY','submitted'),(8,'APPLY','')]:
                c.execute('INSERT INTO jobs(id,url,decision,review_verdict,application_status) VALUES(?,?,?,?,?)',(identifier,f'https://example.test/{identifier}','keep',verdict,status))
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(8,'queued')")
        data=snapshot()
        self.assertEqual(data['total'],8)
        self.assertEqual(sum(data['counts'].values()),8)
        ids=[identifier for group in data['job_ids'].values() for identifier in group]
        self.assertEqual(len(set(ids)),8)
        self.assertEqual(data['job_ids']['needs_information'],[1])
        self.assertEqual(data['job_ids']['queued'],[8])
        with db.connect() as c:c.execute("UPDATE jobs SET review_verdict='HUMAN_REVIEW' WHERE id=2")
        updated=snapshot()
        self.assertEqual(updated['counts']['pending'],0)
        self.assertEqual(updated['counts']['needs_information'],2)
        with db.connect() as c:c.execute("UPDATE application_queue SET status='cancelled' WHERE job_id=8")
        cancelled=snapshot()
        self.assertEqual(cancelled['counts']['inactive'],1)
        self.assertEqual(cancelled['counts']['queued'],0)
        self.assertEqual(sum(cancelled['counts'].values()),cancelled['total'])
