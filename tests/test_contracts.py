import unittest

from pydantic import ValidationError

from app.contracts import Decision, QueueRequest, TrackPatch
from app.repositories import JobRepository


class ContractTests(unittest.TestCase):
    def test_decision_contract_rejects_unknown_values(self):
        self.assertEqual(Decision(decision='keep').decision, 'keep')
        with self.assertRaises(ValidationError):
            Decision(decision='maybe')

    def test_queue_contract_requires_a_bounded_job_list(self):
        self.assertEqual(QueueRequest(job_ids=[1, 2], priority=4).priority, 4)
        with self.assertRaises(ValidationError):
            QueueRequest(job_ids=[], priority=4)

    def test_track_contract_limits_stage_vocabulary(self):
        self.assertEqual(TrackPatch(stage='interview').stage, 'interview')
        with self.assertRaises(ValidationError):
            TrackPatch(stage='phone-screen')


class RepositoryTests(unittest.TestCase):
    def test_stats_and_analytics_are_repository_owned(self):
        repository = JobRepository()
        self.assertIn('total', repository.stats())
        data = repository.analytics()
        self.assertIn('totals', data)
        self.assertIn('queue', data)


if __name__ == '__main__':
    unittest.main()
