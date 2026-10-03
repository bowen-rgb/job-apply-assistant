from __future__ import annotations
import hashlib
import html as html_lib
import json
import re
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Any
from bs4 import BeautifulSoup


FRENCH_MONTHS = {
    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'aout': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12,
}
FRENCH_MONTHS.update(dict(zip(
    ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'), range(1, 13))))
MONTH_PATTERN = '|'.join(FRENCH_MONTHS)


@dataclass
class JobDocument:
    url: str
    canonical_url: str
    title: str = ''
    company: str = ''
    location: str = ''
    employment_type: str = ''
    start_date: str = ''
    end_date: str = ''
    date_posted: str = ''
    valid_through: str = ''
    salary: str = ''
    description: str = ''
    text: str = ''
    structured_json: str = ''
    fingerprint: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_url(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        drop = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref', 'source'}
        q = [(k, v) for k, v in q if k.lower() not in drop]
        path = re.sub(r'/+$', '', p.path) or '/'
        return urllib.parse.urlunsplit((p.scheme.lower() or 'https', p.netloc.lower(), path, urllib.parse.urlencode(q), ''))
    except Exception:
        return url


def _flatten_jsonld(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _flatten_jsonld(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flatten_jsonld(v)


def _is_jobposting(obj: dict) -> bool:
    typ = obj.get('@type')
    if isinstance(typ, str):
        return typ.lower() == 'jobposting'
    if isinstance(typ, list):
        return any(str(x).lower() == 'jobposting' for x in typ)
    return False


def _pick_jobposting(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(' ', strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            # Some sites embed control chars/trailing junk. Avoid unsafe eval.
            continue
        for obj in _flatten_jsonld(parsed):
            if _is_jobposting(obj):
                return obj
    return None


def _org_name(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get('name') or '').strip()
    return str(v or '').strip()


def _location(v: Any) -> str:
    if isinstance(v, list):
        parts = [_location(x) for x in v]
        return ' / '.join(x for x in parts if x)
    if not isinstance(v, dict):
        return str(v or '').strip()
    addr = v.get('address', v)
    if not isinstance(addr, dict):
        return str(addr or '').strip()
    vals = [addr.get('streetAddress'), addr.get('postalCode'), addr.get('addressLocality'), addr.get('addressRegion'), addr.get('addressCountry')]
    out = ', '.join(str(x).strip() for x in vals if x)
    return out


def _salary(v: Any) -> str:
    if not isinstance(v, dict):
        return str(v or '').strip()
    currency = v.get('currency') or ''
    value = v.get('value')
    if isinstance(value, dict):
        unit = value.get('unitText') or ''
        mn = value.get('minValue')
        mx = value.get('maxValue')
        val = value.get('value')
        if mn is not None or mx is not None:
            core = f"{mn if mn is not None else '?'}–{mx if mx is not None else '?'}"
        else:
            core = str(val or '')
        return ' '.join(x for x in [core, currency, unit] if x)
    return ' '.join(x for x in [str(value or ''), str(currency)] if x)


def _clean_html_text(v: str) -> str:
    if not v:
        return ''
    soup = BeautifulSoup(html_lib.unescape(str(v)), 'lxml')
    return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()


def _normalize_date(v: Any) -> str:
    if not v:
        return ''
    s = str(v).strip()
    # ISO date/time -> ISO date.
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).date().isoformat()
    except Exception:
        pass
    m = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            pass
    return s[:40]


def _extract_context_date(text: str, keywords: tuple[str, ...]) -> str:
    low = text.lower()
    # numeric forms near a keyword
    for kw in keywords:
        for m in re.finditer(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', low):
            chunk = text[m.end(): min(len(text), m.end()+70)]
            d = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b', chunk)
            if d:
                try:
                    return date(int(d.group(3)), int(d.group(2)), int(d.group(1))).isoformat()
                except ValueError:
                    pass
            fm = re.search(r'\b(\d{1,2})\s+(' + MONTH_PATTERN + r')\s+(20\d{2})\b', chunk, re.I)
            if fm:
                month = FRENCH_MONTHS[fm.group(2).lower()]
                try:
                    return date(int(fm.group(3)), month, int(fm.group(1))).isoformat()
                except ValueError:
                    pass
    return ''


def extract_date_range(text: str) -> tuple[str, str]:
    numeric = re.search(r'\bdu\s+(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\s+au\s+(\d{1,2})[/-](\d{1,2})[/-](20\d{2})', text or '', re.I)
    if numeric:
        a, ma, ya, b, mb, yb = map(int, numeric.groups())
        try:
            return date(ya, ma, a).isoformat(), date(yb, mb, b).isoformat()
        except ValueError:
            pass
    pattern = r'\bdu\s+(\d{1,2})(?:\s+(' + MONTH_PATTERN + r')\s+(20\d{2}))?\s+au\s+(\d{1,2})\s+(' + MONTH_PATTERN + r')\s+(20\d{2})\b'
    match = re.search(pattern, text or '', re.I)
    if match:
        a, month_a, year_a, b, month_b, year_b = match.groups()
        try:
            return (date(int(year_a or year_b), FRENCH_MONTHS[(month_a or month_b).lower()], int(a)).isoformat(),
                    date(int(year_b), FRENCH_MONTHS[month_b.lower()], int(b)).isoformat())
        except ValueError:
            pass
    return '', ''


def _heuristic_contract(text: str) -> str:
    low = text.lower()
    patterns = [
        ('CDD', r'\bcdd\b'), ('Intérim', r'\bint[eé]rim(?:aire)?\b'), ('Mission', r'\bmission\b'),
        ('CDI', r'\bcdi\b'), ('Stage', r'\bstage\b'), ('Alternance', r'\balternance\b'),
        ('Freelance', r'\bfreelance\b|\bind[eé]pendant\b'),
    ]
    hits = [label for label, rx in patterns if re.search(rx, low, re.I)]
    return ', '.join(hits[:4])


def extract_job_document(html: str, url: str, fallback_title: str = '', fallback_snippet: str = '') -> JobDocument:
    soup = BeautifulSoup(html or '', 'lxml')
    canonical = ''
    c = soup.select_one('link[rel="canonical"]')
    if c and c.get('href'):
        canonical = urllib.parse.urljoin(url, c.get('href'))
    canonical = canonicalize_url(canonical or url)

    job = _pick_jobposting(soup) or {}
    title = str(job.get('title') or job.get('name') or fallback_title or (soup.title.get_text(' ', strip=True) if soup.title else '')).strip()
    company = _org_name(job.get('hiringOrganization'))
    location = _location(job.get('jobLocation')) or _location(job.get('applicantLocationRequirements'))
    employment = job.get('employmentType') or ''
    if isinstance(employment, list):
        employment = ', '.join(str(x) for x in employment)
    description = _clean_html_text(job.get('description') or '')

    # Page body is still valuable when JSON-LD is partial.
    for tag in soup(['script', 'style', 'noscript', 'svg', 'nav', 'header', 'footer']):
        tag.decompose()
    content = soup.select_one('main, article, [role="main"]') or soup
    text = re.sub(r'\n{3,}', '\n\n', content.get_text('\n', strip=True))
    # JSON-LD describes this offer; page chrome and related offers are not evidence.
    combined = '\n'.join(x for x in [title, description or text, fallback_snippet] if x)

    if not employment:
        employment = _heuristic_contract(combined)

    start_date = _normalize_date(job.get('jobStartDate') or job.get('startDate'))
    end_date = _normalize_date(job.get('jobEndDate') or job.get('endDate'))
    range_start, range_end = extract_date_range(combined)
    start_date, end_date = start_date or range_start, end_date or range_end
    if not start_date:
        start_date = _extract_context_date(combined, ('début', 'debut', 'à partir du', 'a partir du', 'du'))
    if not end_date:
        end_date = _extract_context_date(combined, ("jusqu'au", 'jusqu’au', 'fin de contrat', 'fin', 'au'))

    date_posted = _normalize_date(job.get('datePosted'))
    valid_through = _normalize_date(job.get('validThrough'))
    salary = _salary(job.get('baseSalary') or job.get('estimatedSalary'))

    fp_seed = '|'.join([
        re.sub(r'\s+', ' ', title.lower()).strip(),
        re.sub(r'\s+', ' ', company.lower()).strip(),
        re.sub(r'\s+', ' ', location.lower()).strip(),
        employment.lower().strip(),
    ])
    fingerprint = hashlib.sha256(fp_seed.encode('utf-8', errors='ignore')).hexdigest()[:24]

    keep_json = {}
    for key in ('@type', 'title', 'name', 'hiringOrganization', 'jobLocation', 'employmentType', 'datePosted', 'validThrough', 'jobStartDate', 'jobEndDate', 'endDate', 'baseSalary'):
        if key in job:
            keep_json[key] = job[key]

    return JobDocument(
        url=url,
        canonical_url=canonical,
        title=title[:500],
        company=company[:300],
        location=location[:500],
        employment_type=str(employment)[:250],
        start_date=start_date,
        end_date=end_date,
        date_posted=date_posted,
        valid_through=valid_through,
        salary=salary[:300],
        description=description[:40000],
        text=combined[:90000],
        structured_json=json.dumps(keep_json, ensure_ascii=False)[:30000],
        fingerprint=fingerprint,
    )
