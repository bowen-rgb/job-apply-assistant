import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import db, queue_manager
from app.application_overview import snapshot
from app.automatic_review import prepare
from app.human_review import can_prepare


class AutomaticReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(db, 'DB_PATH', Path(self.temp.name)/'test.db')
        self.patch.start(); self.addCleanup(self.patch.stop); db.init_db()
        self.profile = {'automation': {'chatgpt_web_reviewer': {'enabled': True}}}
        for target in ['app.automatic_review.load_profile_raw', 'app.profile_store.load_profile_raw']:
            p = patch(target, side_effect=lambda: copy.deepcopy(self.profile))
            p.start(); self.addCleanup(p.stop)
        queue_manager._stop.clear()
        self.addCleanup(lambda: queue_manager._set(running=False,paused=False,current_job_id=None))
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,url,title,company,body,decision,review_verdict) VALUES(1,'https://lab.test/1','Internship','Example Lab','Simulation','keep','HUMAN_REVIEW')")

    def job(self):
        with db.connect() as c:
            return dict(c.execute('SELECT * FROM jobs WHERE id=1').fetchone())

    def reviewer(self, verdict):
        with db.connect() as c:
            c.execute('UPDATE jobs SET review_verdict=?,review_revision=review_revision||?,review_json=? WHERE id=1',
                      (verdict, 'new', json.dumps({'verdict': verdict})))
        return {'verdict': verdict, 'summary': 'Missing dates' if verdict == 'HUMAN_REVIEW' else verdict}

    def test_start_from_ui_upgrades_old_queued_items_without_forging_approval(self):
        with db.connect() as c:
            c.execute("INSERT INTO application_queue(job_id,status,note) VALUES(1,'queued','Human confirmation required')")
        queue_manager._set(running=False,paused=False)
        with patch('app.browser_control.require_connection'), patch('app.queue_manager.threading.Thread') as thread:
            queue_manager.start('batch',auto_review=True)
            thread.return_value.start.assert_called_once()
        self.assertEqual(self.job()['automatic_review_requested'],1)
        self.assertNotEqual(self.job()['human_review_status'],'approved')
        self.assertEqual(queue_manager.status()['items'][0]['note'],'Automatic AI review pending')

    def test_automatic_queue_reviews_twice_and_does_not_forge_human_approval(self):
        self.assertFalse(queue_manager.enqueue([1])['items'])
        self.assertEqual(len(queue_manager.enqueue([1], auto_review=True)['items']), 1)
        calls = iter(['HUMAN_REVIEW', 'APPLY'])
        with patch('app.automatic_review.review_via_chatgpt_web', side_effect=lambda _: self.reviewer(next(calls))) as review:
            self.assertTrue(prepare(1)); self.assertEqual(review.call_count, 2)
        self.assertTrue(can_prepare(self.job()))
        self.assertNotEqual(self.job()['human_review_status'], 'approved')
        self.profile['availability'] = {'start_date': '2027-03-01'}
        self.assertFalse(can_prepare(self.job()))

    def test_unresolved_review_pauses_the_worker_without_launching_or_recording_rejection(self):
        queue_manager.enqueue([1], auto_review=True)
        with patch('app.automatic_review.review_via_chatgpt_web', side_effect=lambda _: self.reviewer('HUMAN_REVIEW')), patch('app.queue_manager.launch_apply') as launch:
            queue_manager._worker('batch'); launch.assert_not_called()
        state = queue_manager.status()
        self.assertEqual(state['items'][0]['status'], 'waiting_user')
        self.assertIn('Missing dates', state['items'][0]['note'])
        self.assertNotEqual(self.job()['tracker_stage'], 'rejected')
        queue_manager.retry(1)
        self.assertEqual(queue_manager.status()['items'][0]['status'], 'queued')

    def test_one_missing_candidate_fact_does_not_block_the_next_queue_item(self):
        from app.automatic_review import ReviewNeedsInput
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,url,title,company,decision) VALUES(2,'https://lab.test/2','Other','Example','keep')")
        queue_manager.enqueue([1,2],auto_review=True)
        visited=[]
        def review(identifier,stopped):
            visited.append(identifier)
            if identifier==1:raise ReviewNeedsInput('Missing personal qualification')
            return False
        with patch('app.automatic_review.prepare',side_effect=review),patch('app.queue_manager.launch_apply') as launch:
            queue_manager._worker('batch');launch.assert_not_called()
        self.assertEqual(visited,[1,2])
        items={row['job_id']:row for row in queue_manager.status()['items']}
        self.assertEqual(items[1]['status'],'waiting_user')
        self.assertFalse(queue_manager.status()['paused'])

    def test_intermediate_score_is_advice_not_missing_information(self):
        from app.reviewer import review_via_chatgpt_web
        profile={'chatgpt_web_reviewer':{'backend':'test'},'scoring_dimensions':[{'id':'fit','weight':1}]}
        with patch('app.reviewer.load_profile',return_value=profile),patch('app.review_research.collect',return_value={'pages':[]}),patch('app.reviewer.ask_chatgpt_json') as ask:
            for score,expected in [(3.5,'APPLY'),(2.5,'SKIP')]:
                ask.return_value={'verdict':'APPLY','preparation_readiness':'ready','ratings':{'fit':{'score':score}}}
                result=review_via_chatgpt_web(1)
                self.assertEqual(result['verdict'],expected)
                self.assertEqual(result['blockers'],[])

    def test_skip_cancel_and_changed_data_never_authorize_preparation(self):
        queue_manager.enqueue([1], auto_review=True)
        with patch('app.automatic_review.review_via_chatgpt_web', side_effect=lambda _: self.reviewer('SKIP')):
            self.assertFalse(prepare(1))
        self.assertFalse(self.job()['automatic_review_token'])
        self.assertNotEqual(self.job()['tracker_stage'], 'rejected')

    def test_posting_changes_during_review_invalidate_the_result(self):
        queue_manager.enqueue([1], auto_review=True)
        def changed(_):
            result = self.reviewer('APPLY')
            with db.connect() as c: c.execute("UPDATE jobs SET body='Different role' WHERE id=1")
            return result
        with patch('app.automatic_review.review_via_chatgpt_web', side_effect=changed):
            with self.assertRaises(ValueError): prepare(1)
        self.assertFalse(can_prepare(self.job()))


class OutcomeOverviewTests(unittest.TestCase):
    def test_rejected_excludes_matching_rejection_failures_and_silence(self):
        jobs = [dict(id=1, company='A', title='Role', application_status='submitted', tracker_stage='rejected'),
                dict(id=2, company='B', title='Role', decision='reject', application_status='error'),
                dict(id=3, company='C', title='Role', application_status='submitted', tracker_stage='submitted'),
                dict(id=4, company='D', title='Role', application_status='submitted', tracker_stage='interview'),
                dict(id=5, company='E', title='Role', application_status='submitted', tracker_stage='no_response')]
        result = snapshot(jobs, [{'job_id': 3}], [], datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(result['job_ids']['rejected'], [1])
        self.assertEqual(result['job_ids']['waiting'], [3])
        self.assertEqual(result['job_ids']['responses'], [4])
        self.assertEqual(result['counts']['followups'], 1)
