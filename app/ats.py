from __future__ import annotations

import re
import urllib.parse

ATS_PATTERNS = (
    ('greenhouse', (r'greenhouse\.io', r'boards\.greenhouse', r'job-boards\.greenhouse')),
    ('lever', (r'jobs\.lever\.co', r'lever\.co')),
    ('ashby', (r'jobs\.ashbyhq\.com', r'ashbyhq')),
    ('workday', (r'myworkdayjobs\.com', r'workdayjobs', r'workday')),
    ('smartrecruiters', (r'smartrecruiters\.com',)),
    ('icims', (r'icims\.com', r'icims')),
    ('taleo', (r'taleo\.net', r'oraclecloud.*recruit', r'taleo')),
    ('workable', (r'apply\.workable\.com', r'workable\.com')),
    ('jobvite', (r'jobs\.jobvite\.com', r'jobvite\.com')),
    ('breezy', (r'breezy\.hr',)),
    ('rippling', (r'ats\.rippling\.com', r'rippling\.com/.*/jobs')),
    ('teamtailor', (r'teamtailor\.com',)),
    ('recruitee', (r'recruitee\.com',)),
    ('gem', (r'jobs\.gem\.com', r'gem\.com/jobs')),
    ('successfactors', (r'career.*successfactors', r'successfactors\.com')),
)


def detect_ats(url: str = '', html: str = '') -> str:
    hay = f'{url}\n{html[:200000]}'.lower()
    for key, patterns in ATS_PATTERNS:
        if any(re.search(p, hay, re.I) for p in patterns):
            return key
    host = urllib.parse.urlsplit(url).netloc.lower()
    return 'generic' if host else ''
