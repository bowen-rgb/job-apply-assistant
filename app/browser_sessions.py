"""Read session state without storage_state's temporary origin navigation."""
from urllib.parse import urlparse


def merge_states(previous, current):
    origins={x['origin']:x for x in previous.get('origins',[])}
    origins.update({x['origin']:x for x in current.get('origins',[])})
    # Context cookies are a full snapshot. Restoring missing old cookies would
    # resurrect sessions the user explicitly logged out of.
    return {'cookies':current.get('cookies',[]),'origins':list(origins.values())}


def save_context(context):
    from . import secret_store
    origins=[]
    for page in context.pages:
        if page.is_closed() or urlparse(page.url).scheme!='https':continue
        try:
            item=page.evaluate('''() => ({origin:location.origin,localStorage:Object.keys(localStorage).map(name=>({name,value:localStorage.getItem(name)}))})''')
            origins.append(item)
        except Exception:pass
    snapshot={'cookies':context.cookies(),'origins':origins}
    secret_store.update(lambda data:data.update(browser_state=merge_states(data.get('browser_state') or {},snapshot)))
