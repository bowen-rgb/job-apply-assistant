import unittest
from unittest.mock import patch

from app.profile_store import default_profile, runtime_profile
from app.reviewer import build_prompt, build_review_packet


class SkillInventoryTests(unittest.TestCase):
    def test_learning_evidence_reaches_review_without_becoming_mastery(self):
        raw = default_profile()
        row = dict(name='PyTorch', status='learning_target', evidence='Not yet practiced')
        raw['background'].update(skill_inventory=[row], skill_notes=[dict(topic='Boundary',text='Team software is not personal mastery')], graduation_year='2030', graduation_year_status='estimated')
        with patch('app.profile_store.active_resume_path',return_value=None):
            profile = runtime_profile(raw)
        packet = build_review_packet(dict(title='Research internship'),profile)
        self.assertEqual(packet['candidate_constraints']['skill_inventory'],[row])
        self.assertEqual(packet['candidate_constraints']['academic_profile']['graduation_year_status'],'estimated')
        self.assertEqual(packet['candidate_constraints']['pfe_research_goal'].get('skills',[]),[])
        self.assertIn('Never count a planned, team-only or unconfirmed skill as mastered',build_prompt(packet))
        self.assertEqual(raw['background']['skill_inventory'][0]['status'],'learning_target')
