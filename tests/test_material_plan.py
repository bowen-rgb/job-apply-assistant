import unittest
from pathlib import Path
from unittest.mock import patch
from app.material_plan import material_plan


class MaterialPlanTests(unittest.TestCase):
    def test_plan_names_selected_cv_and_targeted_letter_without_claiming_uploaded(self):
        job={'id':7,'company':'Example','title':'Simulation internship','body':'Specific advertised engineering tasks and requirements.'}
        with patch('app.material_plan.select_resume_for_job',return_value=(Path(__file__),{'id':'simulation','label':'Simulation CV','selection_reason':'tags','matched_tags':['simulation']})):
            plan=material_plan(job,{'application':{'generate_cover_letter':True}})
        self.assertEqual(plan['resume_label'],'Simulation CV')
        self.assertEqual(plan['letter_mode'],'targeted')
        self.assertEqual(plan['status'],'planned')

    def test_confirmed_general_cv_pool_does_not_get_an_invented_letter(self):
        import json
        job={'application_context_json':json.dumps({'kind':'general'})}
        with patch('app.material_plan.select_resume_for_job',return_value=(None,None)):
            plan=material_plan(job,{'application':{'generate_cover_letter':True}})
        self.assertEqual(plan['letter_mode'],'cv_only')
