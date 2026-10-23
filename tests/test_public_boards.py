import unittest
import json
import builtins
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from app import public_boards as boards, pfe


class PublicBoardTests(unittest.TestCase):
    def test_capability_check_does_not_import_scraper_native_dependencies(self):
        from app.jobspy_provider import supported_sites
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name.startswith('jobspy'):raise AssertionError('Do not import scraper in web server')
            return original(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'model.py').write_text('class Site(Enum):\n    HELLOWORK = "hellowork"\n    INDEED = "indeed"\n')
            with patch('importlib.util.find_spec',return_value=SimpleNamespace(submodule_search_locations=[folder])),patch('builtins.__import__',side_effect=guarded):
                self.assertEqual(supported_sites(),{'hellowork','indeed'})
    def test_aggregator_employer_and_dates_are_from_offer_not_site_branding(self):
        offer={'titre':'Stage robotique','description':'Stage de fin d’études de 6 mois','employeur':{'nom':'Example Robotics'},'localisation':{'ville':'Paris','pays':'France'},'dateDeDebutMin':'2030-02-01','dateDeDebutMax':'2030-02-01','urlDeCandidature':'https://example.test/jobs/123','source':'jobteaser'}
        html='<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'offreDeStage':offer}}})+'</script>'
        doc=boards.extract_document('1jeune1solution',html,'https://www.1jeune1solution.gouv.fr/stages/123')
        self.assertEqual(doc.company,'Example Robotics');self.assertIn('Paris',doc.location)
        self.assertEqual(doc.start_date,'2030-02-01')
        self.assertIn('https://example.test/jobs/123',doc.structured_json)
        self.assertIn('2030-02-01',doc.structured_json)
        offer['urlDeCandidature']='https://www.jobteaser.com/fr/job-offers/abc-job'
        html='<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'offreDeStage':offer}}})+'</script>'
        self.assertEqual(boards.extract_document('1jeune1solution',html,'https://www.1jeune1solution.gouv.fr/stages/123').canonical_url,offer['urlDeCandidature'])
    def test_known_region_outside_requested_region_is_not_recommended(self):
        profile={'pfe':{'enabled':True,'directions':['robotics'],'locations':['Paris','Île-de-France']}}
        self.assertTrue(pfe.facts({'title':'Stage robotique','location':'Lyon, Auvergne-Rhône-Alpes, France'},profile)['location_conflict'])
        self.assertFalse(pfe.facts({'title':'Stage robotique','location':'Saclay 91190, France'},profile)['location_conflict'])
    def test_jobteaser_uses_verified_public_query_and_pagination_parameters(self):
        query=parse_qs(urlparse(boards.listing_url('jobteaser','robotique','Paris',2)).query)
        self.assertEqual(query['q'],['robotique'])
        self.assertEqual(query['contract'],['internship'])
        self.assertEqual(query['page'],['2'])
    def test_detail_urls_reject_lists_foreign_hosts_and_login(self):
        cases = {'jobteaser':'https://www.jobteaser.com/fr/job-offers/abc-role',
                 '1jeune1solution':'https://www.1jeune1solution.gouv.fr/stages/robotique-123',
                 'apec':'https://www.apec.fr/candidat/recherche-stage.html/offre/123',
                 'wttj':'https://www.welcometothejungle.com/fr/companies/test/jobs/stage_paris',
                 'france_travail':'https://candidat.francetravail.fr/offres/recherche/detail/123ABC'}
        for source,url in cases.items():
            with self.subTest(source=source):
                self.assertTrue(boards.detail_url(source,url))
                self.assertFalse(boards.detail_url(source,url.replace(urlparse(url).hostname,'evil.test')))
                self.assertFalse(boards.detail_url(source,urljoin_root(url)))

    def test_extracts_only_detail_links_and_deduplicates_tracking(self):
        html='''<a href="/fr/job-offers">All jobs</a><a href="/fr/job-offers/abc-role?utm_source=a"><h3>Stage robotique</h3></a>
        <a href="/fr/job-offers/abc-role?utm_source=b">Duplicate</a><a href="https://evil.test/fr/job-offers/123">Other</a>'''
        rows=boards.extract_links('jobteaser',html,'https://www.jobteaser.com/fr/job-offers')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'Stage robotique')

    def test_failed_source_does_not_block_another_or_general_employment(self):
        profile={'pfe':{'enabled':True,'directions':['robotics']},'enabled_sources':['jobteaser','apec'],'public_board_pages':2}
        events=[]
        def read(url, profile):
            if 'jobteaser' in url:raise ValueError('Login required')
            return '<a href="/candidat/recherche-stage.html/offre/123">Stage robotique</a>','static',url
        with patch.object(boards,'read_page',side_effect=read):
            rows=list(boards.discover(profile,lambda *args,**kw:events.append((args,kw))))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].provider_key,'apec')
            self.assertTrue(any(event[0]==('jobteaser','public-listing','failed') for event in events))
            self.assertEqual(list(boards.discover({'preferred_roles':['Receptionist'],'contracts':['CDI']})),[])

    def test_selected_sources_have_queries_inside_budget(self):
        profile={'pfe':{'enabled':True,'directions':['robotics']},'enabled_sources':['jobteaser','1jeune1solution','apec','hellowork','wttj','france_travail'],'search_queries_per_run':36}
        channels={row['channel'] for row in pfe.query_plan(profile)}
        self.assertTrue(set(profile['enabled_sources']).issubset(channels))

    def test_verification_is_not_reported_as_zero_jobs(self):
        self.assertTrue(boards.verification_gate('<main>apec.fr 正在验证设备...</main>'))
        self.assertFalse(boards.verification_gate('<main>Stage robotique</main><script>captcha</script>'))

    def test_pfe_web_hits_use_destination_adapter(self):
        self.assertEqual(boards.source_for_url('https://www.1jeune1solution.gouv.fr/stages/robotique-123','pfe_1jeune1solution'),'1jeune1solution')
        self.assertEqual(boards.source_for_url('https://example.org/research','pfe_research'),'pfe_research')


def urljoin_root(url):
    return 'https://'+urlparse(url).hostname+'/'
