import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright
from app.profile_store import default_profile

STATIC=Path(__file__).resolve().parents[1]/'static'


class CoachTests(unittest.TestCase):
    def run_browser(self, callback, health, jobs, responses=None):
        writes=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='fr-FR');errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if route.request.method!='GET':writes.append((path,route.request.post_data))
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                    elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                    elif responses and responses(route,path):return
                    elif path=='/api/health':route.fulfill(json=health)
                    elif path=='/api/jobs':route.fulfill(json=jobs)
                    elif path=='/api/profile':route.fulfill(json=default_profile())
                    elif path in {'/api/sources','/api/resumes','/api/pipeline'}:route.fulfill(json=[])
                    else:route.fulfill(json={})
                page.route('**/*',respond);page.goto('http://coach.test/')
                callback(page,writes)
                self.assertEqual(errors,[])
            finally:browser.close()

    def test_default_real_journey_resume_confirmation_failure_and_retry(self):
        job=dict(id=7,title='Reception Paris',company='Hotel',location='Paris',url='https://recruiter.test/7',score=95,decision='keep')
        health=dict(resume_ok=True,cdp_ok=False);attempts=[]
        def responses(route,path):
            if path=='/api/jobs/7/application-status':
                attempts.append(json.loads(route.request.post_data))
                if len(attempts)==1:route.fulfill(status=503,json={'detail':'Unavailable'})
                else:job.update(application_status='submitted');route.fulfill(json={'ok':True})
                return True
            return False
        def check(page,writes):
            expect(page.locator('#guideView')).to_be_visible()
            expect(page.locator('body')).to_have_class('simple-mode')
            expect(page.locator('#coachPick')).to_be_visible()
            expect(page.locator('#coachPractice')).not_to_have_attribute('open','')
            page.locator('#coachPick').click()
            expect(page.locator('#coachOpen')).to_have_attribute('href',job['url'])
            expect(page.locator('#coachReturn')).to_be_disabled()
            page.locator('#beginnerGuide details').first.locator('summary').click()
            page.locator('#coachAlready').click()
            expect(page.locator('#coachRecord')).to_be_disabled()
            page.locator('#coachConfirmed').check()
            page.locator('#coachRecord').click()
            expect(page.locator('#coachStatus')).to_contain_text('Cela n’a pas été enregistré')
            expect(page.locator('#coachRecord')).to_be_enabled()
            page.reload()
            expect(page.locator('#coachRecord')).to_be_disabled()
            page.locator('#coachConfirmed').check();page.locator('#coachRecord').click()
            expect(page.locator('#beginnerGuide')).to_contain_text('Vous avez terminé')
            page.reload();expect(page.locator('#coachNext')).to_be_visible()
            self.assertEqual(attempts,[{'status':'submitted'},{'status':'submitted'}])
            self.assertFalse(any('/apply' in path or path=='/api/queue' for path,_ in writes))
        self.run_browser(check,health,[job],responses)

    def test_upload_preserves_selected_file_on_poll_language_change_and_failure(self):
        health=dict(resume_ok=False,cdp_ok=False);uploads=[]
        def responses(route,path):
            if path=='/api/resumes/upload':
                uploads.append(path)
                if len(uploads)==1:route.fulfill(status=503,json={'detail':'Retry'})
                else:route.fulfill(json={'resume':{'id':'cv'}})
                return True
            if path=='/api/resumes/cv/activate':health['resume_ok']=True;route.fulfill(json={'ok':True});return True
            return False
        def check(page,writes):
            expect(page.locator('#coachFile')).to_be_visible()
            page.locator('#coachFile').set_input_files({'name':'my.pdf','mimeType':'application/pdf','buffer':b'%PDF'})
            page.evaluate('refreshAutomationStatus()')
            page.locator('#languageSelect').select_option('en')
            self.assertEqual(page.locator('#coachFile').evaluate('e=>e.files[0].name'),'my.pdf')
            page.locator('#coachUpload').click()
            expect(page.locator('#coachStatus')).to_contain_text('This was not saved')
            self.assertEqual(page.locator('#coachFile').evaluate('e=>e.files[0].name'),'my.pdf')
            page.locator('#coachUpload').click()
            expect(page.locator('#coachSearch')).to_be_visible()
            page.locator('#coachRole').fill('Receptionist');page.locator('#coachPlace').fill('Paris')
            page.locator('#simpleModeToggle').click()
            expect(page.locator('body')).not_to_have_class('simple-mode')
            page.locator('#simpleModeToggle').click()
            expect(page.locator('#coachRole')).to_have_value('Receptionist')
            expect(page.locator('#coachPlace')).to_have_value('Paris')
            self.assertEqual(len(uploads),2)
        self.run_browser(check,health,[],responses)

    def test_missing_and_closed_jobs_are_not_offered_and_mode_remains_reversible(self):
        jobs=[dict(id=1,title='Done',url='https://recruiter.test/1',application_status='submitted'),dict(id=2,title='Skip',url='https://recruiter.test/2',user_action='skipped'),dict(id=3,title='Unsafe',url='javascript:alert(1)'),dict(id=4,title='Expired',url='https://recruiter.test/4',decision='expired')]
        def check(page,writes):
            expect(page.locator('#coachSearch')).to_be_visible()
            page.locator('#coachSearch').click()
            expect(page.locator('#coachStatus')).to_contain_text('Indiquez le poste et la ville')
            self.assertEqual(writes,[])
            page.locator('#simpleModeToggle').click();page.locator('#jobsNav').click()
            expect(page.locator('#batchBtn')).to_be_visible()
            page.reload();expect(page.locator('body')).not_to_have_class('simple-mode')
        self.run_browser(check,dict(resume_ok=True),jobs)

    def test_all_coach_languages_have_the_same_nonempty_keys(self):
        d=json.loads((STATIC/'coach-text.js').read_text(encoding='utf-8').removeprefix('window.CoachTexts=').rstrip(';\n'))
        self.assertEqual(set(d),{'fr','zh','en','de','es','pt'})
        for values in d.values():
            self.assertEqual(set(values),set(d['fr']))
            self.assertTrue(all(value.strip() for value in values.values()))

    def test_search_saves_only_search_targets_and_waits_for_the_real_scan(self):
        scan={'running':False};jobs=[]
        def responses(route,path):
            if path=='/api/search':scan['running']=True;route.fulfill(json=scan);return True
            if path=='/api/search/status':route.fulfill(json=scan);return True
            return False
        def check(page,writes):
            expect(page.locator('#coachSearch')).to_be_visible()
            page.locator('#coachRole').fill('Reception');page.locator('#coachPlace').fill('Paris')
            page.locator('#coachSearch').click()
            expect(page.locator('#coachSearch')).to_be_disabled()
            expect(page.locator('#coachStatus')).to_contain_text('Patientez')
            profile=json.loads(next(body for path,body in writes if path=='/api/profile'))
            self.assertEqual(profile,{'preferences':{'roles':['Reception'],'locations':['Paris']}})
            scan['running']=False
            jobs.append(dict(id=2,title='Real result',url='https://recruiter.test/2',decision='keep'))
            page.evaluate('pollScan()')
            expect(page.locator('#coachPick')).to_be_visible()
            expect(page.locator('#beginnerGuide')).to_contain_text('Real result')
        self.run_browser(check,dict(resume_ok=True),jobs,responses)
