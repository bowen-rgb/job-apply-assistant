import copy
import json
import unittest
from unittest.mock import patch
from tests.test_automatic_review import AutomaticReviewTests
from app import db, review_gaps
from app.reviewer import build_review_packet, validate_review


class ReviewGapsTests(unittest.TestCase):
    setUp=AutomaticReviewTests.setUp

    def prepare(self,kind='candidate'):
        result={'manual_questions':['Old question'], 'blockers':[{'kind':kind,'question':'Python experience?','reason':'Essential skill','evidence':'Python required'}]}
        with db.connect() as c:c.execute('UPDATE jobs SET review_json=? WHERE id=1',(json.dumps(result),))

    def test_clarifications_preserve_exact_reasons_and_do_not_include_transport_errors(self):
        self.prepare()
        with patch.object(review_gaps,'load_profile_raw',return_value=self.profile):
            data=review_gaps.snapshot()
        self.assertEqual(data['items'][0]['questions'][0]['evidence'],'Python required')
        with db.connect() as c:c.execute("UPDATE jobs SET review_verdict='ERROR',review_json='{}' WHERE id=1")
        self.assertEqual(review_gaps.snapshot()['items'],[])

    def test_running_review_shows_previous_result_as_pending_then_replaces_it(self):
        self.prepare()
        with db.connect() as c:
            c.execute('UPDATE jobs SET review_verdict=?,review_json=? WHERE id=1',('RUNNING',json.dumps({'verdict':'HUMAN_REVIEW','summary':'Previous','manual_questions':['Old question']})))
        item=review_gaps.snapshot()['items'][0]
        self.assertTrue(item['processing']);self.assertEqual(item['review_summary'],'Previous')
        with db.connect() as c:
            c.execute('UPDATE jobs SET review_verdict=?,review_summary=?,review_json=?,review_revision=? WHERE id=1',('HUMAN_REVIEW','New summary',json.dumps({'verdict':'HUMAN_REVIEW','preparation_readiness':'blocked','blockers':[{'kind':'candidate','question':'New question'}]}),'new-version'))
        item=review_gaps.snapshot()['items'][0]
        self.assertFalse(item['processing']);self.assertFalse(item['legacy'])
        self.assertEqual(item['review_revision'],'new-version')
        self.assertEqual([q['question'] for q in item['questions']],['New question'])
        with db.connect() as c:c.execute("UPDATE jobs SET review_verdict='APPLY' WHERE id=1")
        self.assertEqual(review_gaps.snapshot()['items'],[])

    def test_save_is_candidate_owned_and_reuse_is_explicit(self):
        self.prepare()
        payload={'candidate_id':'default','job_id':1,'question':'Python experience?','answer':'One personal project','reusable':True}
        with patch.object(review_gaps.workspaces,'candidate_id',return_value='default'),patch.object(review_gaps,'load_profile_raw',side_effect=lambda:copy.deepcopy(self.profile)),patch.object(review_gaps,'save_profile_raw') as save:
            review_gaps.save_answer(payload)
            stored=save.call_args.args[0]['background']['review_answers'][0]
            self.assertEqual(stored['source'],'user_confirmed');self.assertTrue(stored['reusable'])
            with self.assertRaises(ValueError):review_gaps.save_answer({**payload,'candidate_id':'other'})
            with self.assertRaises(ValueError):review_gaps.save_answer({**payload,'question':'invented'})
        self.prepare('form')
        with patch.object(review_gaps.workspaces,'candidate_id',return_value='default'),patch.object(review_gaps,'load_profile_raw',return_value=self.profile):
            with self.assertRaises(ValueError):review_gaps.save_answer(payload)

    def test_review_receives_answers_but_only_relevant_job_scoped_answers(self):
        profile={'saved_answers':[{'match':'school','value':'Confirmed'}], 'review_answers':[
            {'job_id':1,'answer':'For this job','reusable':False},
            {'job_id':2,'answer':'Other job','reusable':False},
            {'job_id':2,'answer':'Personal fact','reusable':True}]}
        packet=build_review_packet({'id':1},profile)['candidate_constraints']
        self.assertEqual(len(packet['confirmed_review_answers']),2)
        self.assertEqual(packet['saved_application_answers'],profile['saved_answers'])
        self.assertEqual(validate_review({'verdict':'HUMAN_REVIEW','blockers':'bad'})['blockers'],[])

    def test_legacy_questions_still_visible(self):
        with db.connect() as c:c.execute('UPDATE jobs SET review_json=? WHERE id=1',(json.dumps({'manual_questions':['Which degree?']}),))
        self.assertEqual(review_gaps.snapshot()['items'][0]['questions'],[{'kind':'unknown','question':'Which degree?','reason':'','evidence':''}])
