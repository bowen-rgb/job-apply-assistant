"""Read the employer website explicitly supplied by its CV collection notice."""
from bs4 import BeautifulSoup
from .qr_fetching import read_public


def research(payload):
    if payload.get('kind')!='general' or not payload.get('company_website'):return payload
    try:
        raw,_,final=read_public(payload['company_website'])
        soup=BeautifulSoup(raw,'lxml')
        for element in soup.select('script,style,nav,footer,header'):element.decompose()
        description=soup.select_one('meta[name=description]')
        text=' '.join([description.get('content','') if description else '']+[e.get_text(' ',strip=True) for e in soup.select('h1,h2,main p')])[:18000]
        if len(text.strip())<80:raise ValueError('Employer website has insufficient readable business information')
        payload.update(company_business=text,company_business_title=soup.title.get_text(' ',strip=True) if soup.title else '',company_business_source=final,company_business_verified=True)
        payload.pop('company_business_error',None)
    except (OSError,ValueError) as exc:payload['company_business_error']=str(exc)[:300]
    return payload
