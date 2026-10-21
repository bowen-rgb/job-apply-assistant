import json, unittest
from unittest.mock import patch
from app.qr_crawler import crawl,links_from,canonical,api_for
from app.qr_semantics import apply_analysis
from app.worker_runtime import Cancelled

ROOT='https://employer.test/careers'
def listing(rows,next_url=''):
    return '<title>Careers at Example Robotics</title>'+''.join('<a href="'+u+'">'+t+'</a>' for u,t in rows)+('<a rel="next" href="'+next_url+'">Next</a>' if next_url else '')
def detail(title='Stage robotique',location='Paris',start='2027-02-01'):
    return '<script type="application/ld+json">'+json.dumps({'@type':'JobPosting','title':title,'hiringOrganization':{'name':'Example Robotics'},'jobLocation':{'address':{'addressLocality':location}},'jobStartDate':start,'description':'Develop robot control software and validate the models in simulation.'})+'</script>'
class CrawlTests(unittest.TestCase):
    def packet(self):return dict(url=ROOT,final_url=ROOT,kind='entry',company='',opportunities=[])
    def reader(self,pages,calls):
        def read(url):
            calls.append(url)
            if url not in pages:raise OSError('missing fixture')
            return pages[url].encode(),'text/html',url
        return read
    def test_pagination_dedupe_evidence_and_resume(self):
        calls=[];pages={ROOT:listing([('/job/a','Stage robotique'),('/job/a?utm_source=x','Stage robotique')],'/careers?page=2'),
                       'https://employer.test/careers?page=2':listing([('/job/b','Stage conception mecanique')]),
                       'https://employer.test/job/a':detail(),'https://employer.test/job/b':detail('Stage conception mecanique')}
        payload=crawl(self.packet(),self.reader(pages,calls),page_budget=1)
        self.assertEqual(payload['crawl']['status'],'partial');self.assertEqual(len(payload['opportunities']),1)
        payload=crawl(payload,self.reader(pages,calls),page_budget=10)
        self.assertEqual(payload['crawl']['status'],'complete');self.assertEqual(len(payload['opportunities']),2)
        self.assertEqual(calls.count(ROOT),1);self.assertTrue(all(x['verified'] for x in payload['opportunities']))
        self.assertTrue(any('control' in x['directions'] for x in payload['opportunities']))
        self.assertNotEqual(canonical(ROOT+'?ref=a'),canonical(ROOT+'?ref=b'))
    def test_failed_http_falls_back_to_chrome_then_grounded_ai(self):
        rendered=[];semantic=[]
        def public(url):raise OSError('403 Forbidden')
        def browser(url):rendered.append(url);return b'<title>Example</title><p>Welcome to Example Robotics careers.</p>','text/html',url
        def ai(packet):semantic.append(packet);return {**packet,'ai_explanation':'Recruitment portal; no confirmed vacancy.'}
        result=crawl(self.packet(),public,browser,ai)
        self.assertEqual(rendered,[ROOT]);self.assertEqual(len(semantic),1)
        self.assertTrue(result['ai_explanation']);self.assertEqual(result['opportunities'],[])
    def test_read_errors_are_partial_and_retryable(self):
        result=crawl(self.packet(),lambda url:(_ for _ in ()).throw(OSError('403')))
        self.assertEqual(result['crawl']['status'],'partial');self.assertEqual(len(result['crawl']['errors']),1)
        calls=[];result=crawl(result,self.reader({ROOT:listing([])},calls))
        self.assertEqual(result['crawl']['status'],'empty');self.assertEqual(calls,[ROOT])
    def test_failed_links_survive_continuation_until_retried(self):
        a='https://employer.test/job/a';b='https://employer.test/job/b'
        pages={ROOT:listing([(a,'Stage robotique A'),(b,'Stage robotique B')]),b:detail()}
        result=crawl(self.packet(),self.reader(pages,[]),page_budget=2)
        self.assertTrue(result['crawl']['errors']);self.assertTrue(result['crawl']['remaining'])
        result=crawl(result,self.reader(pages,[]),page_budget=1)
        self.assertEqual(result['crawl']['status'],'partial');self.assertTrue(result['crawl']['errors'])
        pages[a]=detail()
        result=crawl(result,self.reader(pages,[]))
        self.assertEqual(result['crawl']['errors'],[]);self.assertEqual(result['crawl']['status'],'complete')
    def test_cross_site_private_and_apply_links_not_followed(self):
        calls=[];html=listing([('http://127.0.0.1/job/x','Stage private'),('https://other.test/job/x','Stage unrelated'),('/job/x/apply','Apply engineer'),('/job/a','Stage robotique')])
        result=crawl(self.packet(),self.reader({ROOT:html,'https://employer.test/job/a':detail()},calls))
        self.assertEqual(len(result['opportunities']),1);self.assertEqual(len(calls),2)
    def test_cancel_keeps_pending_work(self):
        with patch('app.qr_crawler.check_cancelled',side_effect=Cancelled('stop')):
            result=crawl(self.packet(),lambda url:None)
        self.assertEqual(result['crawl']['status'],'paused');self.assertEqual(result['crawl']['remaining'],1)
    def test_ats_api_and_smartrecruiters_pagination(self):
        root='https://careers.smartrecruiters.com/Example';api=api_for(root)[1]
        next_api=api.replace('offset=0','offset=100');calls=[]
        record=lambda n:{'id':str(n),'name':'Stage robotique '+str(n),'company':{'identifier':'Example','name':'Example'},'location':{'city':'Paris'}}
        pages={root:listing([]),api:json.dumps({'totalFound':101,'content':[record(1)]}),next_api:json.dumps({'totalFound':101,'content':[record(2)]})}
        result=crawl(dict(url=root,final_url=root,kind='entry',company='Example',opportunities=[]),self.reader(pages,calls),page_budget=3)
        self.assertIn(next_api,calls);self.assertEqual(len(result['opportunities']),2)
        self.assertTrue(all(x['location']=='Paris' for x in result['opportunities']))
        self.assertEqual(result['crawl']['status'],'partial')
    def test_pagination_does_not_consume_link_depth(self):
        pages={ROOT:listing([], '/careers?page=1')};calls=[]
        for i in range(1,9):pages['https://employer.test/careers?page='+str(i)]=listing([],('/careers?page='+str(i+1)) if i<8 else '')
        result=crawl(self.packet(),self.reader(pages,calls))
        self.assertEqual(len(calls),9);self.assertEqual(result['crawl']['status'],'empty')

    def test_multiple_jsonld_jobs_are_a_portal_not_single_application(self):
        from app.qr_context import page_context
        html=detail()+detail('Stage mecanique')
        self.assertEqual(page_context(html,ROOT)['kind'],'entry')

    def test_semantic_links_must_be_observed(self):
        payload=dict(final_url=ROOT,kind='entry',title='Careers',body='Welcome to Example Robotics careers.',company='',observed_links=[{'url':ROOT+'/search','title':'Search jobs'}])
        result=apply_analysis(payload,dict(explanation='Recruitment website',opportunities=[{'url':'https://evil.test/job'},{'url':ROOT+'/search'}]),{})
        self.assertEqual(result['opportunities'],[{'url':ROOT+'/search','title':'Search jobs'}]);self.assertFalse(result['ai_explanation_verified'])
        result=apply_analysis(payload,{'opportunities':[{'url':'https://employer.test/job/new','title':'Stage robotique'}]},{} )
        suggestion=next(r for r in result['opportunities'] if r.get('source')=='chatgpt_suggestion')
        self.assertFalse(suggestion['verified'])

if __name__=='__main__':unittest.main()
