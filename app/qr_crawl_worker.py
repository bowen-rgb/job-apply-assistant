"""Collect a QR employer's listings without creating jobs or dispatching forms."""
import json,sys
from . import qr_application as qr
from .qr_crawler import crawl
from .qr_fetching import read_public
from .qr_browser_reader import read_rendered
from .qr_semantics import enrich

def run(identifier):
    row=qr.get_request(identifier)
    if row['state']!='crawling':raise ValueError('qr_already_started')
    payload=json.loads(row['payload'])
    def persist(value):
        with qr.connect() as c:c.execute("UPDATE qr_requests SET payload=? WHERE id=? AND state='crawling'",(json.dumps(value,ensure_ascii=False),identifier))
    try:
        from .portal_feeds import detect, collect
        root = payload.get('portal_url') or payload.get('final_url') or payload.get('url', '')
        provider = detect(root)
        if provider and provider not in {'greenhouse', 'lever', 'ashby', 'smartrecruiters'}:
            try:
                feed = collect(provider, root, payload.get('company', ''))
                existing = {item['url']: item for item in payload.get('opportunities', [])}
                existing.update({item['url']: item for item in feed['rows']})
                payload['opportunities'] = list(existing.values())
                payload['ats_feed'] = {'provider': provider, 'count': len(feed['rows']), 'capped': feed['capped']}
            except Exception as exc:
                payload['ats_feed'] = {'provider': provider, 'error': str(exc)[:300]}
            persist(payload)
        payload=crawl(payload,read_public,lambda url:read_rendered(url,search_filters=False),enrich,persist)
    except Exception as exc:
        payload.setdefault('crawl',{}).update(status='error',error=str(exc)[:500])
    finally:
        if payload.get('ats_feed', {}).get('capped'):
            payload.setdefault('crawl', {})['capped'] = True
        with qr.connect() as c:c.execute("UPDATE qr_requests SET state='draft',payload=? WHERE id=? AND state='crawling'",(json.dumps(payload,ensure_ascii=False),identifier))

if __name__=='__main__':run(sys.argv[1])
