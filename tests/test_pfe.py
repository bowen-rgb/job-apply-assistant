import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from fastapi.testclient import TestClient
from app import db,workspaces,pfe
from app.profile_store import default_profile,runtime_profile
from app.scoring import evaluate
from app.searcher import Hit,search_web,discover
from app.scan_manager import _upsert_hit
from app.main import app

class PFETests(unittest.TestCase):
 def profile(self):
  raw=default_profile();raw['pfe'].update(enabled=True,directions=['control','robotics','mechanical'],start_month='2030-02',phd_goal=True)
  return runtime_profile(raw)
 def test_duration_is_explicit_and_profiles_do_not_inherit_short_contract_or_french_source_defaults(self):
  base={'preferred_roles':['Engineer'],'contracts':[],'locations':[]}
  a=evaluate({'title':'Engineer','body':'Contrat de 3 mois'},base)
  b=evaluate({'title':'Engineer','body':'Contrat de 6 mois'},base)
  self.assertEqual(a[:2],b[:2])
  self.assertEqual(evaluate({'title':'Engineer','body':'Contrat de 6 mois'},dict(base,availability={'duration_max_months':3}))[1],'reject')
  p=default_profile();self.assertEqual(p['automation']['enabled_sources'],[]);self.assertEqual(p['availability']['duration_max_months'],'');self.assertFalse(p['pfe']['enabled'])
 def test_pfe_classification_tasks_timing_unknown_and_phd_claims(self):
  job=dict(title='Stage M2 en robotique',location='France',body='Durée 5 à 6 mois. Début février 2030. Commande prédictive et validation expérimentale sur robot. Encadrant scientifique. Une possibilité de poursuite en thèse sera étudiée.')
  facts=pfe.facts(job,self.profile())
  self.assertEqual(facts['duration_months'],[5,6]);self.assertEqual(facts['start_month'],'2030-02');self.assertIn('control',facts['directions']);self.assertEqual(facts['phd_followup'],'explicit_opportunity');self.assertEqual(evaluate(job,self.profile())[1],'keep')
  job['body']='Recherche et validation de commande prédictive sur robot.'
  result=pfe.facts(job,self.profile());self.assertIn('start_month',result['unknown']);self.assertEqual(result['phd_followup'],'not_stated');self.assertNotEqual(evaluate(job,self.profile())[1],'reject')
  job['body']='Durée 3 mois. Début septembre 2030. Recherche en commande.'
  self.assertEqual(evaluate(job,self.profile())[1],'reject')
  job['body']='Formation niveau Bac+2. Durée 6 mois.';job['title']='Stage robotique'
  self.assertEqual(evaluate(job,self.profile())[1],'reject')
  job['body']='Stage M2 robotique. Expérience de 3 mois appréciée. Recherche en commande.'
  self.assertIsNone(pfe.facts(job,self.profile())['duration_months'])
  self.assertNotEqual(evaluate(job,self.profile())[1],'reject')
  job['location']='Berlin, Germany'
  self.assertEqual(evaluate(job,self.profile())[1],'reject')
  job['location']='Paris'
  self.assertIn('location',pfe.facts(job,self.profile())['unknown'])
 def test_plan_balances_channels_and_never_requires_start_month_or_duration_in_every_query(self):
  profile=dict(self.profile(),search_queries_per_run=5)
  rows=pfe.query_plan(profile)
  self.assertEqual({r['channel'] for r in rows},{'global','research','ats','team','student'})
  self.assertFalse(any('2030' in r['query'] or 'février' in r['query'] for r in rows))
  profile['search_queries_per_run']=100
  self.assertTrue(any('control systems' in r['query'] for r in pfe.query_plan(profile)))
 def test_pfe_web_engine_failure_and_empty_results_fall_back_without_dropping_team_urls(self):
  hit=Hit('https://research.example.org/team','Control team','Research','','pfe_team')
  with patch('app.searcher.search_bing',return_value=[]),patch('app.searcher.search_duckduckgo',return_value=[hit]):
   self.assertEqual(search_web('laboratoire commande',10,'pfe_team',['bing','duckduckgo']),[hit])
 def test_registry_recognizes_ats_reuses_entries_and_leads_never_become_application_jobs(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(db,'DB_PATH',Path(folder)/'jobs.db'):
   db.init_db();pfe.remember_source('https://jobs.lever.co/example/123');pfe.remember_source('https://jobs.lever.co/example/456')
   self.assertEqual(len(pfe.remembered_boards()),1)
   from app.pfe_discovery import process_page
   process_page(Hit('https://lab.example.org/team','Control lab','','','pfe_team'),{'title':'Control lab','text':'Research team; no advertised opening'},'',True)
   with db.connect() as c:
    self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0);self.assertEqual(c.execute('SELECT COUNT(*) FROM opportunity_leads').fetchone()[0],1)
   self.assertIsNone(pfe.board_from_url('https://jobs.lever.co.evil.example/team/123'))
   with self.assertRaises(ValueError):pfe.save_lead('team','Private','http://127.0.0.1/test')
 def test_reverification_closed_is_not_recruiter_rejection_and_blocked_is_not_closed(self):
  from app.pfe_discovery import verify
  with tempfile.TemporaryDirectory() as folder,patch.object(db,'DB_PATH',Path(folder)/'jobs.db'):
   db.init_db()
   with db.connect() as c:c.execute("INSERT INTO jobs(id,url,title,body,application_status,tracker_stage) VALUES(1,'https://lab.example.org/stage','Stage M2 robotique','Research','submitted','interview')")
   with db.connect() as c:job=dict(c.execute('SELECT * FROM jobs').fetchone())
   pfe.record_evidence(1,job,self.profile(),True,job['url'])
   with patch('app.pfe_discovery.read_public',side_effect=HTTPError(job['url'],403,'blocked',{},None)):
    self.assertEqual(verify(job,self.profile())['state'],'unverified')
   with patch('app.pfe_discovery.read_public',side_effect=HTTPError(job['url'],410,'gone',{},None)):
    self.assertEqual(verify(job,self.profile())['state'],'closed')
   with db.connect() as c:
    row=dict(c.execute('SELECT * FROM jobs').fetchone());self.assertEqual(row['tracker_stage'],'interview');self.assertEqual(row['application_status'],'submitted');self.assertEqual(row['availability_status'],'expired')
 def test_pfe_settings_and_import_are_owner_scoped_and_never_start_scans_or_workers(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'ROOT',Path(folder)):
   token=workspaces.CURRENT.set('default')
   try:db.init_db()
   finally:workspaces.CURRENT.reset(token)
   client=TestClient(app)
   with patch('app.main.start_scan') as scan,patch('app.main.queue_start') as queue:
    response=client.put('/api/pfe/settings',json={'enabled':True,'directions':['control'],'start_month':'2030-02'})
    self.assertEqual(response.status_code,200,response.text)
    response=client.post('/api/pfe/import',json={'title':'Stage M2 commande','url':'https://school.example.org/job/1','text':'Stage M2 de recherche en commande. Durée 6 mois. Début février 2030. Contactez le laboratoire pour la candidature.'})
    self.assertEqual(response.status_code,200,response.text)
    overview=client.get('/api/pfe').json();self.assertEqual(len(overview['jobs']),1);self.assertEqual(overview['jobs'][0]['verification'],'unverified')
    self.assertEqual(client.get('/api/pfe',headers={'X-Candidate-ID':'000000000001'}).status_code,409)
    self.assertEqual(client.put('/api/pfe/settings',json={'enabled':True,'directions':['wrong']}).status_code,422)
    self.assertEqual(client.put('/api/pfe/settings',json={'searxng_url':'file:///private'}).status_code,422)
    self.assertEqual(client.put('/api/profile',json={'availability':{'duration_min_months':6,'duration_max_months':3}}).status_code,400)
    scan.assert_not_called();queue.assert_not_called()
