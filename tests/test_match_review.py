import json
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_automatic_review as fixtures
from app import match_review as flow, db


class MatchReviewTests(unittest.TestCase):
    setUp=fixtures.AutomaticReviewTests.setUp
    job=fixtures.AutomaticReviewTests.job

    def test_strong_matches_are_reviewed_before_queueing_and_not_submitted(self):
        with db.connect() as conn:
            for identifier,decision in [(2,'keep'),(3,'keep'),(4,'low'),(5,'keep')]:
                conn.execute('INSERT INTO jobs(id,url,title,company,decision) VALUES(?,?,?,?,?)',
                             (identifier,f'https://example.test/{identifier}','Example role','Example',decision))
            conn.execute("UPDATE jobs SET application_status='submitted' WHERE id=5")
        decisions={1:iter(['HUMAN_REVIEW','APPLY']),2:iter(['SKIP']),3:iter(['HUMAN_REVIEW','HUMAN_REVIEW'])}
        def review(identifier):
            verdict=next(decisions[identifier])
            with db.connect() as conn:
                conn.execute('UPDATE jobs SET review_verdict=?,review_revision=review_revision||? WHERE id=?',(verdict,'new',identifier))
            return {'verdict':verdict}
        with patch.object(flow,'data_dir',return_value=Path(self.temp.name)),patch.object(flow,'load_profile_raw',return_value=self.profile),patch.object(flow,'review_via_chatgpt_web',side_effect=review) as reviewer,patch('app.queue_manager.launch_apply') as submit:
            flow.run();state=flow.status()
            self.assertEqual(state['phase'],'done')
            self.assertEqual((state['completed'],state['enqueued'],state['skipped'],state['unresolved']),(3,1,1,1))
            self.assertEqual(reviewer.call_count,5);submit.assert_not_called()
            self.assertTrue(self.job()['automatic_review_token'])
            self.assertNotEqual(self.job()['human_review_status'],'approved')
            with db.connect() as conn:
                self.assertEqual([r[0] for r in conn.execute('SELECT job_id FROM application_queue')],[1])
            # Queue preparation reuses this review if posting and profile are unchanged.
            with patch('app.automatic_review.review_via_chatgpt_web') as repeat:
                from app.automatic_review import prepare
                self.assertTrue(prepare(1));repeat.assert_not_called()

    def test_login_failure_pauses_once_and_never_enqueues(self):
        with patch.object(flow,'data_dir',return_value=Path(self.temp.name)),patch.object(flow,'load_profile_raw',return_value=self.profile),patch.object(flow,'review_via_chatgpt_web',side_effect=ValueError('Login required')) as reviewer:
            flow.run();state=flow.status()
            self.assertEqual(state['phase'],'blocked');self.assertIn('Login',state['error'])
            self.assertEqual(state['enqueued'],0);self.assertEqual(reviewer.call_count,1)

    def test_changed_profile_during_review_never_authorizes_queue(self):
        def changed(identifier):
            with db.connect() as conn:conn.execute("UPDATE jobs SET review_verdict='APPLY' WHERE id=?",(identifier,))
            self.profile['availability']={'start_date':'2030-03-01'}
            return {'verdict':'APPLY'}
        import copy
        with patch.object(flow,'data_dir',return_value=Path(self.temp.name)),patch.object(flow,'load_profile_raw',side_effect=lambda:copy.deepcopy(self.profile)),patch.object(flow,'review_via_chatgpt_web',side_effect=changed):
            flow.run();self.assertEqual(flow.status()['phase'],'blocked')
            self.assertFalse(self.job()['automatic_review_token'])

    def test_scan_hook_only_runs_when_requested(self):
        with patch.object(flow,'start') as start:
            flow.after_scan({});start.assert_not_called()
            flow.after_scan({'review_and_queue_strong':True});start.assert_called_once()

    def test_platform_opens_its_own_chrome_and_launches_the_background_workflow(self):
        profile={'chatgpt_web_reviewer':{'enabled':True,'backend':'chatgpt'}}
        with patch.object(flow,'data_dir',return_value=Path(self.temp.name)), \
             patch('app.worker_runtime.any_running',return_value=False), \
             patch('app.worker_runtime.is_running',return_value=False), \
             patch('app.worker_runtime.launch') as launch, \
             patch('app.scan_manager.status',return_value={'running':False}), \
             patch('app.profile_store.runtime_profile',return_value=profile), \
             patch('app.browser_control.status',return_value={'ready':False}), \
             patch('app.browser_control.start',return_value={'ready':True}) as chrome, \
             patch('app.browser_control.require_connection'):
            flow.start()
            chrome.assert_called_once_with(profile)
            launch.assert_called_once_with('app.match_review',0)
