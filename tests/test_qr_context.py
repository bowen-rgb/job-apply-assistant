import json
import unittest
from unittest.mock import patch
from app.qr_context import page_context,readiness,discover_roles
from app.qr_semantics import apply_analysis
from app.resume_matcher import rank_resumes
from app.application_target import letter_target

class QRContextTests(unittest.TestCase):
    def test_inmind_tenant_is_employer_and_event_is_not_a_vacancy(self):
        html='''<title>InMind</title><img alt="Logo Inmind"><h1>Arts &amp; Métiers</h1>
        <script>inmind.cvInmind = true; inmind.companyName = "saint-gobain";
        inmind.consent = {"company_cgu":"Saint-Gobain : https://www.saint-gobain.com/fr/privacy"};</script>'''
        ctx=page_context(html,'https://cv.inmind.fr/saint-gobain/27257')
        self.assertEqual(ctx['company'],'Saint-Gobain');self.assertEqual(ctx['kind'],'general')
        self.assertEqual(ctx['company_website'],'https://www.saint-gobain.com/')
        self.assertEqual(ctx['company_evidence'],'inmind.companyName');self.assertEqual(ctx['tasks'],[])
        self.assertFalse(readiness(ctx)['letter_allowed'])
        self.assertNotEqual(page_context(html,'https://unrelated.test/')['company'],'Saint-Gobain')

    def test_general_pool_business_advice_requires_cv_quote_and_official_source(self):
        payload={'kind':'general','company':'Example','company_website':'https://example.test/','tasks':[]}
        summary='Example develops mechanical systems and numerical simulation for industrial products.'
        cv='I developed mechanical numerical simulation and validated finite element models.'
        result={'business_summary':summary,'business_source_url':'https://example.test/about',
                'resume_ranking':[{'resume_id':'a','cv_quote':cv,'task_quote':summary,'confidence':'medium','reason':'Company simulation activities match the documented project.'}]}
        analysis=apply_analysis(dict(payload),result,{'a':{'text':cv,'label':'Simulation'}})
        self.assertEqual(analysis['semantic_ranking'][0]['source'],'company_business_advisory')
        self.assertFalse(analysis['company_business_verified']);self.assertEqual(analysis['tasks'],[])
        bad={**result,'business_source_url':'https://unrelated.test/'}
        self.assertNotIn('semantic_ranking',apply_analysis(dict(payload),bad,{'a':{'text':cv,'label':'Simulation'}}))

    def test_company_names_are_not_career_titles_or_ats_domains(self):
        from app.qr_context import company_name
        self.assertEqual(company_name('Emploi groupe SNCF : Recrutement'),'SNCF')
        self.assertEqual(company_name('Michelin | Careers'),'Michelin')
        for name in ['career5.successfactors.eu','cv.inmind.fr','Recruitment','Workday']:
            self.assertEqual(company_name(name),'')
        ctx=page_context('<title>Emploi groupe SNCF : Recrutement</title>','https://employer.test/')
        self.assertEqual(ctx['company'],'SNCF');self.assertIn('Recrutement',ctx['company_quote'])

    def test_employer_fallbacks_and_provider_rejection(self):
        cases=[('<title>Careers opportunities in CMA CGM Group</title>','CMA CGM Group','page_title'),
               ('<footer>© 2026 Example Aerospace | All rights reserved</footer>','Example Aerospace','footer'),
               ('<header><img alt="Example Robotics logo"></header>','Example Robotics','logo_alt'),
               ('<meta property="og:site_name" content="Workday">','','')]
        for html,company,source in cases:
            ctx=page_context('<html>'+html+'</html>','https://employer.test/')
            self.assertEqual(ctx['company'],company);self.assertEqual(ctx['company_evidence'],source)
            self.assertEqual(ctx['kind'],'entry')

    def test_actual_nonstandard_role_has_duties_but_upload_alone_does_not(self):
        html='<html><title>Careers at Example Robotics</title><h1>Stage ingénieur robotique</h1><h2>Vos missions</h2><p>Développer la commande et valider le modèle du robot par des essais en simulation.</p></html>'
        ctx=page_context(html,'https://employer.test/job/robot')
        self.assertEqual(ctx['kind'],'vacancy');self.assertTrue(readiness(ctx)['ready'])
        generic=page_context('<html><title>Careers at Example Robotics</title><input type=file></html>','https://employer.test/')
        self.assertEqual(generic['kind'],'entry');self.assertFalse(readiness(generic)['ready'])
        pool=page_context('<html><title>Careers at Example Robotics</title><h1>Candidature spontanée</h1><input type=file></html>','https://employer.test/apply')
        self.assertEqual(pool['kind'],'general');self.assertFalse(readiness(pool)['letter_allowed'])

    def test_discovery_uses_actual_links_bounded_search_and_prioritizes_stage(self):
        context=page_context('<html><a href="/search/">Find jobs</a></html>','https://employer.test/')
        search=b'<html><a href="/job/sales">Sales specialist</a><a href="/job/robot">Stage robotique commande</a><a href="/privacy">Privacy</a></html>'
        calls=[]
        def read(url):calls.append(url);return search,'text/html',url
        roles=discover_roles(context,read)
        self.assertEqual(len(calls),1);self.assertEqual(len(roles),2)
        self.assertEqual(roles[0]['title'],'Stage robotique commande')

    def test_selected_cv_uses_actual_project_content_not_filename_or_active_order(self):
        rows=[{'id':'a','label':'Version A','tags':['robotique']},{'id':'b','label':'Version B','tags':[]},{'id':'c','label':'Version C','tags':[]},{'id':'d','label':'Version D','tags':[]}]
        texts={'a':'Simulation thermique numérique par éléments finis et validation des contraintes',
               'b':'Conception mécanique CAO et dimensionnement de structures sous CATIA',
               'c':'Jumeau numérique Unity synchronisation capteurs et visualisation temps réel',
               'd':'Développé la commande PID du quadrirotor et validé le modèle robotique par simulation'}
        cases=[('Stage conception mécanique',['Conception CAO et dimensionnement de structures CATIA'],'b'),
               ('Stage jumeau numérique',['Jumeau numérique Unity et visualisation des capteurs temps réel'],'c'),
               ('Stage commande robotique',['Développer la commande du quadrirotor et valider le modèle par simulation'],'d')]
        for title,tasks,expected in cases:
            ranked=rank_resumes({'role_title':title,'tasks':tasks},rows,lambda r:texts[r['id']])
            self.assertEqual(ranked[0]['resume_id'],expected);self.assertTrue(ranked[0]['evidence'])
        self.assertEqual(rank_resumes({'role_title':'','tasks':[]},rows,lambda r:texts[r['id']]),[])
        unknown=rank_resumes({'role_title':'Comptabilité fiscale','tasks':['Auditer les bilans financiers']},rows,lambda r:texts[r['id']])
        self.assertEqual(unknown[0]['score'],0)

    def test_semantic_ranking_requires_quotes_in_both_page_and_selected_cv(self):
        tasks='Développer la commande du quadrirotor en simulation.'
        payload={'kind':'vacancy','role_title':'Stage robotique','title':'Stage robotique','tasks':[tasks],'body':tasks,'company':'Example Robotics'}
        cv='Développé la commande PID du quadrirotor sous Python.'
        cvs={'d':{'text':cv,'label':'Version D'}}
        result={'company':'Invented Company','company_quote':'Invented Company robotics','resume_ranking':[
            {'resume_id':'missing','cv_quote':cv,'task_quote':tasks},
            {'resume_id':'d','cv_quote':'Expert professionnel ROS en entreprise','task_quote':tasks},
            {'resume_id':'d','cv_quote':cv,'task_quote':'Invented tasks unrelated to webpage'},
            {'resume_id':'d','cv_quote':cv,'task_quote':tasks,'reason':'PID réalisé, missions de commande','confidence':'medium'}]}
        final=apply_analysis(payload,result,cvs)
        self.assertEqual(final['company'],'Example Robotics')
        self.assertEqual(len(final['semantic_ranking']),1)
        self.assertEqual(final['semantic_ranking'][0]['source'],'grounded_semantic')


    def test_production_chrome_reader_collects_delayed_dom_and_shadow_links_without_applying(self):
        from playwright.sync_api import sync_playwright
        from app import qr_browser_reader as reader
        from unittest.mock import MagicMock
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context()
            context.route('https://employer.test/**',lambda route:route.fulfill(content_type='text/html',body='''<html><meta charset="utf-8"><title>Careers at Example Robotics</title><body><div id="root"></div><script>
                setTimeout(()=>{document.querySelector('#root').innerHTML='<h1>Stage ingénieur robotique</h1><section class="missions">Développer la commande du quadrirotor et valider les modèles en simulation.</section><button onclick="document.title=String(1/0)">Apply now</button>';let host=document.createElement('div');document.body.append(host);host.attachShadow({mode:'open'}).innerHTML='<a href="https://employer.test/job/second">Stage ingénieur mécanique</a>';},60);
            </script></body></html>'''))
            try:
                with patch.object(reader,'require_connection'),patch.object(reader,'validate_destination'),patch.object(reader,'runtime_profile',return_value={}),patch.object(reader,'sync_playwright',return_value=MagicMock()),patch('app.apply_worker._open_browser',return_value=(browser,context,'cdp')):
                    raw,_,url=reader.read_rendered('https://employer.test/job/robot')
                result=page_context(raw,url)
                self.assertEqual(result['company'],'Example Robotics')
                self.assertEqual(result['kind'],'vacancy')
                self.assertTrue(any(role['url'].endswith('/second') for role in result['opportunities']))
                self.assertNotIn(b'<title>Infinity</title>',raw)
                self.assertTrue(browser.is_connected())
            finally:browser.close()

    def test_legacy_qr_and_provider_brand_block_letter_target(self):
        for job in [{'provider_key':'qr','company':'Example','title':'Careers','body':'x'*60},
                    {'company':'Workday','title':'Stage Robotique','body':'x'*60},
                    {'company':'Example','title':'Careers','body':'x'*60}]:
            with self.assertRaises(ValueError):letter_target(job)

if __name__=='__main__':unittest.main()
