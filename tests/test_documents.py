import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import cover_letter, profile_store
from app.chatgpt_bridge import _matches_purpose
from app.form_engine import upload_resume, upload_cover_letter
from unittest.mock import MagicMock
from app.letter_policy import CHECKS

LETTER_BODY = '\n\n'.join([
    'Actuellement étudiante en hôtellerie, je souhaite rejoindre Example Hôtel pour le poste de réceptionniste. '
    'Les missions d’accueil et de réservation correspondent à mon expérience de l’accueil hôtelier. '
    'Je souhaite contribuer à un service attentif aux demandes des clients et approfondir la coordination avec les autres équipes de votre établissement.',
    'Lors de mon expérience en accueil hôtelier, j’ai participé à la réception des clients et au suivi de leurs demandes. '
    'Cette première pratique me donne un point de départ concret pour comprendre les procédures de réservation et les transmissions entre services. '
    'Je souhaite m’appuyer sur ces situations pour prendre progressivement en charge les tâches décrites dans votre annonce, dans le respect des procédures de l’hôtel.',
    'Cette mission m’intéresse pour son articulation entre contact avec les clients et organisation quotidienne de l’accueil. '
    'Je souhaite y consolider ma pratique des réservations et contribuer à la continuité du service. '
    'Mon expérience reste celle présentée dans mon CV et je serais heureuse de préciser lors d’un échange les responsabilités que je pourrais exercer au sein de votre équipe.'
])


def letter_review():
    return {'checks':dict.fromkeys(CHECKS,True),'issues':[],
            'evidence':[{'claim':'Pratique de l’accueil hôtelier','source':'cv','quote':'Experience accueil hôtel'}]}


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
            answer = {'letter': LETTER_BODY}
            with patch.object(cover_letter, 'ask_chatgpt_json', side_effect=lambda *args,**kwargs: letter_review() if kwargs.get('purpose')=='cover-letter-review' else answer) as chat:
                cover_letter.generate_letter(None, job, raw, None, {})
                payload = json.loads(chat.call_args_list[0].args[1].rsplit('\n', 1)[1])
                self.assertEqual(payload['cv'], 'Experience accueil hôtel')
                self.assertEqual(payload['job']['company'], 'Example Hôtel')
                self.assertTrue(cover_letter.letter_paths(1)[1].read_bytes().startswith(b'%PDF'))
                cover_letter.generate_letter(None, job, raw, None, {})
                self.assertEqual(chat.call_count, 2)
                job['company'] = 'Different Hôtel'
                cover_letter.generate_letter(None, job, raw, None, {})
                self.assertEqual(chat.call_count, 4)

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
