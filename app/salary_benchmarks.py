"""User-provided salary evidence, including the upstream company-index format."""
import hashlib
import json
import math
from . import capability_store as store
from .tracker_exchange import parse_upload
from .application_intelligence import fold
from .vendor.job_search import salary_lookup


def ingest(name,content):
    if len(content)>2_000_000:raise ValueError('Salary sample file exceeds 2 MB')
    identifier='salary-'+hashlib.sha256(content).hexdigest()[:16]
    if name.lower().endswith('.json'):
        data=json.loads(content.decode('utf-8-sig'))
        if isinstance(data,dict) and 'companies' in data:
            errors,warnings=salary_lookup.collect_validation_issues(data)
            if errors:raise ValueError('; '.join(errors[:10]))
            meta={'name':name,'kind':'company_index','data':data,'warnings':warnings}
            store.save_item(identifier,'salary',meta);return {'id':identifier,'count':len(data['companies']),'kind':'company_index','warnings':warnings}
    rows=parse_upload(name,content);clean=[]
    aliases={'salary':('salary','amount','salaire','薪资','工资'),'currency':('currency','devise','币种'),
             'period':('period','periode','周期'),'company':('company','entreprise','公司'),
             'role':('role','title','poste','岗位'),'city':('city','location','ville','地点'),
             'basis':('basis','base','口径'),'source':('source','来源')}
    for row in rows:
        folded={fold(key):value for key,value in row.items()}
        item={key:next((folded[a] for a in names if a in folded),'') for key,names in aliases.items()}
        value=item['salary']
        try:value=float(str(value).replace(' ','').replace(',','.'))
        except ValueError:raise ValueError('Each sample needs a numeric salary')
        if not math.isfinite(value) or value<=0:raise ValueError('Salary must be a positive finite number')
        if not item['currency'] or not item['period'] or not item['basis']:raise ValueError('Every sample needs currency, period and basis (gross/net/index)')
        item['salary']=value;clean.append(item)
    if not clean:raise ValueError('No salary samples found')
    store.save_item(identifier,'salary',{'name':name,'kind':'samples','rows':clean})
    return {'id':identifier,'count':len(clean),'kind':'samples'}


def percentile(values,percent):
    values=sorted(values);point=(len(values)-1)*percent/100;low=math.floor(point);high=math.ceil(point)
    return values[low]+(values[high]-values[low])*(point-low)


def lookup(identifier,company='',role='',city='',currency='',period='',basis=''):
    data=store.item(identifier,'salary')
    if not data:raise KeyError(identifier)
    if data['kind']=='company_index':
        matches=salary_lookup.search_company(data['data'],company,city or None) if company else data['data']['companies']
        return {'kind':'company_index','matches':matches[:100],'metadata':data['data'].get('metadata',{}),'unit':'index; not a salary amount'}
    rows=[row for row in data['rows'] if all(not value or fold(value) in fold(row.get(key,'')) for key,value in [('company',company),('role',role),('city',city)])]
    groups={}
    for row in rows:
        key=(str(row['currency']).upper(),fold(row['period']),fold(row['basis']))
        if currency and key[0]!=currency.upper() or period and key[1]!=fold(period) or basis and key[2]!=fold(basis):continue
        groups.setdefault(key,[]).append(row)
    result=[]
    for key,samples in groups.items():
        amounts=[row['salary'] for row in samples]
        result.append({'currency':key[0],'period':key[1],'basis':key[2],'count':len(samples),
                       'quantiles':{str(p):round(percentile(amounts,p),2) for p in (10,25,50,75,90)} if len(samples)>=3 else None,
                       'sources':list(dict.fromkeys(str(row.get('source') or '') for row in samples))})
    return {'kind':'samples','groups':result,'note':'Descriptive user-provided samples; different currencies, periods and bases are never mixed.'}
