import json
import io
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from PIL import Image
import zxingcpp

STATIC=Path(__file__).resolve().parents[1]/'static'
PREVIEW={'id':'a'*32,'state':'draft','job_id':None,'resumes':[{'id':'robot','label':'D · Robotique'},{'id':'general','label':'Forum · Général'}],
         'preview':{'url':'https://employer.test/apply','final_url':'https://employer.test/apply','company':'Test Robotics','company_evidence':'JobPosting.hiringOrganization','sector':'control','sector_inferred':True,'sector_evidence':'robotique','title':'Stage robotique commande','kind':'vacancy','resume_id':'robot','resume_reason':'qr_resume_job'}}

class QRUITests(unittest.TestCase):
    def test_upload_preview_override_single_dispatch_and_handoff(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN',viewport={'width':1280,'height':1000})
                page.add_init_script("localStorage.setItem('jaa-ui-mode','full')")
                writes=[];errors=[];started=False;resumed=False;resume_polls=0
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    nonlocal started,resumed,resume_polls
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if route.request.method=='POST':writes.append((path,None if path=='/api/qr/decode' else route.request.post_data))
                    if path=='/api/qr/decode':route.fulfill(json={'codes':['https://employer.test/apply']});return
                    if path=='/api/qr/inspect':route.fulfill(json=PREVIEW);return
                    if path.endswith('/start') and path.startswith('/api/qr/'):started=True
                    if path.endswith('/resume') and path.startswith('/api/qr/'):resumed=True
                    if path.startswith('/api/qr/'+PREVIEW['id']):
                        state=json.loads(json.dumps(PREVIEW));state.update(state='authorized',job_id=8)
                        if resumed and route.request.method=='GET':resume_polls+=1
                        completed=resumed and resume_polls>=2
                        state['progress']={'status':'submitted_verified' if completed else 'needs_human','step':'completed' if completed else 'login','worker_running':resumed and not completed,'detail':{'note':'Test-only fixture'},'verification':'verified' if completed else ''}
                        route.fulfill(json=state);return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Test Candidate','identity':{},'active':True}]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path in {'/api/jobs','/api/sources','/api/pipeline','/api/accounts','/api/resumes'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://qr-ui.test/')
                page.locator('#qrNav').click()
                expect(page.locator('#qrApplicationDialog')).to_be_visible()
                expect(page.locator('#qrApplicationDialog')).to_contain_text('上传图片不会发送申请')
                self.assertEqual(writes,[])
                folder=Path('tmp/qr-ui');folder.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(folder/'empty-desktop.png'),animations='disabled')
                picture=Image.fromarray(zxingcpp.create_barcode('https://employer.test/apply',zxingcpp.BarcodeFormat.QRCode).to_image(scale=4))
                buffer=io.BytesIO();picture.save(buffer,format='PNG')
                page.locator('#qrFile').set_input_files({'name':'qr.png','mimeType':'image/png','buffer':buffer.getvalue()})
                expect(page.locator('#qrCompany')).to_have_value('Test Robotics')
                expect(page.locator('#qrResume')).to_have_value('robot')
                expect(page.locator('#qrApplicationDialog')).to_contain_text('根据页面关键词推测')
                self.assertFalse(any(path.endswith('/start') for path,_ in writes))
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#qrApplicationDialog').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                    page.screenshot(path=str(folder/f'preview-{width}.png'),animations='disabled')
                page.locator('#qrResume').select_option('general')
                page.locator('#qrCompany').fill('Test Robotics Confirmed')
                page.locator('#qrSend').click()
                expect(page.locator('.qr-progress')).to_contain_text('请在 Chrome 登录')
                sends=[json.loads(body) for path,body in writes if path.endswith('/start')]
                self.assertEqual(sends,[{'resume_id':'general','company':'Test Robotics Confirmed'}])
                expect(page.locator('#qrSend')).to_have_count(0)
                page.locator('#qrResumeRun').click()
                expect(page.locator('.qr-progress')).to_contain_text('网站已确认提交')
                self.assertFalse(any(path=='/api/queue/start' for path,_ in writes))
                self.assertEqual(errors,[])
            finally:browser.close()
