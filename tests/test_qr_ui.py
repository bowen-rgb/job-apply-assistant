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
         'preview':{'url':'https://employer.test/apply','final_url':'https://employer.test/apply','company':'Test Robotics','company_evidence':'JobPosting.hiringOrganization','sector':'control','sector_inferred':True,'sector_evidence':'robotique','title':'Stage robotique commande','role_title':'Stage robotique commande','tasks':['Développer la commande du quadrirotor et valider le modèle en simulation.'],'readiness':{'ready':True,'missing':[],'letter_allowed':True},'kind':'vacancy','resume_id':'robot','resume_reason':'qr_resume_job'}}

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
                    if route.request.method=='POST':writes.append((path,None if path=='/api/qr/decode' or path.endswith('/image') else route.request.post_data))
                    if path.endswith('/image'):route.fulfill(json={'saved':True});return
                    if path=='/api/qr/decode':route.fulfill(json={'codes':['https://employer.test/apply']});return
                    if path=='/api/qr/inspect':route.fulfill(json=PREVIEW);return
                    if path.endswith('/selection'):
                        data=json.loads(json.dumps(PREVIEW));data['preview'].update(json.loads(route.request.post_data));route.fulfill(json=data);return
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
                    self.assertTrue(page.locator('#qrSend').evaluate('e=>{const b=e.getBoundingClientRect();return b.top>=0&&b.bottom<=innerHeight}'))
                    page.screenshot(path=str(folder/f'preview-{width}.png'),animations='disabled')
                page.locator('#qrResume').select_option('general')
                page.locator('.qr-company-edit summary').click()
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

    def test_batch_images_paste_duplicates_remove_reload_and_mobile_layout(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1280,'height':1000});records={};writes=[];decodes=0;errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    nonlocal decodes
                    req=route.request;path=urlparse(req.url).path
                    if path=='/':
                        route.fulfill(content_type='text/html',body='''<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/qr-application.css"><style>:root{--text:#191d24;--line:#aaa;--ref-surface-1:#fff;--ref-surface-2:#eee}*{box-sizing:border-box}button{padding:12px}input,select{width:100%;padding:12px}header{display:flex}label{display:block}dialog{margin:auto}</style></head><body><button id="qrNav">QR</button><script>window.Locale={t:s=>s};window.Accounts={key:s=>'test-'+s};</script><script src="/static/qr-application.js"></script><script>QRApplication.init()</script></body></html>''');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if req.method in {'POST','DELETE'}:writes.append(path)
                    if path=='/api/qr':route.fulfill(json=list(records.values()));return
                    if path=='/api/qr/decode':
                        decodes+=1
                        if decodes==3:route.fulfill(status=400,json={'detail':'qr_no_code'})
                        else:route.fulfill(json={'codes':['https://employer.test/a','https://employer.test/b'] if decodes==1 else ['https://employer.test/b'] if decodes==2 else ['https://employer.test/'+str(decodes)]})
                        return
                    if path=='/api/qr/inspect':
                        url=json.loads(req.post_data)['url'];key=format(len(records)+decodes+10,'032x')
                        data=json.loads(json.dumps(PREVIEW));data['id']=key;data['preview'].update(url=url,final_url=url,company='Company '+url.rsplit('/',1)[-1])
                        records[key]=data;route.fulfill(json=data);return
                    key=path.rsplit('/',1)[-1]
                    if key in records:
                        if req.method=='DELETE':del records[key];route.fulfill(json={'removed':True})
                        else:route.fulfill(json=records[key])
                        return
                    route.fulfill(status=404,json={'detail':'qr_not_found'})
                page.route('**/*',respond);page.goto('http://batch.test/');page.locator('#qrNav').click()
                picture=Image.fromarray(zxingcpp.create_barcode('https://employer.test/a',zxingcpp.BarcodeFormat.QRCode).to_image(scale=4));buffer=io.BytesIO();picture.save(buffer,format='PNG')
                image={'name':'code.png','mimeType':'image/png','buffer':buffer.getvalue()}
                page.locator('#qrFile').set_input_files([image,{**image,'name':'duplicate.png'},{**image,'name':'unreadable.png'}])
                expect(page.locator('[data-qr-select]')).to_have_count(2)
                expect(page.locator('#qrTickets')).to_contain_text('unreadable.png')
                expect(page.locator('[data-qr-retry]')).to_have_count(1)
                self.assertFalse(any(path.endswith('/start') for path in writes))
                page.locator('[data-qr-remove]').first.click();expect(page.locator('[data-qr-select]')).to_have_count(1)
                page.evaluate(r"""()=>{const e=new Event('paste',{bubbles:true,cancelable:true});Object.defineProperty(e,'clipboardData',{value:{items:[],getData:()=> 'https://employer.test/c\nhttps://employer.test/d\nhttps://employer.test/d'}});document.querySelector('#qrApplicationDialog').dispatchEvent(e)}""")
                expect(page.locator('[data-qr-select]')).to_have_count(3)
                page.locator('[data-qr-select]').first.click()
                expect(page.locator('#qrCompany')).to_have_value('Company b')
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#qrApplicationDialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
                    page.screenshot(path=f'tmp/qr-ui/batch-{width}.png',animations='disabled')
                page.locator('#qrClose').click();page.locator('#qrNav').click()
                expect(page.locator('[data-qr-select]')).to_have_count(3)
                page.evaluate("""bytes=>{const files=[new File([new Uint8Array(bytes)],'paste1.png',{type:'image/png'}),new File([new Uint8Array(bytes)],'paste2.png',{type:'image/png'})];const e=new Event('paste',{bubbles:true,cancelable:true});Object.defineProperty(e,'clipboardData',{value:{items:files.map(f=>({kind:'file',type:'image/png',getAsFile:()=>f}))}});document.querySelector('#qrApplicationDialog').dispatchEvent(e)}""",list(buffer.getvalue()))
                expect(page.locator('[data-qr-select]')).to_have_count(5)
                self.assertEqual(decodes,5)
                page.locator('#qrClear').click();expect(page.locator('[data-qr-select]')).to_have_count(0)
                expect(page.locator('#qrCompany')).to_have_count(0)
                self.assertEqual(len(records),0);self.assertEqual(errors,[])
                self.assertFalse(any(path.endswith('/start') for path in writes))
            finally:browser.close()
    def test_keep_adding_during_import_retry_drag_drop_and_choose_role_in_same_card(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1280,'height':900});records={};held=[];decodes=0;sequence=0;writes=[];errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                def respond(route):
                    nonlocal decodes,sequence
                    path=urlparse(route.request.url).path;req=route.request
                    if path.startswith('/static/'):
                        route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if path=='/':
                        route.fulfill(content_type='text/html',body='''<html><meta charset="utf-8"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/workbench.css"><link rel="stylesheet" href="/static/reference-system.css"><link rel="stylesheet" href="/static/qr-application.css"><link rel="stylesheet" href="/static/angelina-ui.css"><button id="qrNav">QR</button><script>window.Locale={t:s=>s};window.Accounts={key:s=>'desk:'+s}</script><script src="/static/qr-application.js"></script><script>QRApplication.init()</script></html>''');return
                    if req.method!='GET':writes.append(path)
                    if path=='/api/qr':route.fulfill(json=list(records.values()));return
                    if path=='/api/qr/decode':
                        decodes+=1
                        if decodes==1:held.append(route);return
                        if decodes==3:route.fulfill(status=400,json={'detail':'qr_no_code'});return
                        route.fulfill(json={'codes':['https://employer.test/'+('b' if decodes==5 else str(decodes))]});return
                    if path=='/api/qr/inspect':
                        sequence+=1;data=json.loads(json.dumps(PREVIEW));data['id']=format(sequence,'032x');payload=json.loads(req.post_data);url=payload['url'];data['preview'].update(url=url,final_url=url,source_name=payload.get('source_name',''))
                        if url.endswith('portal'):data['preview'].update(kind='entry',role_title='',tasks=[],readiness={'ready':False},opportunities=[{'url':'https://employer.test/job/target','title':'Target robotics role'}])
                        records[data['id']]=data;route.fulfill(json=data);return
                    key=path.split('/')[3] if path.startswith('/api/qr/') else ''
                    if key in records:
                        if path.endswith('/target'):
                            records[key]['preview'].update(kind='vacancy',role_title='Target robotics role',final_url='https://employer.test/job/target',tasks=['Design and validate the robot control system in simulation.'],readiness={'ready':True},resume_id='robot')
                        if req.method=='DELETE':del records[key];route.fulfill(json={'removed':True});return
                        route.fulfill(json=records[key]);return
                    route.fulfill(status=404,json={'detail':'qr_not_found'})
                page.route('**/*',respond);page.goto('http://desk.test/');page.locator('#qrNav').click()
                picture=Image.fromarray(zxingcpp.create_barcode('https://employer.test/a',zxingcpp.BarcodeFormat.QRCode).to_image(scale=4));buffer=io.BytesIO();picture.save(buffer,format='PNG')
                file={'name':'first.png','mimeType':'image/png','buffer':buffer.getvalue()}
                picker=page.locator('#qrFile').element_handle()
                page.locator('#qrFile').set_input_files(file)
                expect(page.locator('#qrTickets')).to_contain_text('first.png')
                expect(page.locator('#qrAdd')).to_be_enabled()
                page.locator('#qrFile').set_input_files({**file,'name':'second.png'})
                expect(page.locator('#qrTickets')).to_contain_text('second.png')
                page.locator('#qrLinkToggle').click();page.locator('#qrLink').fill('https://employer.test/manual')
                held[0].fulfill(json={'codes':['https://employer.test/a']})
                expect(page.locator('[data-qr-select]')).to_have_count(2)
                expect(page.locator('#qrLink')).to_have_value('https://employer.test/manual')
                self.assertTrue(picker.evaluate('e=>e.isConnected'))
                page.locator('#qrLinkForm button').click();expect(page.locator('[data-qr-select]')).to_have_count(3)
                page.locator('#qrFile').set_input_files({**file,'name':'bad.png'})
                expect(page.locator('[data-qr-retry]')).to_have_count(1)
                page.locator('[data-qr-retry]').click();expect(page.locator('[data-qr-select]')).to_have_count(4)
                page.evaluate("""()=>{const dt=new DataTransfer();dt.items.add(new File(['test'],'drag.png',{type:'image/png'}));document.querySelector('#qrApplicationDialog').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));}""")
                expect(page.locator('[data-qr-select]')).to_have_count(5)
                page.locator('#qrLinkToggle').click();page.locator('#qrLink').fill('https://employer.test/portal');page.locator('#qrLinkForm button').click()
                expect(page.locator('[data-qr-select]')).to_have_count(6)
                page.locator('[data-qr-select]').last.click();expect(page.locator('#qrSend')).to_be_disabled()
                page.locator('#qrRole').select_option('https://employer.test/job/target')
                expect(page.locator('.qr-job')).to_have_text('Target robotics role')
                expect(page.locator('[data-qr-select]')).to_have_count(6)
                expect(page.locator('#qrSend')).to_be_enabled()
                self.assertEqual(len(records),6)
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':900})
                    self.assertTrue(page.locator('#qrApplicationDialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
                    self.assertTrue(page.locator('#qrAdd').evaluate('e=>{const b=e.getBoundingClientRect();return b.top>=0&&b.bottom<innerHeight}'))
                    page.screenshot(path=f'tmp/qr-ui/desk-{width}.png',animations='disabled')
                self.assertFalse(any(path.endswith('/start') or path=='/api/queue/start' for path in writes));self.assertEqual(errors,[])
            finally:browser.close()
