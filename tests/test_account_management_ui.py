import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC=Path(__file__).resolve().parents[1]/'static'


class AccountManagementUITests(unittest.TestCase):
    def test_independent_website_cards_edit_toggle_and_resume_actions(self):
        accounts=[dict(origin='https://indeed.test',login_url='https://indeed.test/login',site_name='Indeed',username='alice@example.test',enabled=True,has_password=True),
                  dict(origin='https://hellowork.test',login_url='https://hellowork.test/login',site_name='HelloWork',username='hello@example.test',enabled=True,has_password=True)]
        writes=[];fail_save=False
        resumes=[dict(id='first',label='CV hôtel',original_name='hotel.pdf',tags=['accueil'],active=False,size=1024),
                 dict(id='second',label='CV accueil',original_name='accueil.pdf',tags=[],active=True,size=1024)]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.add_init_script("localStorage.setItem('jaa-ui-mode','full')")
                def respond(route):
                    nonlocal fail_save
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if path=='/api/accounts':
                        if route.request.method=='PUT':
                            payload=json.loads(route.request.post_data);writes.append(payload)
                            if fail_save:route.fulfill(status=503,json={'detail':'Offline'});return
                            account=next(a for a in accounts if a['login_url']==payload['login_url'])
                            account.update({key:payload[key] for key in ('site_name','username','enabled')})
                            route.fulfill(json={'ok':True});return
                        route.fulfill(json=accounts);return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[dict(id='default',name='Alice',identity={},active=True)]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path=='/api/resumes':data=resumes
                    elif path=='/api/gmail':data={'configured':False,'connected':False}
                    elif path in {'/api/jobs','/api/sources','/api/pipeline'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://account-ui.test/')
                page.locator('#accountsNav').click()
                cards=page.locator('#savedAccounts [role=listitem]')
                expect(cards).to_have_count(2)
                expect(cards.first).to_contain_text('Indeed')
                expect(cards.nth(1)).to_contain_text('HelloWork')
                expect(page.locator('#accountEditor')).not_to_have_attribute('open','')
                for width in [320,768,1024,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    self.assertTrue(page.locator('#accountsDialog').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                cards.first.get_by_role('button',name='编辑',exact=True).focus()
                page.keyboard.press('Enter')
                expect(page.locator('#accountUser')).to_have_value('alice@example.test')
                expect(page.locator('#accountURL')).to_have_attribute('readonly','')
                expect(page.locator('#accountPassword')).to_have_value('')
                expect(page.locator('#accountPassword')).not_to_have_attribute('required','')
                page.locator('#accountUser').fill('changed@example.test')
                expect(page.locator('#accountPassword')).to_have_attribute('required','')
                page.locator('#accountUser').fill('alice@example.test')
                expect(page.locator('#accountPassword')).not_to_have_attribute('required','')
                page.locator('#accountSiteName').fill('Indeed France')
                fail_save=True
                page.locator('#accountSave button.primary').click()
                expect(page.locator('#accountsNotice')).to_contain_text('Offline')
                expect(page.locator('#accountSiteName')).to_have_value('Indeed France')
                fail_save=False
                page.locator('#accountSave button.primary').click()
                expect(cards.first).to_contain_text('Indeed France')
                expect(cards.nth(1)).to_contain_text('hello@example.test')
                self.assertEqual(writes[-1]['password'],'')
                self.assertEqual(writes[-1]['login_url'],'https://indeed.test/login')
                cards.first.get_by_role('checkbox').uncheck()
                expect(cards.first).to_contain_text('自动登录已关闭')
                expect(cards.nth(1).get_by_role('checkbox')).to_be_checked()
                page.locator('#accountAdd').click()
                expect(page.locator('#accountURL')).to_have_value('')
                expect(page.locator('#accountURL')).not_to_have_attribute('readonly','')
                expect(page.locator('#accountPassword')).to_have_attribute('required','')
                page.locator('#accountsClose').click()
                page.locator('#profileNav').click()
                expect(page.locator('#resumeList')).to_contain_text('使用这份简历')
                expect(page.locator('#resumeList')).to_contain_text('当前使用')
                expect(page.locator('#resumeList')).to_contain_text('保存名称和标签')
                expect(page.locator('#resume-tags-first')).to_have_attribute('placeholder','标签，例如：接待、物流…')
                self.assertEqual(errors,[])
            finally:browser.close()
