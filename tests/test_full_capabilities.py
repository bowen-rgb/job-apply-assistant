import base64
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import db,capability_store as store,secret_store,profile_store
from app.capabilities_routes import router


class FullCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.secrets={'gmail_connection':{'email':'candidate@example.test','scopes':'https://www.googleapis.com/auth/gmail.compose'},'gmail_compose_enabled':True}
        self.patches=[patch.dict(os.environ,{'JAA_WORKSPACE_HOME':str(self.root),'JAA_CANDIDATE_ID':'abc123abc123'}),
                      patch.object(db,'DB_PATH',self.root/'jobs.db'),patch.object(secret_store,'read',side_effect=lambda:deepcopy(self.secrets)),
                      patch.object(secret_store,'update',side_effect=lambda fn:fn(self.secrets))]
        for p in self.patches:p.start()
        db.init_db();store.init();profile_store.ensure_profile()
        profile_store.save_profile_raw({'identity':{'first_name':'Test','last_name':'Candidate','email':'candidate@example.test'}})
        with db.connect() as c:c.execute("INSERT INTO jobs(id,url,company,title,body,location,tracker_stage,application_status,last_application_at) VALUES(1,'https://employer.test/jobs/1','Example Lab','Simulation internship','Python finite element simulation','Paris','submitted','submitted','2026-08-01')")
        app=FastAPI();app.include_router(router);self.client=TestClient(app)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def task(self,kind,result,job=1):
        identifier=store.create_task(kind,job,{});store.update_task(identifier,'ready',result=result);return identifier

    def docx(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="w"><w:p w14:paraId="ABCD"><w:r><w:t>Old</w:t></w:r><w:r><w:t> content</w:t></w:r></w:p><w:p><w:r><w:t>Keep</w:t></w:r></w:p></w:document>')
            z.writestr('word/styles.xml',b'original styles');z.writestr('media/image.png',b'original image')
        return buffer.getvalue()

    def test_artifacts_and_task_records_are_candidate_scoped(self):
        identifier=self.task('research',{'sources':[]})
        self.assertEqual(store.tasks()[0]['id'],identifier)
        for invalid in ('../profile.json',str(self.root/'outside')):
            with self.assertRaises(ValueError):store.safe_file(invalid)
        with patch.dict(os.environ,{'JAA_CANDIDATE_ID':'def456def456'}),patch.object(db,'DB_PATH',self.root/'other.db'):
            db.init_db();self.assertFalse(store.tasks())
        self.assertEqual(store.task(identifier)['state'],'ready')

    def test_model_configuration_masks_keys_and_preserves_blank_key(self):
        from app import model_backends as m
        with patch('app.pfe_discovery.validate_destination'):
            m.configure('compatible',{'base_url':'https://model.test/v1','model':'example','api_key':'SECRET-KEY'})
            m.configure('compatible',{'base_url':'https://model.test/v1','model':'example2'})
        self.assertNotIn('SECRET-KEY',json.dumps(m.status()))
        self.assertEqual(self.secrets['model_backends']['compatible']['api_key'],'SECRET-KEY')
        for url in ('http://remote.test','https://a:b@model.test','https://model.test/?secret=x'):
            with self.assertRaises(ValueError):m.configure('compatible',{'base_url':url,'model':'x'})

    def test_model_http_adapters_share_json_contract(self):
        from app import model_backends as m
        self.secrets['model_backends']={key:{'base_url':'https://model.test/v1','model':'m','api_key':'key'} for key in ('compatible','anthropic','ollama')}
        responses=[{'choices':[{'message':{'content':'{"ok":true}'}}]}, {'content':[{'type':'text','text':'{"ok":true}'}]}, {'message':{'content':'{"ok":true}'}}]
        with patch.object(m,'_http_json',side_effect=responses) as read,patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('Do not open Chrome')):
            for backend in ('compatible','anthropic','ollama'):self.assertTrue(m.ask('Test',backend)['ok'])
        self.assertIn('response_format',read.call_args_list[0].args[1])
        self.assertEqual(read.call_args_list[1].args[2]['anthropic-version'],'2023-06-01')
        self.assertEqual(read.call_args_list[2].args[1]['format'],'json')

    def test_opencode_ndjson_and_cli_tool_denial(self):
        from app import model_backends as m
        from unittest.mock import Mock
        process=Mock(returncode=0);process.communicate.return_value=('\n'.join([json.dumps({'type':'step_start'}),json.dumps({'type':'text','part':{'text':'{"ok":true}'}})]),'');process.poll.return_value=0
        with patch.object(m.shutil,'which',return_value='opencode.exe'),patch.object(m.subprocess,'Popen',return_value=process):
            self.assertTrue(m._cli('opencode','untrusted text',self.root/'agent')['ok'])
        self.assertEqual(json.loads((self.root/'agent/opencode.json').read_text())['permission'],'deny')
        self.assertEqual(process.communicate.call_args.kwargs['input'],'untrusted text')

    def test_sources_require_keys_and_keep_secrets_out_of_status(self):
        from app import extended_sources as s
        with self.assertRaises(ValueError):s.search('adzuna','stage',read=lambda *a,**k:self.fail('network'))
        s.configure('adzuna',{'app_id':'id','app_key':'SECRET-KEY','enabled':True,'country':'fr'})
        self.assertNotIn('SECRET-KEY',json.dumps(s.status()))
        calls=[]
        def read(url,**kwargs):calls.append((url,kwargs));return {'results':[{'title':'Engineer internship','redirect_url':'https://jobs.test/1','company':{'display_name':'Lab'},'location':{'display_name':'Paris'},'description':'Python'}]}
        self.assertEqual(s.search('adzuna','stage','Paris',read=read)[0]['company'],'Lab')
        self.assertIn('/fr/search/1?',calls[0][0])

    def test_all_source_schemas_parse_real_contract_shapes(self):
        from app.extended_sources import search
        cases={
          'brave':{'web':{'results':[{'title':'Engineer intern','url':'https://job.test/1','description':'stage'}]}},
          'mojeek':{'response':{'results':[{'title':'Engineer intern','url':'https://job.test/1','desc':'stage'}]}},
          'jooble':{'jobs':[{'title':'Engineer intern','link':'https://job.test/1'}]},
          'careerjet':{'jobs':[{'title':'Engineer intern','url':'https://job.test/1'}]},
          'francetravail_api':{'resultats':[{'id':'1','intitule':'Engineer intern'}]},
          'jobtech':{'hits':[{'id':1,'headline':'Engineer intern'}]},
          'freehire':{'data':[{'title':'Engineer intern','url':'https://job.test/1','company':'Lab','posted_at':'2026-10-01'}]},
          'jobdanmark':{'items':[{'title':'Engineer intern','url':'/job/1','companyName':'Lab'}]},
          'jobnet':{'jobAds':[{'jobAdId':'1','title':'Engineer intern','hiringOrgName':'Lab'}]},
          'jobbank':'<rss><channel><item><title>Engineer intern</title><link>https://job.test/1</link><description>stage</description></item></channel></rss>',
          'jobindex':'<div class="PaidJob"><a href="/jobannonce/1">Engineer intern</a></div>',
          'euraxess':'<article><a href="/jobs/123">Engineer intern</a></article>',
          'linkedin_guest':'<li><a href="https://linkedin.com/jobs/1">Engineer intern</a><h4 class="base-search-card__subtitle">Lab</h4></li>'}
        for key,data in cases.items():
            calls=[]
            def read(url,**kwargs):
                calls.append((url,kwargs));return {'access_token':'token'} if 'oauth2' in url else data
            with self.subTest(source=key):
                rows=search(key,'stage','Paris',config={'api_key':'x','affid':'x','client_id':'x','client_secret':'x'},read=read)
                self.assertTrue(rows)
                if key=='jobdanmark':self.assertEqual(calls[0][1]['body']['filters'][0]['type'],'freetext')
                if key=='careerjet':self.assertIn('locale_code=fr_FR',calls[0][0])
                if key=='linkedin_guest':self.assertEqual(rows[0]['company'],'Lab')

    def test_worker_states_success_cancellation_and_secret_redaction(self):
        from app.capability_worker import run
        from app.worker_runtime import Cancelled
        identifier=store.create_task('model_check',None,{'backend':'ollama'})
        with patch('app.model_backends.ask',return_value={'ok':True}):run(identifier)
        self.assertEqual(store.task(identifier)['state'],'ready')
        identifier=store.create_task('model_check',None,{})
        with patch('app.capability_worker.check_cancelled',side_effect=Cancelled()):run(identifier)
        self.assertEqual(store.task(identifier)['state'],'cancelled')
        self.secrets['api_key']='SUPERSECRET'
        identifier=store.create_task('model_check',None,{})
        with patch('app.model_backends.ask',side_effect=ValueError('failed SUPERSECRET')):run(identifier)
        self.assertNotIn('SUPERSECRET',store.task(identifier)['error'])

    def test_task_api_validates_kind_job_and_notion_write_ack(self):
        for data in ({'kind':'nope'},{'kind':'tailor_cv'},{'kind':'research','job_id':1,'params':{'unsafe':'x'}},{'kind':'notion_sync'}):
            self.assertGreaterEqual(self.client.post('/api/capabilities/tasks',json=data).status_code,400)
        with patch('app.capabilities_routes.launch') as launch:
            result=self.client.post('/api/capabilities/tasks',json={'kind':'research','job_id':1}).json()
            launch.assert_called_once();self.assertEqual(store.task(result['id'])['state'],'queued')
        self.client.post('/api/capabilities/tasks/'+str(result['id'])+'/cancel')
        self.assertEqual(store.task(result['id'])['state'],'cancelled')

    def test_docx_replacement_preserves_other_parts_and_styles(self):
        from app.document_templates import build_docx,docx_paragraphs
        original=self.docx();result=build_docx(original,{'0':['New & proven','Second line']})
        self.assertEqual([x['text'] for x in docx_paragraphs(result)],['New & proven','Second line','Keep'])
        with zipfile.ZipFile(io.BytesIO(result)) as z:
            self.assertEqual(z.read('word/styles.xml'),b'original styles');self.assertEqual(z.read('media/image.png'),b'original image')
            self.assertEqual(z.read('word/document.xml').count(b'w14:paraId'),1)
        self.assertEqual(docx_paragraphs(original)[0]['text'],'Old content')
        with self.assertRaises(ValueError):build_docx(original,{'500':'bad'})

    def test_template_zip_traversal_and_missing_compiler_fail(self):
        from app.document_templates import register,compile_template
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('../outside.tex','x')
        with self.assertRaises(ValueError):register('evil.zip',buffer.getvalue())
        template=register('cv.tex',b'Name [NAME] Body [BODY]')
        with patch('app.document_templates.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'compiler'):compile_template(template['id'],store.safe_file('tasks/test/result.pdf'),{'NAME':'Test'})
        self.assertEqual(store.safe_file(template['path']).read_bytes(),b'Name [NAME] Body [BODY]')

    def test_pdf_generation_and_two_page_quality(self):
        from app.document_templates import render_cv,pdf_report
        path=self.root/'cv.pdf';document={'name':'Test Candidate','contact':'test@example.test','sections':[{'heading':'Projects','lines':[{'text':'Finite element simulation with Python and verified boundary conditions.'}]}]}
        result=render_cv(document,path)
        self.assertTrue(result['passed'],result);self.assertEqual(result['pages'],1)
        self.assertIn('Finite element',pdf_report(path)['text'])

    def fake_context(self):
        return {'job':{'id':1,'company':'Example Lab','title':'Simulation','url':'https://employer.test/jobs/1','body':'Python finite element simulation'},
                'candidate':{'identity':{'first_name':'Test','last_name':'Candidate'},'background':{}},
                'cv':'Performed finite element simulation with Python.','resume':{},'cv_sha256':'a'}

    def test_tailored_cv_exact_evidence_and_independent_review(self):
        from app import career_intelligence as c
        workspace=store.safe_file('tasks/77');workspace.mkdir(parents=True)
        draft={'sections':[{'heading':'Projects','lines':[{'text':'Performed finite element simulation with Python.','source':'cv','source_quote':'Performed finite element simulation with Python.'}]}]}
        checks={key:True for key in ('factual_support','qualification_status','individual_contribution','dates_and_constraints','no_keyword_stuffing')}
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'model',side_effect=[draft,{'checks':checks,'issues':[]}]):
            result=c.tailor_cv(1,'ollama',workspace);self.assertTrue(result['quality']['passed']);self.assertTrue(result['needs_approval'])
        bad=deepcopy(draft);bad['sections'][0]['lines'][0]['source_quote']='Invented prototype validation'
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'model',return_value=bad):
            with self.assertRaisesRegex(ValueError,'exact candidate'):c.tailor_cv(1,'ollama',workspace)

    def test_failed_cv_review_and_stale_adoption_never_change_materials(self):
        from app import career_intelligence as c
        workspace=store.safe_file('tasks/88');workspace.mkdir(parents=True)
        draft={'sections':[{'heading':'Project','lines':[{'text':'Proven work','source':'cv','source_quote':'Performed finite element simulation'}]}]}
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'model',side_effect=[draft,{'checks':{},'issues':['unsupported claim']}]):
            with self.assertRaisesRegex(ValueError,'review failed'):c.tailor_cv(1,'ollama',workspace)
        identifier=self.task('tailor_cv',{'quality':{'passed':True},'fingerprint':'old'})
        with patch.object(c,'context',return_value=self.fake_context()),patch('app.profile_store.add_resume') as add:
            with self.assertRaisesRegex(ValueError,'changed'):c.adopt_cv(identifier)
            add.assert_not_called()

    def test_profile_facts_require_real_quotes_and_explicit_selection(self):
        from app import career_intelligence as c
        store.save_item('doc1','document',{'name':'project','text':'Performed finite element simulation with Python.','sha256':'x'})
        proposal={'facts':[{'text':'Simulation project','document_id':'doc1','quote':'Performed finite element simulation'}]}
        with patch.object(c,'model',return_value=proposal):result=c.profile_expand(['doc1'],'ollama',self.root)
        self.assertFalse(profile_store.load_profile_raw()['background'].get('evidence_facts'))
        identifier=self.task('profile_expand',result,None);c.accept_facts(identifier,[0]);c.accept_facts(identifier,[0])
        self.assertEqual(len(profile_store.load_profile_raw()['background']['evidence_facts']),1)
        with self.assertRaises(ValueError):c.accept_facts(identifier,[2])

    def test_interview_citations_gaps_and_mock_turns_are_grounded(self):
        from app import career_intelligence as c
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'company_research',return_value={'sources':[{'url':'https://read.test'}]}),patch.object(c,'model',return_value={'sources':['https://unread.test']}):
            with self.assertRaises(ValueError):c.prepare_interview(1,'ollama',self.root)
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'model',return_value={'gaps':[{'posting_quote':'Not in the posting'}]}):
            with self.assertRaises(ValueError):c.upskill(1,'ollama',self.root)
        identifier=self.task('interview',{'turns':[]})
        with patch.object(c,'context',return_value=self.fake_context()),patch.object(c,'model',return_value={'feedback':'Use actual evidence','next_question':'How did you validate?'}):
            c.mock_turn(identifier,'My answer','ollama',self.root)
        self.assertEqual(len(store.task(identifier)['result']['turns']),1)

    def test_salary_does_not_mix_units_and_requires_three_samples(self):
        from app.salary_benchmarks import ingest,lookup
        rows=[{'salary':x,'currency':'EUR','period':'month','basis':'gross','company':'Lab'} for x in (1000,1200,1400)]
        rows.append({'salary':20000,'currency':'USD','period':'year','basis':'net','company':'Lab'})
        identifier=ingest('samples.json',json.dumps(rows).encode())['id'];result=lookup(identifier)
        self.assertEqual(len(result['groups']),2);self.assertEqual(result['groups'][0]['quantiles']['50'],1200)
        self.assertIsNone(result['groups'][1]['quantiles'])
        with self.assertRaises(ValueError):ingest('bad.json',b'[{"salary":123}]')

    def test_notion_idempotent_upsert_uses_actual_target_and_stable_id(self):
        from app import notion_sync as n
        n.configure({'target_id':'a'*32,'target_type':'data_source','token':'secret'})
        pages={};calls=[]
        def read(path,body=None,method='GET'):
            calls.append((path,body,method))
            if path=='data_sources/'+'a'*32 and method=='GET':return {'properties':{'Name':{'type':'title'}}}
            if path.endswith('/query'):
                key=body['filter']['rich_text']['equals'];return {'results':[{'id':pages[key]}] if key in pages else []}
            if path=='pages':
                key=body['properties']['JAA ID']['rich_text'][0]['text']['content'];pages[key]='p1';return {'id':'p1'}
            return {}
        self.assertEqual(n.sync(read)['created'],1);self.assertEqual(n.sync(read)['updated'],1)
        self.assertEqual(sum(path=='pages' for path,_,_ in calls),1)
        self.assertEqual(next(body for path,body,_ in calls if path=='pages')['parent']['data_source_id'],'a'*32)
        self.assertNotIn('secret',json.dumps(n.status()))

    def test_portal_proposal_must_extract_jobs_before_enable(self):
        from app import portal_registry as p
        with patch.object(p,'validate_destination'):
            row=p.register({'url':'https://jobs.test/search','label':'Test jobs','item_selector':'.job','title_selector':'.title'})
        with self.assertRaises(ValueError):p.enable(row['id'],True)
        result=p.probe(row['id'],'stage',lambda url:(b'<div class="job"><a href="/1"><b class="title">Engineer intern</b></a></div>',{},'https://jobs.test/search'))
        self.assertEqual(result['count'],1);p.enable(row['id'],True);self.assertTrue(store.item(row['id'],'portal')['enabled'])

    def test_sqlite_import_read_only_dedup_and_terminal_states(self):
        from app.tracker_exchange import parse_upload,import_rows
        path=self.root/'external.sqlite'
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE applications(company TEXT,title TEXT,stage TEXT,date TEXT)');c.execute("INSERT INTO applications VALUES('Another Lab','Engineer intern','hired','2026-08-01')")
        c.close()
        content=path.read_bytes();rows=parse_upload(path.name,content)
        self.assertEqual(path.read_bytes(),content);self.assertEqual(import_rows(rows)['added'],1)
        self.assertEqual(import_rows(rows)['duplicates'],1)
        with db.connect() as c:self.assertEqual(c.execute("SELECT tracker_stage FROM jobs WHERE company='Another Lab'").fetchone()[0],'hired')

    def test_lint_allows_honest_negation_and_flags_claims(self):
        from app.writing_lint import lint
        rules={'forbiddenClaims':['flow cytometry'],'bannedPhrases':['synergies']}
        self.assertIn('forbidden-claim',[x['rule'] for x in lint('I ran flow cytometry. Passionate about synergies.',rules)['issues']])
        self.assertFalse(lint('I have not used flow cytometry yet.',rules)['issues'])

    def test_followup_draft_and_send_are_exactly_once_and_keep_confirmation(self):
        from app import followup_mail as f
        self.secrets['gmail_connection']['email']='candidate@example.test'
        identifier=self.task('followup_draft',{'subject':'Follow-up','body':'Thank you.'})
        token=f.preview(identifier,'hr@example.test','Follow-up','Thank you.')['token'];calls=[]
        def read(path,body=None,method='GET'):
            calls.append(path);return {'id':'draft1' if path=='drafts' else 'sent1'}
        f.create_draft(token,read);f.create_draft(token,read)
        with self.assertRaises(ValueError):f.send(token,False,read)
        f.send(token,True,read);f.send(token,True,read)
        self.assertEqual(calls,['drafts','drafts/send'])
        self.assertEqual(f.preview(identifier,'hr@example.test','Follow-up','Thank you.')['state'],'sent')

    def test_uncertain_send_never_retries(self):
        from app import followup_mail as f
        identifier=self.task('followup_draft',{});token=f.preview(identifier,'hr@example.test','Follow-up','Thank you.')['token']
        f.create_draft(token,lambda *a:{'id':'d1'})
        with self.assertRaisesRegex(ValueError,'uncertain'):f.send(token,True,lambda *a:(_ for _ in ()).throw(TimeoutError()))
        with self.assertRaises(ValueError):f.send(token,True,lambda *a:self.fail('must not retry'))

    def test_reset_backs_up_binaries_database_and_preserves_accounts(self):
        from app.application_archive import reset_preview,reset
        file=store.safe_file('documents/source.txt');file.parent.mkdir();file.write_text('Candidate original evidence')
        store.save_item('doc1','document',{'name':'source.txt','path':'documents/source.txt'})
        from app.document_templates import register,template_root
        template=register('example.tex',b'[NAME] [BODY]')
        font=template_root(template)/'fonts'/'sample.dat';font.parent.mkdir();font.write_bytes(b'Bundled font evidence')
        self.secrets['account']={'password':'keep-me'}
        with patch('app.worker_runtime.any_running',return_value=False),patch('app.queue_manager.status',return_value={}),patch('app.scan_manager.status',return_value={}):
            preview=reset_preview('documents')
            with self.assertRaises(ValueError):reset('documents',preview['token'],'no')
            result=reset('documents',preview['token'],'RESET')
        self.assertFalse(file.exists());self.assertFalse(store.items('document'))
        self.assertFalse(template_root(template).exists())
        with zipfile.ZipFile(store.safe_file(result['backup'])) as z:
            self.assertEqual(z.read('documents/source.txt'),b'Candidate original evidence');self.assertIn('database.sql',z.namelist())
            self.assertEqual(z.read(Path(template['root']).as_posix()+'/fonts/sample.dat'),b'Bundled font evidence')
        self.assertEqual(self.secrets['account']['password'],'keep-me')

    def test_cli_preview_and_import_use_same_records(self):
        from app.cli import parser,execute
        result=execute(parser().parse_args(['scan','--preview']));self.assertFalse(result['network_started'])
        path=self.root/'ledger.json';path.write_text('[{"company":"CLI Lab","title":"Engineer intern"}]')
        preview=execute(parser().parse_args(['import',str(path)]));self.assertFalse(preview[0]['duplicate'])
        self.assertEqual(execute(parser().parse_args(['import',str(path),'--write']))['added'],1)

    def test_custom_template_manifest_and_plain_input_without_shell(self):
        from app.document_templates import register,compile_template
        bundle=io.BytesIO()
        with zipfile.ZipFile(bundle,'w') as z:
            z.writestr('template.json',json.dumps({'entrypoint':'src/main.md','command':['pandoc','{source}','-o','{output}'],'max_pages':2}))
            z.writestr('src/main.md','[NAME]\n\n[BODY]');z.writestr('fonts/example.dat',b'Font bytes')
        row=register('template.zip',bundle.getvalue());self.assertEqual(row['engine'],'custom')
        with patch('app.document_templates.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'pandoc'):compile_template(row['id'],store.safe_file('tasks/c/result.pdf'),{'BODY':'verified text'})
        self.assertIn('[BODY]',store.safe_file(row['path']).read_text())
        self.assertEqual(store.safe_file('tasks/c/compile/fonts/example.dat').read_bytes(),b'Font bytes')
        self.assertIn('verified text',store.safe_file('tasks/c/compile/src/main.md').read_text())

    def test_search_plan_selection_changes_real_queries_and_behavior_stays_scoped(self):
        from app.capability_actions import accept_plan
        from app.providers import build_queries
        identifier=self.task('search_plan',{'roles':['Engineer intern'],'queries':['stage simulation Paris']},None)
        accept_plan(identifier,[0,1]);profile=profile_store.runtime_profile()
        self.assertIn('Engineer intern',profile['preferred_roles']);self.assertIn(('global','stage simulation Paris'),build_queries(profile))
        response=self.client.put('/api/capabilities/behavioral',json={'energizers':'Model validation','drainers':'Frequent travel'})
        self.assertEqual(response.status_code,200);self.assertEqual(profile_store.runtime_profile()['behavioral_profile']['energizers'],'Model validation')

    def test_rank_adoption_is_atomic_and_refuses_changed_sources(self):
        from app.capability_actions import accept_rank,job_fingerprint
        import hashlib
        with db.connect() as c:job=dict(c.execute('SELECT * FROM jobs WHERE id=1').fetchone())
        profile_hash=hashlib.sha256(json.dumps(profile_store.runtime_profile(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        result={'ranked':[{'job_id':1,'fingerprint':job_fingerprint(job),'review':{'verdict':'HUMAN_REVIEW','confidence':80,'summary':'Check dates'}}],'profile_fingerprint':profile_hash}
        identifier=self.task('rank',result,None);self.assertEqual(accept_rank(identifier,[0])['updated'],1)
        with db.connect() as c:c.execute("UPDATE jobs SET body='changed description' WHERE id=1")
        with self.assertRaisesRegex(ValueError,'Posting changed'):accept_rank(identifier,[0])

    def test_archive_contains_selected_cv_and_history(self):
        from app.application_archive import archive_job
        from reportlab.pdfgen.canvas import Canvas
        file=self.root/'original.pdf';canvas=Canvas(str(file));canvas.drawString(50,750,'Test Candidate simulation evidence');canvas.save()
        profile_store.add_resume(file,'test.pdf','Simulation')
        result=archive_job(1)
        with zipfile.ZipFile(store.safe_file(result['artifact'])) as z:
            self.assertEqual(z.read('resume.pdf'),file.read_bytes());self.assertEqual(json.loads(z.read('application.json'))['job']['id'],1)

    def test_mail_draft_uncertainty_and_closed_application_are_not_retried(self):
        from app import followup_mail as f
        identifier=self.task('followup_draft',{});token=f.preview(identifier,'hr@example.test','Follow-up','Thanks.')['token']
        with self.assertRaisesRegex(ValueError,'uncertain'):f.create_draft(token,lambda *a:(_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(store.item('mail-'+token,'mail_draft')['state'],'draft_unknown')
        with self.assertRaises(ValueError):f.create_draft(token,lambda *a:self.fail('No duplicate draft'))
        token=f.preview(identifier,'other@example.test','Follow-up','Thanks.')['token'];f.create_draft(token,lambda *a:{'id':'d1'})
        with db.connect() as c:c.execute("UPDATE jobs SET tracker_stage='hired' WHERE id=1")
        with self.assertRaisesRegex(ValueError,'no longer open'):f.send(token,True,lambda *a:self.fail('Must not send'))

    def test_non_browser_letter_backend_preserves_all_lm_rules_and_audit(self):
        from app import cover_letter,model_backends
        from tests.test_letter_policy import LETTER_BODY,letter_review
        self.secrets['model_backends']={'compatible':{'model':'example','base_url':'https://model.test/v1','api_key':'secret'}}
        def response(value):return {'choices':[{'message':{'content':json.dumps(value,ensure_ascii=False)}}]}
        job={'id':1,'title':'Réceptionniste','company':'Example Hôtel','body':'Accueil et réservation des clients à la réception de l’hôtel.'}
        with patch.object(cover_letter,'resume_text',return_value='Experience accueil hôtel'),patch.object(model_backends,'_http_json',side_effect=[response({'letter':LETTER_BODY,'concerns':[]}),response(letter_review())]) as http,patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('No browser')):
            result=cover_letter.generate_letter(None,job,{'identity':{'first_name':'Ada'}},None,{'backend':'compatible'})
        self.assertTrue(result['quality']['passed'])
        for call in http.call_args_list:
            prompt=call.args[1]['messages'][0]['content'];self.assertIn('LM01',prompt);self.assertIn('LM12',prompt)

    def test_linkedin_login_reuses_human_tab_without_navigation(self):
        from app import linkedin_discovery as li
        from unittest.mock import MagicMock
        page=MagicMock();page.url='https://www.linkedin.com/checkpoint/challenge';page.is_closed.return_value=False
        context=MagicMock();context.pages=[page];browser=MagicMock();browser.contexts=[context]
        api=MagicMock();api.chromium.connect_over_cdp.return_value=browser
        manager=MagicMock();manager.__enter__.return_value=api
        with patch.object(li,'require_connection'),patch('playwright.sync_api.sync_playwright',return_value=manager):li.login()
        page.goto.assert_not_called();context.new_page.assert_not_called();browser.close.assert_not_called();page.bring_to_front.assert_called_once()

    def test_linkedin_triage_does_not_promote_unobserved_company_or_url(self):
        from app import linkedin_discovery as li
        rows=[{'kind':'posts','url':'https://linkedin.com/posts/1','links':['https://lab.test/jobs/1'],'body':'Example Lab offers Robotics internship in Paris'}]
        identifier=self.task('linkedin_scan',{'rows':rows},None)
        opportunity={'source_index':0,'company':'Example Lab','title':'Robotics internship','url':'https://lab.test/jobs/1','evidence_quote':'offers Robotics internship'}
        with patch('app.career_intelligence.model',return_value={'opportunities':[opportunity]}):result=li.triage(identifier,'ollama',self.root)
        task=self.task('linkedin_triage',result,None);self.assertEqual(li.accept(task,[0])['added'],1)
        with db.connect() as c:row=c.execute("SELECT * FROM jobs WHERE url='https://lab.test/jobs/1'").fetchone();self.assertEqual(row['application_status'],'');self.assertEqual(row['source'],'LinkedIn discovery')
        opportunity['company']='Imagined Employer'
        with patch('app.career_intelligence.model',return_value={'opportunities':[opportunity]}):
            with self.assertRaises(ValueError):li.triage(identifier,'ollama',self.root)

    def test_html_tracker_export_escapes_untrusted_cells(self):
        from app.tracker_exchange import export_rows
        result,_=export_rows([{'company':'<script>alert(1)</script>','title':'Research'}],'html')
        self.assertNotIn(b'<script>alert(1)',result);self.assertIn(b'&lt;script&gt;',result)

    def test_reviewed_cv_adoption_is_idempotent_and_changed_pdf_is_rejected(self):
        from app import career_intelligence as c
        from app.repositories.jobs import JobRepository
        from reportlab.pdfgen.canvas import Canvas
        file=self.root/'original.pdf';canvas=Canvas(str(file));canvas.drawString(40,750,'Performed finite element simulation with Python.');canvas.save()
        profile_store.add_resume(file,'test.pdf','Simulation')
        with db.connect() as conn:conn.execute("UPDATE jobs SET tracker_stage='saved',application_status='' WHERE id=1")
        draft={'sections':[{'heading':'Projects','lines':[{'text':'Performed finite element simulation with Python.','source':'cv','source_quote':'Performed finite element simulation with Python.'}]}]}
        audit={'checks':{key:True for key in ('factual_support','qualification_status','individual_contribution','dates_and_constraints','no_keyword_stuffing')},'issues':[]}
        workspace=store.safe_file('tasks/adoption');workspace.mkdir(parents=True)
        with patch.object(c,'model',side_effect=[draft,audit]):result=c.tailor_cv(1,'ollama',workspace)
        task=self.task('tailor_cv',result)
        with patch.object(JobRepository,'assert_preparable'):
            first=c.adopt_cv(task);self.assertEqual(c.adopt_cv(task),first)
        self.assertEqual(len(profile_store.list_resumes()),2)
        row=next(r for r in profile_store.list_resumes() if r['id']==first['resume_id'])
        (profile_store.resume_directory()/row['filename']).write_bytes(b'changed after adoption')
        with self.assertRaisesRegex(ValueError,'no longer'):c.adopt_cv(task)

    def test_changed_mailbox_or_revoked_compose_blocks_external_write(self):
        from app import followup_mail as f
        task=self.task('followup_draft',{});token=f.preview(task,'hr@example.test','Follow-up','Thank you.')['token']
        self.secrets['gmail_connection']['email']='other@example.test'
        with self.assertRaisesRegex(ValueError,'account changed'):f.create_draft(token,lambda *a:self.fail('Wrong mailbox'))
        self.secrets['gmail_connection']['email']='candidate@example.test'
        f.create_draft(token,lambda *a:{'id':'draft1'})
        self.secrets['gmail_compose_enabled']=False
        with self.assertRaisesRegex(ValueError,'compose'):f.send(token,True,lambda *a:self.fail('Permission was revoked'))
        self.assertEqual(store.item('mail-'+token,'mail_draft')['state'],'draft')

    def test_offer_is_not_hire_and_german_ledger_columns_are_recognized(self):
        from app.tracker_exchange import stage,normalize
        self.assertEqual(stage("Offre d’embauche"),'offer')
        self.assertEqual(stage('Embauché'),'hired')
        row=normalize([{'Firma':'Test GmbH','Stelle':'Simulation internship','Status':'beworben','Bewerbungsdatum':'2026-08-01','Ort':'Paris'}])[0]
        self.assertEqual(row['company'],'Test GmbH');self.assertEqual(row['stage'],'submitted');self.assertFalse(row['errors'])

    def test_cli_reports_failed_model_task_as_failure(self):
        from app.cli import main
        with patch('app.model_backends.ask',side_effect=ValueError('Model unavailable')),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(main(['task','model_check','--backend','ollama','--run']),1)
        self.assertEqual(json.loads(output.getvalue())['state'],'error')

    def test_chatgpt_backend_requires_platform_chrome_before_connecting(self):
        from app import model_backends as m
        with patch('app.browser_control.require_connection',side_effect=ValueError('Dedicated Chrome required')),patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('Do not open another browser')):
            with self.assertRaisesRegex(ValueError,'Chrome required'):m.ask('Test','chatgpt')

    def test_legacy_source_selection_can_disable_native_api_and_registered_portal(self):
        from app import extended_sources as s,portal_registry as p
        from app.providers import all_sources
        s.configure('adzuna',{'enabled':True,'app_id':'id','app_key':'key'})
        self.assertTrue(next(row for row in s.status() if row['id']=='adzuna')['enabled'])
        profile_store.save_profile_raw({'automation':{'enabled_sources':[]}})
        with patch.object(s,'search',side_effect=AssertionError('Disabled source must not run')):
            self.assertFalse(list(s.discover(profile_store.runtime_profile())))
        self.assertFalse(next(row for row in s.status() if row['id']=='adzuna')['enabled'])
        with patch.object(p,'validate_destination'):row=p.register({'url':'https://jobs.test/','label':'Registered Lab','item_selector':'.job'})
        identifier=row['id'];key='portal_'+identifier
        self.assertIn(key,{source.key for source in all_sources(profile_store.runtime_profile())})
        cfg=store.item(identifier,'portal');cfg['tested']=True;store.save_item(identifier,'portal',cfg);p.enable(identifier,True)
        self.assertTrue(p.entries()[0]['enabled'])
        profile_store.save_profile_raw({'automation':{'enabled_sources':[]}})
        with patch.object(p,'probe',side_effect=AssertionError('Disabled portal must not run')):
            self.assertFalse(list(p.discover(profile_store.runtime_profile())))
        self.assertFalse(p.entries()[0]['enabled'])

    def test_untested_portal_cannot_bypass_probe_via_legacy_source_checkbox(self):
        from app import portal_registry as p
        with patch.object(p,'validate_destination'):row=p.register({'url':'https://jobs.test/','label':'Lab','item_selector':'.job'})
        profile_store.save_profile_raw({'automation':{'enabled_sources':['portal_'+row['id']]}})
        with patch.object(p,'probe',side_effect=AssertionError('Must not scrape an untested source')):
            self.assertFalse(list(p.discover(profile_store.runtime_profile())))

    def test_cli_scan_uses_the_shared_controller_and_returns_its_final_counts(self):
        from app.cli import parser,execute
        final={'running':False,'found':3,'inserted':2,'updated':1}
        with patch('app.scan_manager.start') as start,patch('app.scan_manager.status',side_effect=[{'running':True},{'running':False},final]),patch('time.sleep'):
            result=execute(parser().parse_args(['scan','--source','adzuna']))
        self.assertEqual(result,final);self.assertEqual(start.call_args.args[0]['enabled_sources'],['adzuna'])

    def test_cli_ui_reuses_only_the_same_application_and_data_folder(self):
        from app.cli import parser,execute
        metadata={'application':'job-apply-assistant','workspace':str(self.root)}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(metadata).encode())),patch('webbrowser.open') as opening:
            self.assertTrue(execute(parser().parse_args(['ui']))['reused_backend']);opening.assert_called_once()
        metadata['workspace']=str(self.root/'other')
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(metadata).encode())),patch('webbrowser.open') as opening:
            with self.assertRaisesRegex(ValueError,'data folder'):execute(parser().parse_args(['ui']))
            opening.assert_not_called()


if __name__=='__main__':unittest.main()
