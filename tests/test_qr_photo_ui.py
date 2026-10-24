from tests.ui_navigation import navigate, set_appearance
import copy,io,unittest
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from playwright.sync_api import sync_playwright,expect
from app.profile_store import default_profile
from tests.test_qr_ui import PREVIEW,STATIC


class PhotoAndBatchUITests(unittest.TestCase):
    def test_saved_photo_zoom_selection_and_batch_remove(self):
        records=[]
        for n in range(3):
            row=copy.deepcopy(PREVIEW);row['id']=format(n+1,'032x')
            row['preview'].update(company='Emploi groupe SNCF : Recrutement',company_display='SNCF',source_name='photo-'+str(n)+'.png',image_url=f'/api/qr/{row["id"]}/image')
            records.append(row)
        records[-1].update(state='authorized',job_id=8,progress={'status':'submitted_verified'})
        image=io.BytesIO();Image.new('RGB',(400,600),'lightblue').save(image,format='PNG')
        deleted=[];writes=[];errors=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1280,'height':1000})
                page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode','full')")
                page.on('pageerror',lambda error:errors.append(str(error)))
                def route(r):
                    path=urlparse(r.request.url).path
                    if path=='/':r.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):r.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if path.endswith('/image'):r.fulfill(body=image.getvalue(),content_type='image/png');return
                    if r.request.method!='GET':writes.append(path)
                    if path=='/api/qr':r.fulfill(json=records);return
                    if path.startswith('/api/qr/'):
                        identifier=path.split('/')[3]
                        row=next(x for x in records if x['id']==identifier)
                        if r.request.method=='DELETE':deleted.append(identifier);records.remove(row);r.fulfill(json={'removed':True});return
                        r.fulfill(json=row);return
                    data={}
                    if path=='/api/profile':data=default_profile()
                    elif path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Example Candidate','active':True,'identity':{}}]}
                    elif path in {'/api/jobs','/api/sources','/api/pipeline','/api/accounts','/api/resumes'}:data=[]
                    r.fulfill(json=data)
                page.route('**/*',route);page.goto('http://photo.test/');navigate(page,'qrNav')
                expect(page.locator('#qrResultTitle')).to_have_text('SNCF')
                page.locator('.qr-photo-open').click();expect(page.locator('#qrPhotoDialog')).to_be_visible()
                page.locator('#qrPhotoZoom').fill('200')
                self.assertEqual(page.locator('#qrPhotoDialog img').evaluate('e=>e.style.width'),'200%')
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#qrPhotoDialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
                page.locator('#qrPhotoClose').click();page.set_viewport_size({'width':1280,'height':1000})
                page.locator('#qrSelectAll').click();expect(page.locator('[data-qr-check]:checked')).to_have_count(2)
                folder=Path('docs/assets/angelina');folder.mkdir(exist_ok=True)
                page.screenshot(path=str(folder/'qr-batch-select.png'))
                page.locator('#qrRemoveSelected').click();expect(page.locator('[data-qr-row]')).to_have_count(1)
                self.assertEqual(len(deleted),2);self.assertFalse(any(x.endswith('/start') for x in writes));self.assertEqual(errors,[])
            finally:browser.close()
