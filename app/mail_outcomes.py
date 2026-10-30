"""Read-only Gmail outcome discovery; only explicit confirmation changes tracking."""
import base64
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from . import secret_store
from .repositories.jobs import JobRepository
from .repositories.application_insights import ingest_message
from .db import connect


def gmail_reader():
    data = secret_store.read()
    config, connection = data.get('gmail_config', {}), data.get('gmail_connection', {})
    if not connection.get('refresh_token'):
        raise ValueError('Connect Gmail in Profiles & accounts first')
    def read(request):
        with urlopen(request, timeout=20) as response:
            payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError('Gmail response too large')
        return json.loads(payload)
    token = read(Request('https://oauth2.googleapis.com/token', data=urlencode({
        **config, 'refresh_token': connection['refresh_token'], 'grant_type': 'refresh_token'}).encode()))
    def get(path):
        return read(Request('https://gmail.googleapis.com/gmail/v1/users/me/'+path,
                            headers={'Authorization': 'Bearer '+token['access_token']}))
    return get, connection.get('email', '')


def decode_message(raw, mailbox):
    if {'SENT', 'DRAFT', 'SPAM', 'TRASH'} & set(raw.get('labelIds', [])):
        return None
    payload = raw.get('payload', {})
    headers = {x['name'].casefold(): x['value'] for x in payload.get('headers', [])}
    from email.utils import parseaddr, getaddresses
    sender = parseaddr(headers.get('from', ''))[1]
    recipient_headers = [headers[key] for key in ('to', 'delivered-to', 'cc') if headers.get(key)]
    recipients = {email.casefold() for _, email in getaddresses(recipient_headers)}
    if sender.casefold() == mailbox.casefold() or mailbox.casefold() not in recipients:
        return None
    def bodies(part, depth=0):
        if depth > 8 or part.get('filename') or part.get('body', {}).get('attachmentId'):
            return []
        encoded = part.get('body', {}).get('data', '')
        if part.get('mimeType') in {'text/plain', 'text/html'} and encoded and len(encoded) <= 200000:
            text = base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)).decode('utf-8', errors='replace')
            if part['mimeType'] == 'text/html':
                soup = BeautifulSoup(text, 'lxml')
                for tag in soup.select('script,style,blockquote,[hidden]'):
                    tag.decompose()
                text = soup.get_text('\n', strip=True)
            return [text]
        result = []
        for child in part.get('parts', [])[:30]:
            result.extend(bodies(child, depth+1))
        return result
    content = '\n'.join(bodies(payload)).strip()
    if not content:  # Subject/snippet is insufficient evidence.
        return None
    subject = headers.get('subject', '')
    return {'id': raw['id'], 'thread_id': raw.get('threadId', ''), 'sender': headers.get('from', ''),
            'subject': subject, 'text': subject+'\n'+content,
            'received_at': datetime.fromtimestamp(int(raw['internalDate'])/1000, timezone.utc).isoformat()}


def sync(days=30, reader=None):
    jobs = [j for j in JobRepository().list() if j.get('tracker_stage') or j.get('application_status')]
    if not jobs:
        return {'proposed': 0, 'read': 0, 'reason': 'no_tracked_applications'}
    get, mailbox = reader or gmail_reader()
    # Archive remains in scope; no Inbox-only restriction. Company terms are query data.
    companies = list(dict.fromkeys(j['company'] for j in jobs if j.get('company')))[:80]
    names = ['"'+name.replace('"', '').replace('\\', '').replace('\n', ' ')[:100]+'"' for name in companies]
    if not names:
        return {'proposed': 0, 'read': 0, 'reason': 'missing_company'}
    query = f'newer_than:{days}d -in:sent -in:drafts -in:spam -in:trash '+'{'+' '.join(names)+'}'
    counts = {'read': 0, 'proposed': 0, 'ignored': 0, 'duplicate': 0, 'truncated': False}
    with connect() as conn:
        cursor = conn.execute('SELECT * FROM mail_sync_cursor WHERE id=1').fetchone()
        known = {row['message_id'] for row in conn.execute('SELECT message_id FROM mail_outcomes')}
    token = cursor['page_token'] if cursor and cursor['query'] == query and cursor['mailbox'] == mailbox else ''
    for page in range(3):
        params = {'q': query, 'maxResults': 25}
        if token:
            params['pageToken'] = token
        result = get('messages?'+urlencode(params))
        for item in result.get('messages', []):
            if item['id'] in known:
                counts['duplicate'] += 1
                continue
            raw = get('messages/'+quote(item['id'], safe='')+'?format=full')
            decoded = decode_message(raw, mailbox)
            counts['read'] += 1
            outcome = ingest_message(decoded, jobs) if decoded else 'ignored'
            counts[outcome] += 1
        token = result.get('nextPageToken', '')
        with connect() as conn:
            conn.execute('INSERT OR REPLACE INTO mail_sync_cursor(id,query,mailbox,page_token) VALUES(1,?,?,?)', (query, mailbox, token))
        if not token:
            break
    counts['truncated'] = bool(token)
    return counts
