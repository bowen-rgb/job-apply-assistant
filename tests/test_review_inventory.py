import unittest
from tests import test_automatic_review as fixture
from app import db
from app.review_inventory import snapshot


class InventoryTests(unittest.TestCase):
    setUp=fixture.AutomaticReviewTests.setUp

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
