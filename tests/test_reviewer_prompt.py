import copy
import json
import unittest
from app.reviewer import build_prompt, _prompt_packet, build_review_packet, validate_review


class ReviewPromptTests(unittest.TestCase):
    def test_commute_origin_and_public_research_are_available_during_review(self):
        packet=build_review_packet({'id':7,'url':'https://employer.test/role'},
            {'address_line1':'12 Example Street','city':'Example City','postal_code':'75000',
             'country':'France','email':'do-not-send@example.test','max_commute_minutes':90})
        origin=packet['candidate_constraints']['commute_origin']
        self.assertEqual(origin['address_line1'],'12 Example Street')
        self.assertNotIn('email',origin)
        prompt=build_prompt(packet)
        self.assertNotIn('Do not browse',prompt)
        self.assertIn('Search the web',prompt)
        self.assertIn('commute_origin',prompt)
        self.assertIn('research_findings',prompt)

    def test_public_findings_require_a_source_and_cannot_become_candidate_facts(self):
        result=validate_review({'verdict':'APPLY','research_findings':[
            {'topic':'worksite','answer':'Official address','source_url':'https://employer.test/contact','source_quote':'Worksite: official address','status':'verified'},
            {'topic':'commute','answer':'Exact 45 minutes','source_url':'','status':'verified'}]})
        self.assertEqual(result['research_findings'][0]['status'],'verified')
        self.assertEqual(result['research_findings'][1]['status'],'unverified')

    def test_changed_review_policy_invalidates_cached_automatic_authorization(self):
        from unittest.mock import patch
        from app import human_review
        job={'review_verdict':'APPLY','title':'Example role'}
        with patch('app.profile_store.load_profile_raw',return_value={}):
            job['automatic_review_token']=human_review.automatic_token(job)
            self.assertTrue(human_review.automatic_ready(job))
            with patch.object(human_review,'AUTOMATIC_REVIEW_POLICY_VERSION','next-policy'):
                self.assertFalse(human_review.automatic_ready(job))

    def test_transport_projection_preserves_current_evidence_and_constraints(self):
        packet={'candidate_constraints':{'academic_profile':{'graduation_year':'2030'},
            'availability_preferences':{'duration_months':6,'weekends':False},
            'skill_inventory':[{'name':'FEM','status':'basics_to_confirm','evidence':'Practiced with assistance',
                'previous_assessment':{'status':'expert'},'cv_versions':{'A':'duplicate'},
                'source':{'document':'local-cv.pdf','basis':'confirmed project'}}]},
            'job':{'description':'Observed original vacancy','snippet':'Observed original vacancy'}}
        original=copy.deepcopy(packet)
        compact=_prompt_packet(packet)
        self.assertEqual(packet,original)
        skill=compact['candidate_constraints']['skill_inventory'][0]
        self.assertEqual(skill['status'],'basics_to_confirm')
        self.assertEqual(skill['evidence'],'Practiced with assistance')
        self.assertEqual(skill['source'],{'basis':'confirmed project'})
        self.assertNotIn('previous_assessment',skill)
        self.assertEqual(compact['candidate_constraints']['availability_preferences']['weekends'],False)
        self.assertEqual(compact['job']['description'],'Observed original vacancy')

    def test_ratings_are_in_output_contract_only_when_requested(self):
        prompt=build_prompt({'scoring_dimensions':[{'id':'technical','weight':1}]})
        schema=json.loads(prompt.split('Output fields: ',1)[1].split('\nJOB_PACKET:',1)[0])
        self.assertIn('ratings',schema)
        self.assertIn('manual_questions',schema)
        plain=build_prompt({})
        schema=json.loads(plain.split('Output fields: ',1)[1].split('\nJOB_PACKET:',1)[0])
        self.assertNotIn('ratings',schema)
        self.assertIn('not permission to submit',plain)
        self.assertIn('no universal four-month maximum',plain)

    def test_duplicate_skill_metadata_does_not_dominate_prompt(self):
        skills=[{'name':f'Skill {i}','status':'learning_target','evidence':'Not demonstrated',
                 'cv_versions':{'A':'duplicate '*100},'previous_assessment':{'source':'old '*100}} for i in range(40)]
        packet={'candidate_constraints':{'skill_inventory':skills},'job':{'description':'Actual vacancy'}}
        self.assertLess(len(build_prompt(packet)),len(json.dumps(packet,indent=2))/2)
