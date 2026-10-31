import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.profile_store import select_resume_for_job


class ResumeRoutingTests(unittest.TestCase):
    def test_title_direction_outweighs_generic_body_tags_and_reason_is_visible(self):
        rows=[{'id':'mechanical','label':'Mechanical','filename':'b.pdf','tags':['mecanique','conception']},
              {'id':'simulation','label':'Simulation','filename':'a.pdf','tags':['simulation']}]
        with tempfile.TemporaryDirectory() as folder:
            for row in rows:(Path(folder)/row['filename']).touch()
            with patch('app.profile_store.list_resumes',return_value=rows),patch('app.profile_store.resume_directory',return_value=Path(folder)):
                _,selected=select_resume_for_job({'title':'Stage simulation','body':'Groupe de conception mecanique.'},{'application':{'auto_resume_routing':True,'active_resume_id':'mechanical'}})
                self.assertEqual(selected['id'],'simulation')
                self.assertEqual(selected['selection_reason'],'tags')
                self.assertEqual(selected['matched_tags'],['simulation'])
