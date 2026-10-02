import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import cover_letter, profile_store
from app.chatgpt_bridge import _matches_purpose
from app.form_engine import upload_resume, upload_cover_letter
from unittest.mock import MagicMock


class DocumentTests(unittest.TestCase):
    def test_single_library_cv_recovers_missing_active_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cv = root / 'candidate.pdf'
            cv.write_bytes(b'cv')
            with patch.object(profile_store, 'ROOT', root), patch.object(profile_store, 'RESUME_DIR', root), patch.object(profile_store, '_resume_index', return_value=[{'filename': cv.name}]):
                self.assertEqual(profile_store.active_resume_path({'application': {}}), cv)
                with patch.object(profile_store, '_resume_index', return_value=[{'filename': cv.name}, {'filename': 'other.pdf'}]):
                    (root / 'other.pdf').write_bytes(b'other')
                    self.assertIsNone(profile_store.active_resume_path({'application': {}}))

    def test_letter_generation_has_job_cv_and_invalidates_changed_job(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(cover_letter, 'LETTER_DIR', Path(folder)), patch.object(cover_letter, 'resume_text', return_value='Experience accueil hôtel'):
            job = {'id': 1, 'title': 'Réceptionniste', 'company': 'Example Hôtel', 'body': 'Accueil et réservation'}
            raw = {'identity': {'first_name': 'Ada'}, 'availability': {'text': 'Week-ends'}}
            answer = {'letter': 'Madame, Monsieur,\n' + 'Je souhaite rejoindre votre hôtel pour contribuer à un accueil attentif. ' * 5}
            with patch.object(cover_letter, 'ask_chatgpt_json', return_value=answer) as chat:
                cover_letter.generate_letter(None, job, raw, None, {})
                payload = json.loads(chat.call_args.args[1].split('\n', 1)[1])
                self.assertEqual(payload['cv'], 'Experience accueil hôtel')
                self.assertEqual(payload['job']['company'], 'Example Hôtel')
                self.assertTrue(cover_letter.letter_paths(1)[1].read_bytes().startswith(b'%PDF'))
                cover_letter.generate_letter(None, job, raw, None, {})
                self.assertEqual(chat.call_count, 1)
                job['company'] = 'Different Hôtel'
                cover_letter.generate_letter(None, job, raw, None, {})
                self.assertEqual(chat.call_count, 2)

    def test_generation_error_is_visible_and_not_ready(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(cover_letter, 'LETTER_DIR', Path(folder)):
            with self.assertRaises(ValueError):
                cover_letter.generate_letter(None, {'id': 2}, {}, None, {})
            metadata, _ = cover_letter.letter_paths(2)
            self.assertEqual(json.loads(metadata.read_text(encoding='utf-8'))['status'], 'error')

    def test_only_letter_answers_match_letter_purpose(self):
        self.assertFalse(_matches_purpose({'verdict': 'APPLY'}, 'cover-letter'))
        self.assertFalse(_matches_purpose({'letter': ''}, 'cover-letter'))
        self.assertTrue(_matches_purpose({'letter': 'Madame, Monsieur'}, 'cover-letter'))

    def test_resume_and_letter_go_to_separate_file_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            cv = Path(folder) / 'cv.pdf'
            letter = Path(folder) / 'letter.pdf'
            cv.write_bytes(b'cv')
            letter.write_bytes(b'letter')
            letter_input, resume_input = MagicMock(), MagicMock()
            letter_input.get_attribute.side_effect = lambda key: {'name': 'cover_letter', 'accept': '.pdf'}.get(key, '')
            resume_input.get_attribute.side_effect = lambda key: {'name': 'cv', 'accept': '.pdf'}.get(key, '')
            inputs = MagicMock()
            inputs.count.return_value = 2
            inputs.first = letter_input
            inputs.nth.side_effect = [letter_input, resume_input, letter_input, resume_input]
            page = MagicMock()
            page.locator.return_value = inputs
            report = {'filled': [], 'actions': [], 'errors': []}
            with patch('app.form_engine.label_for', side_effect=lambda page, field, index: 'Lettre de motivation' if field is letter_input else 'CV'):
                upload_resume(page, cv, ['input[type="file"]'], report)
                upload_cover_letter(page, letter, report)
            resume_input.set_input_files.assert_called_once_with(str(cv))
            letter_input.set_input_files.assert_called_once_with(str(letter))
            self.assertEqual(report['filled'], ['resume', 'cover_letter_file'])
