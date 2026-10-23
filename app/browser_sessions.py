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


from contextlib import contextmanager


@contextmanager
def inspection_context(playwright, target_id=''):
    """Background reads own a hidden browser; handoffs borrow an existing tab."""
    if target_id:
        from .apply_worker import _open_browser
        from .profile_store import runtime_profile
        from .browser_control import require_connection
        require_connection()
        _, context, mode = _open_browser(playwright, runtime_profile(), {'application_tab_id': target_id})
        if mode != 'cdp':
            raise ValueError('Dedicated Chrome required for the existing login tab')
        yield context
        return
    from .browser_control import chrome_executable
    from . import secret_store
    executable = chrome_executable()
    if not executable:
        raise ValueError('Install Google Chrome to read recruitment pages in the background')
    browser = playwright.chromium.launch(executable_path=str(executable), headless=True)
    try:
        context = browser.new_context(storage_state=secret_store.read().get('browser_state') or None)
        yield context
    finally:
        browser.close()
