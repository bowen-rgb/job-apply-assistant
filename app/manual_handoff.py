"""Focus an existing application tab without navigation, filling or submission."""
from playwright.sync_api import sync_playwright

from .db import connect
from .preparation_summary import preparation_summary
from .profile_store import runtime_profile
from .worker_runtime import is_running


MISSING_TAB = 'Onglet préparé introuvable. Retrouvez-le dans le navigateur dédié ou ouvrez le lien du poste ; les champs non envoyés ne sont pas récupérables.'


def focus_existing(context, job):
    target = job.get('application_tab_id')
    urls = {job.get('url'), preparation_summary(job).get('form_url')}
    matches = []
    for page in context.pages:
        if page.is_closed():
            continue
        if target:
            session = context.new_cdp_session(page)
            try:
                matched = session.send('Target.getTargetInfo')['targetInfo']['targetId'] == target
            finally:
                session.detach()
            if matched:
                page.bring_to_front()
                return
        elif page.url in urls:
            matches.append(page)
    if len(matches) == 1:
        # Legacy runs require an exact URL. Never reload or open another tab.
        # https://playwright.dev/python/docs/api/class-page#page-bring-to-front
        matches[0].bring_to_front()
        return
    raise ValueError(MISSING_TAB)


def take_over(job_id):
    with connect() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        queue = c.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    if is_running('app.apply_worker', job_id) or row['application_status'] in {'opening', 'preparing', 'preparing_letter'} or (queue and queue['status'] == 'running'):
        raise ValueError('Arrêtez la préparation et attendez sa fin avant de reprendre cet onglet.')
    cfg = runtime_profile()
    if cfg.get('browser_mode', 'cdp') != 'cdp':
        raise ValueError('La reprise nécessite le navigateur dédié lancé par start.bat.')
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cfg.get('chrome_cdp_endpoint') or 'http://127.0.0.1:9222', timeout=8000)
            if not browser.contexts:
                raise ValueError(MISSING_TAB)
            focus_existing(browser.contexts[0], dict(row))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Navigateur dédié inaccessible. Ouvrez start.bat et réessayez.') from exc
    return {'ok': True, 'message': 'Onglet activé. Vérifiez les documents et réponses, puis envoyez sur le site et confirmez ici.'}
