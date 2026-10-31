"""Explicit, version-bound Gmail drafts/sends. Nothing is sent by model workers."""
import base64
from datetime import datetime,timezone
from email.message import EmailMessage
from email.utils import parseaddr
import hashlib
import json
import re
from urllib.parse import urlencode,quote
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from . import secret_store,capability_store as store
from .db import connect


def configure_compose(enabled):
    if type(enabled) is not bool:raise ValueError('Choose whether Gmail compose is enabled')
    secret_store.update(lambda data:data.update(gmail_compose_enabled=enabled))


def status():
    data=secret_store.read();connection=data.get('gmail_connection',{})
    from .gmail_connection import COMPOSE_SCOPE
    return {'enabled':bool(data.get('gmail_compose_enabled')),
            'authorized':COMPOSE_SCOPE in connection.get('scopes','').split(),'email':connection.get('email','')}


def request(path,body=None,method='GET',*,mailbox=''):
    from .gmail_connection import COMPOSE_SCOPE
    data=secret_store.read();connection=data.get('gmail_connection',{});config=data.get('gmail_config',{})
    if mailbox and str(connection.get('email','')).casefold()!=mailbox.casefold():raise ValueError('Gmail account changed; verify a fresh preview')
    if not data.get('gmail_compose_enabled') or COMPOSE_SCOPE not in connection.get('scopes','').split():raise ValueError('Enable Gmail compose and reconnect to grant permission first')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('Gmail redirect refused')
    opener=build_opener(NoRedirect())
    req=Request('https://oauth2.googleapis.com/token',data=urlencode({**config,'refresh_token':connection['refresh_token'],'grant_type':'refresh_token'}).encode())
    with opener.open(req,timeout=20) as response:token=json.load(response)['access_token']
    req=Request('https://gmail.googleapis.com/gmail/v1/users/me/'+path,method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with opener.open(req,timeout=30) as response:return json.loads(response.read(2_000_000))


def preview(task_id,to,subject,body,message_id=''):
    task=store.task(task_id)
    if task['state']!='ready' or task['kind']!='followup_draft':raise ValueError('Generate a follow-up draft first')
    if any(char in to+subject for char in '\r\n') or not re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+',to):raise ValueError('Enter one valid recipient email')
    if not subject.strip() or len(subject)>400 or not body.strip() or len(body)>20000:raise ValueError('Check the subject and body')
    source=None
    if message_id:
        with connect() as c:row=c.execute('SELECT * FROM mail_outcomes WHERE message_id=? AND job_id=?',(message_id,task['job_id'])).fetchone()
        if not row:raise ValueError('Message is not linked to this application')
        source=dict(row)
        if parseaddr(source['sender'])[1].casefold()!=to.casefold():raise ValueError('Recipient does not match the original recruiter message')
    record={'task_id':task_id,'job_id':task['job_id'],'to':to,'subject':subject,'body':body,
            'message_id':message_id,'thread_id':source.get('thread_id','') if source else '',
            'from':status()['email'],'state':'preview'}
    token=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    # Re-opening an identical preview must not reset an already-sent draft.
    existing=store.item('mail-'+token,'mail_draft')
    if existing:return {'token':token,**existing}
    store.save_item('mail-'+token,'mail_draft',record)
    return {'token':token,**record}


def assert_mailbox(record):
    current=status()
    if not current['enabled'] or not current['authorized']:raise ValueError('Enable Gmail compose and reconnect before writing this draft')
    if not record.get('from') or record['from'].casefold()!=current['email'].casefold():raise ValueError('Gmail account changed; create and verify a fresh preview before continuing')


def create_draft(token,read=request):
    identifier='mail-'+token;record=store.item(identifier,'mail_draft')
    if not record:raise KeyError(token)
    assert_mailbox(record)
    if read is request:
        from functools import partial
        read=partial(request,mailbox=record['from'])
    if record['state']=='draft':return record
    if record['state']!='preview':raise ValueError('This draft is no longer editable')
    message=EmailMessage();message['To']=record['to'];message['From']=record['from'];message['Subject']=record['subject'];message.set_content(record['body'])
    if record.get('message_id'):
        original=read('messages/'+quote(record['message_id'],safe='')+'?format=metadata')
        headers={row['name'].lower():row['value'] for row in original.get('payload',{}).get('headers',[])}
        rfc=headers.get('message-id')
        if rfc:message['In-Reply-To']=rfc;message['References']=(headers.get('references','')+' '+rfc).strip()
    data={'message':{'raw':base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip('=')}}
    if record.get('thread_id'):data['message']['threadId']=record['thread_id']
    with connect() as c:
        raw=c.execute('SELECT metadata_json FROM capability_items WHERE id=?',(identifier,)).fetchone()['metadata_json']
        current=json.loads(raw)
        if current['state']!='preview':raise ValueError('Draft creation is already in progress')
        current['state']='creating'
        if not c.execute('UPDATE capability_items SET metadata_json=? WHERE id=? AND metadata_json=?',(json.dumps(current,ensure_ascii=False),identifier,raw)).rowcount:raise ValueError('Draft changed')
    try:response=read('drafts',data,'POST')
    except Exception as exc:
        record['state']='draft_unknown';store.save_item(identifier,'mail_draft',record)
        raise ValueError('Draft creation uncertain. Check Gmail drafts before creating another.') from exc
    record.update(gmail_draft_id=response['id'],state='draft')
    store.save_item(identifier,'mail_draft',{k:v for k,v in record.items() if k!='id'});return record


def send(token,acknowledged,read=request):
    if acknowledged is not True:raise ValueError('Explicitly confirm this exact draft before sending')
    identifier='mail-'+token
    with connect() as c:
        row=c.execute("SELECT metadata_json FROM capability_items WHERE id=? AND kind='mail_draft'",(identifier,)).fetchone()
        if not row:raise KeyError(token)
        record=json.loads(row['metadata_json'])
        if record['state']=='sent':return record
        assert_mailbox(record)
        if read is request:
            from functools import partial
            read=partial(request,mailbox=record['from'])
        if record['state']!='draft':raise ValueError('Draft is not ready, or a previous send needs verification')
        job=c.execute('SELECT application_status,tracker_stage FROM jobs WHERE id=?',(record['job_id'],)).fetchone()
        if not job or job['application_status'] not in {'submitted','submitted_verified'} or job['tracker_stage'] in {'rejected','withdrawn','offer','hired','offer_declined'}:
            raise ValueError('Application is no longer open for follow-up; the Gmail draft has not been sent')
        record['state']='sending'
        changed=c.execute('UPDATE capability_items SET metadata_json=? WHERE id=? AND metadata_json=?',
                          (json.dumps(record,ensure_ascii=False),identifier,row['metadata_json'])).rowcount
        if not changed:raise ValueError('Draft changed; reload it')
    try:
        response=read('drafts/send',{'id':record['gmail_draft_id']},'POST')
        if not response.get('id'):raise ValueError('No Gmail confirmation returned')
        record.update(state='sent',gmail_message_id=response['id'])
    except Exception:
        record['state']='send_unknown'
        store.save_item(identifier,'mail_draft',record)
        raise ValueError('Send outcome uncertain. Check Gmail before any retry; automatic retry is disabled.')
    store.save_item(identifier,'mail_draft',record)
    from .repositories.application_insights import add_activity
    try:add_activity(record['job_id'],'followup_sent','Gmail '+response['id']+' · '+record['to'],datetime.now(timezone.utc).date().isoformat())
    except (ValueError,KeyError):
        record['history_warning']='Gmail confirmed sending; local activity could not be recorded.'
        store.save_item(identifier,'mail_draft',record)
    return record
