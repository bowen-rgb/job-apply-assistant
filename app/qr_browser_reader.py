"""Read career pages through dedicated Chrome; job-search filters only, never apply."""
import re
from html import escape
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from .browser_control import require_connection
from .profile_store import runtime_profile
from .pfe_discovery import validate_destination
from .worker_runtime import check_cancelled


def read_rendered(url, *, search_filters=True):
    require_connection()
    validate_destination(url)
    from .apply_worker import _open_browser
    with sync_playwright() as p:
        _,context,mode=_open_browser(p,runtime_profile())
        if mode!='cdp':
            context.close()
            raise ValueError('Chrome CDP required for page inspection')
        checked=set()
        def guard(route):
            target=route.request.url
            if target.startswith(('data:','blob:')):route.fallback();return
            host=urlparse(target).hostname
            try:
                if host not in checked:validate_destination(target);checked.add(host)
                route.fallback()
            except Exception:route.abort()
        context.route('**/*',guard)
        try:
            page=context.new_page()
            page.goto(url,wait_until='domcontentloaded',timeout=35000)
            # Let a SPA expose its first content, without clicking or accepting popups.
            try:page.wait_for_load_state('networkidle',timeout=6000)
            except Exception:pass
            if search_filters and '/search' in urlparse(page.url).path and runtime_profile().get('pfe',{}).get('enabled'):
                # Search is navigation, not an application form. Only an unambiguous
                # keyword field and search button, with no identity/upload fields.
                inputs=page.locator('input[name=q],input[name=keywords],input[placeholder*="keyword" i],input[placeholder*="mot-cl" i]')
                visible=[inputs.nth(i) for i in range(inputs.count()) if inputs.nth(i).is_visible()]
                if len(visible)==1:
                    field=visible[0]
                    safe=field.evaluate('(e)=>!e.closest("form")?.querySelector("input[type=file],input[type=password],input[type=email]")')
                    buttons=page.get_by_role('button',name=re.compile(r'^(search(?: jobs)?|rechercher|recherche|chercher|suchen)$',re.I))
                    actions=[buttons.nth(i) for i in range(buttons.count()) if buttons.nth(i).is_visible()]
                    if safe and len(actions)==1:
                        try:
                            field.fill('stage')
                            location=page.locator('input[name=locationsearch]')
                            if location.count()==1 and location.is_visible():location.fill('France')
                            actions[0].click(timeout=5000)
                            try:page.wait_for_load_state('networkidle',timeout=5000)
                            except Exception:pass
                        except Exception:pass
            if '/search' in urlparse(page.url).path:
                # Search navigation may finish before SPA job cards are rendered.
                try:page.locator('a[href*="/job/"],a[href*="/jobs/"]').first.wait_for(state='attached',timeout=10000)
                except Exception:pass
            check_cancelled()
            chunks=[];head=''
            for frame in page.frames[:6]:
                if frame.url.startswith('about:'):continue
                validate_destination(frame.url)
                try:
                    html=frame.content()
                    visible=frame.locator('body').inner_text(timeout=4000)[:60000]
                    # Playwright selectors also traverse open shadow roots.
                    links=frame.locator('a[href]').evaluate_all('(els)=>els.slice(0,250).map(e=>({href:e.href,text:e.innerText}))')
                    soup=BeautifulSoup(html,'lxml')
                    if not chunks and soup.head:head=soup.head.decode_contents()
                    body=soup.body.decode_contents() if soup.body else soup.decode_contents()
                    chunks.append('<section data-frame>'+body+'<section data-visible-page><pre>'+escape(visible)+'</pre>'+ 
                                  ''.join('<a href="'+escape(x['href'],quote=True)+'">'+escape(x['text'] or '')+'</a>' for x in links)+'</section></section>')
                except Exception:continue
            if not chunks:raise ValueError('qr_page_unavailable')
            return ('<html><head>'+head+'</head><body>'+ '\n'.join(chunks)+'</body></html>').encode(), 'text/html', page.url
        finally:
            context.close()
