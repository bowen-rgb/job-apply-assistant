import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.preparation_summary import preparation_summary


class PreparationSummaryTests(unittest.TestCase):
    def test_summary_exposes_checklist_and_prepared_page_without_field_values(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.preparation_summary.ROOT', Path(folder)):
            path = Path(folder) / 'data' / 'application_audits' / 'one.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                'page_url_after_prepare': 'https://recruiter.test/form',
                'documents': {'resume_attached': True, 'letter_text_filled': True},
                'required_unanswered_count': 1,
                'required_unanswered_labels': ['Availability date'],
                'report': {'private_contact': 'candidate@example.test'},
            }), encoding='utf-8')
            result = preparation_summary({'fill_audit_path': str(path)})
            self.assertTrue(result['audit_available'])
            self.assertTrue(result['documents']['letter_attached'])
            self.assertEqual(result['required_unanswered'], 1)
            self.assertEqual(result['missing_fields'], ['Availability date'])
            self.assertEqual(result['form_url'], 'https://recruiter.test/form')
            self.assertNotIn('report', result)
            path.write_text('{broken', encoding='utf-8')
            self.assertFalse(preparation_summary({'fill_audit_path': str(path)})['audit_available'])

    def test_missing_or_outside_audit_is_unknown_instead_of_ready(self):
        result = preparation_summary({'url': 'https://recruiter.test/job', 'fill_audit_path': str(Path(__file__))})
        self.assertFalse(result['audit_available'])
        self.assertIsNone(result['required_unanswered'])
        self.assertEqual(result['form_url'], 'https://recruiter.test/job')
