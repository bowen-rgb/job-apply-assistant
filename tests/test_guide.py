import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from app.main import app
from app.profile_store import default_profile

STATIC = Path(__file__).resolve().parents[1] / 'static'


class GuideTests(unittest.TestCase):
    def test_worked_example_check_confirmation_recording_and_resume_are_isolated(self):
        mutations=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='fr-FR')
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if route.request.method!='GET':mutations.append(path)
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                    elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                    elif path=='/api/profile':route.fulfill(json=default_profile())
                    elif path in {'/api/jobs','/api/sources','/api/resumes','/api/pipeline'}:route.fulfill(json=[])
                    else:route.fulfill(json={})
                page.route('**/*',respond);page.goto('http://example.test/')
                page.locator('#guideNav').click()
                expect(page.locator('#workedExample')).to_contain_text('Exercice fictif')
                page.locator('#exampleReal').click()
                expect(page.locator('#resumeFile')).to_be_focused()
                expect(page.locator('#exampleCompanion')).to_be_visible()
                page.locator('#exampleCompanion button').click()
                page.locator('#exampleAdvance').click()
                expect(page.locator('#workedExample')).to_contain_text('Hôtel Exemple')
                page.locator('#exampleAdvance').click()
                expect(page.locator('#exampleAdvance')).to_be_disabled()
                page.locator('#exampleChecked').check()
                page.evaluate('refreshAutomationStatus()')
                expect(page.locator('#exampleChecked')).to_be_checked()
                page.locator('#languageSelect').select_option('en')
                expect(page.locator('#workedExample')).to_contain_text('Check the recruiter’s form')
                page.locator('#exampleAdvance').click()
                page.reload();page.locator('#guideNav').click()
                expect(page.locator('#workedExample')).to_contain_text('Send on the site and wait for confirmation')
                page.locator('#exampleAdvance').click()
                expect(page.locator('#workedExample')).to_contain_text('Return and record the application')
                page.locator('#exampleAdvance').click()
                expect(page.locator('#workedExample')).to_contain_text('Example complete')
                expect(page.locator('#workedExample progress')).to_have_attribute('value','5')
                page.evaluate('window.print=()=>{window.printedGuide=document.querySelector("#workedExample").textContent;}')
                page.locator('#guidePrint').click()
                printed=page.evaluate('window.printedGuide')
                self.assertIn('1. Add and activate the CV',printed)
                self.assertIn('5. Return and record the application',printed)
                expect(page.locator('#workedExample')).to_contain_text('Example complete')
                page.locator('#exampleReset').click()
                expect(page.locator('#workedExample progress')).to_have_attribute('value','0')
                self.assertEqual(mutations,[]);self.assertEqual(errors,[])
            finally:browser.close()

    def test_example_translations_are_complete_in_all_six_languages(self):
        data=json.loads((STATIC/'example-text.js').read_text(encoding='utf-8').removeprefix('window.ExampleTexts=').rstrip(';\n'))
        self.assertEqual(set(data),{'fr','zh','en','de','es','pt'})
        for language,strings in data.items():
            self.assertEqual(set(strings),set(data['fr']),language)
            self.assertTrue(all(value.strip() for value in strings.values()))

    def test_guide_locales_have_complete_text(self):
        data = json.loads((STATIC / 'guide-text.js').read_text(encoding='utf-8').removeprefix('window.GuideTexts=').rstrip(';\n'))
        self.assertEqual(set(data), {'fr', 'zh', 'en', 'de', 'es', 'pt'})
        for language, strings in data.items():
            self.assertEqual(set(strings), set(data['fr']), language)
            self.assertTrue(all(value.strip() for value in strings.values()))

    def test_beginner_navigation_languages_cv_and_submission_do_not_trigger_automation(self):
        health = {'resume_ok': False, 'cdp_ok': False}
        mutations = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale='fr-FR')
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                def respond(route):
                    path = urlparse(route.request.url).path
                    if route.request.method != 'GET':
                        mutations.append(path)
                    if path == '/':
                        route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html')
                    elif path.startswith('/static/'):
                        route.fulfill(path=str(STATIC / path.removeprefix('/static/')))
                    elif path == '/api/health':
                        route.fulfill(json=health)
                    elif path == '/api/profile':
                        route.fulfill(json=default_profile())
                    elif path == '/api/resumes':
                        route.fulfill(json=[dict(id='cv1', original_name='CV.pdf', label='Mon CV', active=True, size=100, tags=[])])
                    elif path in {'/api/jobs', '/api/pipeline', '/api/sources'}:
                        route.fulfill(json=[])
                    else:
                        route.fulfill(json={})
                page.route('**/*', respond)
                page.goto('http://guide.test/')
                expect(page.locator('#welcomeGuide')).to_be_visible()
                page.locator('#welcomeGuide [data-guide-target="guide"]').click()
                expect(page.locator('#guideNav')).to_have_attribute('aria-current', 'page')
                expect(page.locator('#jobsNav')).not_to_have_class('navmain active')
                expect(page.locator('#guideView')).to_contain_text('manuellement sans ChatGPT')
                expect(page.locator('#guideView')).to_contain_text('Navigateur dédié non détecté')
                page.locator('#guideView [data-guide-id="resumeFile"]').first.click()
                expect(page.locator('#resumeFile')).to_be_focused()
                expect(page.locator('#resumeList a')).to_have_attribute('href', '/api/resumes/cv1/download')
                page.locator('#first_name').fill('Draft')
                page.locator('#profileHelp summary').click()
                page.locator('#profileHelp [data-guide-id="saveProfileBtn"]').click()
                expect(page.locator('#saveProfileBtn')).to_be_focused()
                expect(page.locator('#first_name')).to_have_value('Draft')
                page.locator('#guideNav').click()
                health.update(resume_ok=True, cdp_ok=True)
                page.locator('#guideRetry').click()
                expect(page.locator('#guideView')).to_contain_text('connexion ChatGPT à vérifier')
                page.locator('#languageSelect').select_option('zh')
                expect(page.locator('#guideView')).to_contain_text('我已经投递了')
                page.locator('#guideView [data-guide-id="pipelineBoard"]').click()
                expect(page.locator('#pipelineView')).to_be_visible()
                page.locator('#jobsNav').click()
                page.locator('#guideDismiss').click()
                page.reload()
                expect(page.locator('#welcomeGuide')).to_be_hidden()
                page.locator('#guideNav').click()
                expect(page.locator('#guideView')).to_be_visible()
                self.assertEqual(mutations, [])
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_guide_survives_missing_api_and_does_not_invent_readiness(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale='fr-FR')
                def respond(route):
                    path = urlparse(route.request.url).path
                    if path == '/':
                        route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html')
                    elif path.startswith('/static/'):
                        route.fulfill(path=str(STATIC / path.removeprefix('/static/')))
                    else:
                        route.abort('failed')
                page.route('**/*', respond)
                page.goto('http://guide.test/')
                page.locator('#guideNav').click()
                expect(page.locator('#guideView')).to_contain_text('État non vérifié')
                page.locator('#guideView .guide-trouble summary').click()
                expect(page.locator('#guideView .guide-trouble')).to_contain_text('vérifiez que start.bat reste ouvert')
                page.locator('#guideRetry').click()
                expect(page.locator('#guideView .guide-trouble')).to_have_attribute('open', '')
            finally:
                browser.close()

    def test_resume_download_serves_only_registered_files_inside_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'resumes'
            root.mkdir()
            (root / 'cv.pdf').write_bytes(b'%PDF-test')
            (Path(tmp) / 'outside.pdf').write_bytes(b'private')
            rows = [{'id': 'ok', 'filename': 'cv.pdf', 'original_name': 'CV.pdf'},
                    {'id': 'bad', 'filename': '../outside.pdf', 'original_name': 'CV.pdf'}]
            with patch('app.main.list_resumes', return_value=rows), patch('app.profile_store.RESUME_DIR', root):
                client = TestClient(app)
                r = client.get('/api/resumes/ok/download')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.content, b'%PDF-test')
                self.assertIn('attachment', r.headers['content-disposition'])
                self.assertEqual(client.get('/api/resumes/bad/download').status_code, 404)
                self.assertEqual(client.get('/api/resumes/missing/download').status_code, 404)
