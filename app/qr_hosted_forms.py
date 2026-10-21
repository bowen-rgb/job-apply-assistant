"""Identify a hosted form's recipient, not its hosting service."""
import re
from urllib.parse import urlparse

HOST_NAMES={'google','google forms','google formulaires','forms','formulaires google','google llc','google inc.','google ireland limited','google workspace'}
ATS_NAMES={'successfactors','sap successfactors','sap','sap se','sap successfactors recruiting','successfactors careers'}


def is_hosted_ats(url):
    host=urlparse(url or '').hostname or ''
    return any(host==suffix or host.endswith('.'+suffix) for suffix in ('successfactors.eu','successfactors.com','successfactors.cn'))


def is_host_name(name,url):
    value=str(name or '').strip().lower()
    return (is_google_form(url) and value in HOST_NAMES) or (is_hosted_ats(url) and value in ATS_NAMES)


def is_google_form(url):
    p=urlparse(url or '')
    return p.hostname=='forms.gle' or (p.hostname=='docs.google.com' and p.path.startswith('/forms/'))


def form_identity(title,body,url):
    if not is_google_form(url):return {}
    title=re.sub(r'\s*[-|–—]\s*Google\s*(?:Forms|Formulaires)\s*$','',title or '',flags=re.I).strip()
    patterns=[r'^(?:r[eé]cup[eé]ration|collecte|d[eé]p[oô]t)\s+(?:de\s+)?(?:vos?\s+)?CV\s+(?:au|aux|chez|pour|[àa])\s+(?:le\s+|la\s+|l[’\x27])?(.+?)\s*$',
              r'^(?:CV|resume)\s+(?:collection|submission|drop[ -]?off)\s+(?:at|for|to)\s+(.+?)\s*$']
    candidates=[]
    for line in (title+'\n'+(body or '')[:6000]).splitlines():
        for pattern in patterns:
            match=re.search(pattern,line.strip(),re.I)
            if match:candidates.append((match[1],line.strip()))
    match=re.search(r'(?:examin[eé](?:e)?s?|trait[eé](?:e)?s?)\s+par\s+(?:le\s+|la\s+|l[’\x27])?([^.!?\n]{2,90})',body or '',re.I)
    if match and re.search(r'\bCV\b|r[eé]sum[eé]',(body or '')[:2000],re.I) and not is_host_name(match[1],url):candidates.append((match[1],match[0]))
    from .qr_context import company_name
    for name,quote in candidates:
        name=company_name(name.strip(' .:'))
        if name:return {'company':name,'company_quote':quote,'company_evidence':'form.recipient','kind':'general'}
    return {}


def repair_identity(payload):
    """Also repairs old saved Google Forms previews using their original text."""
    candidates=[payload.get(k,'') for k in ('final_url','url','original_qr_url')]
    url=next((u for u in candidates if is_google_form(u) or is_hosted_ats(u)),candidates[0])
    if is_hosted_ats(url):
        if is_host_name(payload.get('company'),url) and payload.get('company_evidence')!='JobPosting.hiringOrganization':payload.update(company='',company_quote='',company_evidence='',needs_enrichment=True)
        return payload
    if not is_google_form(url):return payload
    explicit=form_identity(payload.get('page_title') or payload.get('title',''),payload.get('body',''),url)
    if explicit:
        payload.update(explicit,company_source_url=url,role_title='',tasks=[])
    elif str(payload.get('company','')).strip().lower() in HOST_NAMES and payload.get('company_evidence')!='JobPosting.hiringOrganization':
        payload.update(company='',company_quote='',company_evidence='',needs_enrichment=True)
    return payload
