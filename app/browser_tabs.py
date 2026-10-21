"""Resolve a handoff by stable Chrome target, including after login redirects."""


def find_target(context, target_id):
    for page in context.pages:
        if page.is_closed():
            continue
        session = context.new_cdp_session(page)
        try:
            if session.send('Target.getTargetInfo')['targetInfo']['targetId'] == target_id:
                return page
        finally:
            session.detach()
    return None


def application_page(context, job):
    target_id = job.get('application_tab_id')
    if target_id:
        page = find_target(context, target_id)
        if page is None:
            raise ValueError('The application tab was closed. Reopen it explicitly before continuing.')
        # Never navigate or reload a handoff: its current URL and input belong to the user.
        return page
    original = job['url'].split('?')[0].rstrip('/')
    page = next((tab for tab in reversed(context.pages) if not tab.is_closed()
                 and tab.url.split('?')[0].rstrip('/') == original), None)
    if page is None:
        page = context.new_page()
        page.goto(job['url'], wait_until='domcontentloaded', timeout=45000)
    return page
