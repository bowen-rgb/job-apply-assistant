"""Exercise the real local frontend using isolated example data, never live jobs."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC = Path(__file__).resolve().parents[1] / 'static'


class PFEUITests(unittest.TestCase):
    def test_settings_evidence_leads_and_scan_are_separate_actions(self):
        writes = []
        state = dict(settings=dict(enabled=False, directions=['control'], locations=['France'], start_month='2027-02', duration_months=6),
                     plan=[dict(channel='research', direction='control', query='stage M2 commande France')],
                     readiness={}, jobspy_available=False,
                     jobs=[dict(id=1, title='EXAMPLE · Stage M2 commande', company='Example lab', location='France', url='https://lab.example.org/stage', verification='unverified', checked_at='2026-10-19',
                                facts=dict(score=70, kind='pfe', axes=dict(eligibility=20,time=10,technical=20,research=20,phd=0), evidence=dict(research='Validation expérimentale'), unknown=['start_month'], phd_followup='not_stated'))],
                     leads=[dict(id='team1', kind='team', title='EXAMPLE · Research team', url='https://lab.example.org/team', contact='', evidence='Research topic; no advertised opening', status='unconfirmed')],
                     sources=[dict(domain='lab.example.org', ats='', board='', last_seen_at='2026-10-19', status='observed')])
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale='zh-CN'); errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script("localStorage.setItem('jaa-ui-mode','full')")
                def respond(route):
                    path = urlparse(route.request.url).path
                    method = route.request.method
                    if path == '/': route.fulfill(path=str(STATIC/'index.html'), content_type='text/html'); return
                    if path.startswith('/static/'): route.fulfill(path=str(STATIC/path.removeprefix('/static/'))); return
                    if method not in {'GET','HEAD'}:
                        payload = json.loads(route.request.post_data or '{}'); writes.append((path,payload))
                        if path == '/api/pfe/settings': state['settings'] = payload
                        if path.startswith('/api/pfe/leads/'): state['leads'][0]['status'] = payload['status']
                    data = {}
                    if path == '/api/candidates': data = dict(active_id='default',items=[dict(id='default', name='EXAMPLE',identity={}, active=True)])
                    elif path == '/api/profile': data = {'automation':{}}
                    elif path in {'/api/jobs','/api/sources','/api/pipeline','/api/accounts','/api/resumes'}: data = []
                    elif path == '/api/pfe': data = state
                    route.fulfill(json=data)
                page.route('**/*',respond); page.goto('http://pfe-ui.test/')
                page.locator('#pfeNav').click()
                expect(page.locator('#pfeView')).to_be_visible()
                expect(page.locator('#pfeScan')).to_be_disabled()
                page.locator('#pfeEnabled').check()
                page.locator('#pfeSave').click()
                expect(page.locator('#pfeNotice')).to_contain_text('已保存')
                self.assertEqual([path for path,_ in writes],['/api/pfe/settings'])
                self.assertEqual(writes[0][1]['duration_months'],6)
                expect(page.locator('#pfeList')).to_contain_text('没有明确提到后续博士机会')
                page.locator('#pfeList summary').click()
                expect(page.locator('#pfeList')).to_contain_text('Validation expérimentale')
                for width in [320,768,1440]:
                    page.set_viewport_size(dict(width=width,height=950))
                    self.assertTrue(page.locator('#pfeView').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                page.locator('[data-pfe-tab="team"]').click()
                expect(page.locator('#pfeList')).to_contain_text('尚未确认有实习名额')
                expect(page.locator('#pfeList button')).to_have_count(0)
                page.locator('[data-pfe-lead]').select_option('contact_planned')
                expect(page.locator('[data-pfe-lead]')).to_be_enabled()
                self.assertEqual(writes[-1],('/api/pfe/leads/team1',dict(status='contact_planned')))
                page.locator('[data-pfe-tab="sources"]').click()
                expect(page.locator('#pfeList')).to_contain_text('lab.example.org')
                page.locator('#pfeSettings summary').click()
                page.locator('#pfeSkills').fill('MATLAB, Python')
                for language,title in [('de','PFE & Forschung'),('es','Prácticas e investigación'),('pt','Estágio e investigação'),('fr','PFE & recherche'),('en','PFE & research'),('zh','毕业实习与科研机会')]:
                    page.locator('#languageSelect').select_option(language)
                    expect(page.locator('#pfeNav')).to_have_text(title)
                    expect(page.locator('#pfeSkills')).to_have_value('MATLAB, Python')
                page.locator('#pfeScan').click()
                expect(page.locator('#pfeNotice')).to_contain_text('扫描进行中')
                self.assertEqual(writes[-1][0],'/api/search')
                self.assertFalse(any('queue' in path or 'submit' in path for path,_ in writes))
                self.assertEqual(errors,[])
            finally:
                browser.close()
