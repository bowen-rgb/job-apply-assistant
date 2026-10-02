import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app import job_translation
from app.contracts import TitleTranslationRequest


class JobTranslationTests(unittest.TestCase):
    def test_recruitment_terms_preserve_brand_and_original(self):
        original = "Hôte(sse) d'accueil - THE ROYAL PUB"
        self.assertEqual(job_translation.local_title(original, 'zh'), '接待员 - THE ROYAL PUB')
        self.assertEqual(job_translation.local_title('Chef de service — H/F', 'zh'), '部门主管')
        self.assertEqual(job_translation.local_title('Agent polyvalent en crèche (F/H)', 'zh'), '托育中心综合工作人员')
        self.assertEqual(job_translation.local_title(original, 'fr'), original)
        for language in job_translation.LANGUAGES:
            self.assertNotEqual(job_translation.local_title(original, language), original)

    def test_glossary_needs_no_network(self):
        with patch.object(job_translation.urllib.request, 'urlopen') as network:
            result = job_translation.translate_title('Extra / CDD Assistant Hall de nuit (H/F)', 'zh')
        network.assert_not_called()
        self.assertIn('夜班酒店大堂助理', result['title'])
        self.assertIn('固定期限合同', result['title'])

    def test_remote_translation_is_cached_by_source_and_language(self):
        answer = {'responseStatus': 200, 'responseData': {'translatedText': '特殊职位'}}
        with tempfile.TemporaryDirectory() as folder, patch.object(job_translation, 'CACHE_DIR', Path(folder)), patch.object(job_translation.urllib.request, 'urlopen', side_effect=lambda *args, **kwargs: io.StringIO(json.dumps(answer))) as network:
            first = job_translation.translate_title('Un poste particulier', 'zh')
            self.assertEqual(first['title'], '特殊职位')
            self.assertEqual(job_translation.translate_title('Un poste particulier', 'zh'), first)
            self.assertEqual(network.call_count, 1)
            job_translation.translate_title('Un poste différent', 'zh')
            job_translation.translate_title('Un poste particulier', 'en')
            self.assertEqual(network.call_count, 3)
            query = network.call_args.args[0].full_url
            self.assertNotIn('candidate', query)

    def test_provider_failure_retains_original_without_poisoning_cache(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(job_translation, 'CACHE_DIR', Path(folder)), patch.object(job_translation.urllib.request, 'urlopen', side_effect=OSError('offline')):
            result = job_translation.translate_title('Un poste particulier', 'zh')
            self.assertEqual(result, {'title': 'Un poste particulier', 'status': 'unavailable'})
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_api_translates_only_stored_titles_and_limits_batches(self):
        with TestClient(app) as client, patch('app.main.job_repository.titles', return_value=[{'id': 42, 'title': 'Chef de service — H/F'}]):
            response = client.post('/api/jobs/translate-titles', json={'job_ids': [42], 'language': 'zh'})
            self.assertEqual(response.status_code, 200)
            translated = response.json()['translations']['42']
            self.assertEqual(translated['title'], '部门主管')
            self.assertEqual(translated['original'], 'Chef de service — H/F')
            self.assertEqual(client.post('/api/jobs/translate-titles', json={'job_ids': [42], 'language': 'invalid'}).status_code, 422)
            self.assertEqual(client.post('/api/jobs/translate-titles', json={'job_ids': list(range(13)), 'language': 'zh'}).status_code, 422)

    def test_all_known_titles_are_searchable_without_remote_requests(self):
        source = [{'id': 42, 'title': 'Chef de service — H/F'}]
        with TestClient(app) as client, patch('app.main.job_repository.list', return_value=source), patch.object(job_translation.urllib.request, 'urlopen') as network:
            result = client.get('/api/jobs?language=zh').json()[0]
            self.assertEqual(result['title'], 'Chef de service — H/F')
            self.assertEqual(result['display_title'], '部门主管')
            network.assert_not_called()
