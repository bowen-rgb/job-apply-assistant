"""Regressions for observed review timeouts and distinct clarification actions."""
import json
import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import chatgpt_bridge as bridge, db, review_gaps, match_review as flow
from tests import test_automatic_review as fixtures


class ResponseProgressTests(unittest.TestCase):
    def test_generation_cannot_extend_wait_without_limit(self):
        clock = [0.0]
        page = MagicMock()
        page.wait_for_timeout.side_effect = lambda ms: clock.__setitem__(0, clock[0] + ms / 1000)
        with patch.object(bridge.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(bridge, 'check_cancelled'), \
             patch.object(bridge, '_response_failure', return_value=None), \
             patch.object(bridge, '_page_json', return_value=None), \
             patch.object(bridge, '_is_generating', return_value=True), \
             patch.object(bridge, '_assistant_messages', return_value=[]), \
             patch.object(bridge, '_diagnostic'):
            with self.assertRaises(bridge.PlaywrightTimeoutError):
                bridge._wait_response(page, 'final-review', [], [], 3)
        self.assertEqual(clock[0], 9)

    def test_timeout_retries_only_the_owned_review_tab_once(self):
        first, second, context = MagicMock(), MagicMock(), MagicMock()
        context.new_page.side_effect = [first, second]
        expected = {'verdict': 'APPLY', 'confidence': 95, 'summary': 'Verified fixture'}
        with patch.object(bridge, 'CHATGPT_LOCK'), patch.object(bridge, '_find_prompt'), \
             patch.object(bridge, '_set_prompt'), patch.object(bridge, '_assistant_messages', return_value=[]), \
             patch.object(bridge, '_diagnostic'), \
             patch.object(bridge, '_wait_response', side_effect=[bridge.PlaywrightTimeoutError('No ChatGPT response detected'), expected]):
            self.assertEqual(bridge.ask_chatgpt_json(context, 'Fixture review', {}, purpose='final-review'), expected)
            self.assertEqual(context.new_page.call_count, 2)
            context.close.assert_not_called()
            first.reload.assert_not_called()

    def test_active_generation_is_not_cut_off_at_initial_response_timeout(self):
        clock = [0.0]
        page = MagicMock()
        page.wait_for_timeout.side_effect = lambda ms: clock.__setitem__(0, clock[0] + ms / 1000)
        expected = {'verdict': 'APPLY', 'confidence': 95, 'summary': 'Verified fixture'}
        with patch.object(bridge.time, 'time', side_effect=lambda: clock[0]), \
             patch.object(bridge.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(bridge, 'check_cancelled'), \
             patch.object(bridge, '_response_failure', return_value=None), \
             patch.object(bridge, '_page_json', side_effect=lambda *args: expected if clock[0] >= 4 else None), \
             patch.object(bridge, '_is_generating', side_effect=lambda page: clock[0] < 4), \
             patch.object(bridge, '_assistant_messages', return_value=[]), \
             patch.object(bridge, '_diagnostic'):
            self.assertEqual(bridge._wait_response(page, 'final-review', [], [], 3), expected)


class ClarificationActionTests(unittest.TestCase):
    def setUp(self):
        fixtures.AutomaticReviewTests.setUp(self)
        profile = patch.object(review_gaps, 'load_profile_raw', side_effect=lambda: copy.deepcopy(self.profile))
        profile.start(); self.addCleanup(profile.stop)

    def test_personal_facts_public_research_and_answered_reviews_are_distinct(self):
        questions = {
            1: {'kind': 'candidate', 'question': 'Personal project evidence?'},
            2: {'kind': 'posting', 'question': 'Public role start date?'},
            3: {'kind': 'candidate', 'question': 'Confirmed skill evidence?'},
        }
        with db.connect() as conn:
            for identifier in (2, 3):
                conn.execute("INSERT INTO jobs(id,url,title,company,decision,review_verdict) VALUES(?,?,?,?,?,?)",
                             (identifier, f'https://fixture.test/{identifier}', 'Fixture role', 'Example', 'keep', 'HUMAN_REVIEW'))
            for identifier, gap in questions.items():
                conn.execute('UPDATE jobs SET review_json=? WHERE id=?',
                             (json.dumps({'verdict': 'HUMAN_REVIEW', 'preparation_readiness': 'blocked', 'blockers': [gap]}), identifier))
        self.profile['background'] = {'review_answers': [
            {'job_id': 3, 'question': 'Confirmed skill evidence?', 'answer': 'User-confirmed fixture', 'reusable': False, 'source': 'user_confirmed'}]}
        data = review_gaps.snapshot()
        self.assertEqual(data['actions']['personal_input']['job_ids'], [1])
        self.assertEqual(data['actions']['public_research']['job_ids'], [2])
        self.assertEqual(data['actions']['rereview']['job_ids'], [3])
        self.assertEqual([data['actions'][key]['count'] for key in ('personal_input', 'public_research', 'rereview')], [1, 1, 1])

    def test_queued_and_processing_records_are_not_actionable_again(self):
        with db.connect() as conn:
            conn.execute('UPDATE jobs SET review_json=? WHERE id=1', (json.dumps({'verdict':'HUMAN_REVIEW','blockers':[{'kind':'posting','question':'Date?'}]}),))
            conn.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'queued')")
        data = review_gaps.snapshot()
        self.assertEqual(data['items'], [])
        self.assertTrue(all(row['count'] == 0 for row in data['actions'].values()))

    def test_mixed_gaps_overlap_but_do_not_authorize_rereview_before_personal_answer(self):
        items = [{'id':1,'processing':False,'questions':[
            {'kind':'candidate','question':'Personal evidence?'},
            {'kind':'posting','question':'Public date?'}]}]
        actions = review_gaps.action_sets(items, [])
        self.assertEqual(actions['personal_input']['job_ids'], [1])
        self.assertEqual(actions['public_research']['job_ids'], [1])
        self.assertEqual(actions['rereview']['job_ids'], [])
        items[0]['processing'] = True
        self.assertTrue(all(row['count'] == 0 for row in review_gaps.action_sets(items, []).values()))

    def test_strong_review_skips_unanswered_personal_gaps_and_research_targets_only_public_gaps(self):
        with db.connect() as conn:
            conn.execute('UPDATE jobs SET review_json=? WHERE id=1', (json.dumps({'blockers':[{'kind':'candidate','question':'Evidence?'}]}),))
            conn.execute("INSERT INTO jobs(id,url,title,company,decision,review_verdict,review_json) VALUES(2,'https://fixture.test/2','Public','Example','keep','HUMAN_REVIEW',?)",
                         (json.dumps({'blockers':[{'kind':'posting','question':'Date?'}]}),))
            conn.execute("INSERT INTO jobs(id,url,title,company,decision) VALUES(3,'https://fixture.test/3','Initial','Example','keep')")
        self.assertEqual([row['id'] for row in flow.action_candidates('strong')], [3])
        self.assertEqual([row['id'] for row in flow.action_candidates('research')], [2])
        self.assertEqual(flow.action_candidates('rereview'), [])

    def test_personal_only_blocker_does_not_trigger_identical_second_review(self):
        with db.connect() as conn:
            job = dict(conn.execute('SELECT * FROM jobs WHERE id=1').fetchone())
        result={'verdict':'HUMAN_REVIEW','blockers':[{'kind':'candidate','question':'Evidence?'}]}
        with patch.object(flow,'load_profile_raw',return_value=self.profile), \
             patch.object(flow,'review_via_chatgpt_web',return_value=result) as reviewer, \
             patch('app.review_research.collect') as research:
            self.assertEqual(flow.review_one(job), 'HUMAN_REVIEW')
        reviewer.assert_called_once_with(1)
        research.assert_not_called()

    def test_research_batch_stops_at_its_targets_instead_of_expanding_into_initial_reviews(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO jobs(id,url,title,company,decision) VALUES(2,'https://fixture.test/2','Initial','Example','keep')")
        with patch.object(flow,'data_dir',return_value=Path(self.temp.name)), \
             patch.object(flow,'load_profile_raw',return_value=self.profile), \
             patch.object(flow,'review_one',return_value='HUMAN_REVIEW') as review:
            flow.save({'phase':'starting','mode':'research','targets':[1]})
            flow.run()
            self.assertEqual([call.args[0]['id'] for call in review.call_args_list], [1])
            self.assertEqual(flow.saved_state()['phase'], 'done')
            self.assertEqual(flow.saved_state()['total'], 1)
