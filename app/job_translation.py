"""Display-only job-title translations; never change application source data.

Common recruitment terms are translated locally. Other public titles use the
MyMemory GET API, with a bounded timeout and a content-addressed local cache.
No candidate profile, CV, application answers or contact details are sent.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from .profile_store import ROOT

CACHE_DIR = ROOT / 'data' / 'title_translations'
LANGUAGES = ('zh', 'en', 'de', 'es', 'pt')
_network_slots = threading.BoundedSemaphore(3)
# Ordered by specificity. Brands and place names remain verbatim.
TERMS = (
    (r'assistant(?:e)?\s+hall\s+de\s+nuit', ('夜班酒店大堂助理', 'Night lobby assistant', 'Nacht-Lobbyassistenz', 'Asistente nocturno de vestíbulo', 'Assistente noturno de receção')),
    (r'agent(?:e)?\s+polyvalent(?:e)?\s+en\s+cr[eè]che', ('托育中心综合工作人员', 'Nursery support worker', 'Kita-Allroundkraft', 'Personal polivalente de guardería', 'Assistente polivalente de creche')),
    (r'h[oô]te(?:\(sse\)|sse)?\s+d[’\x27]\s*accueil', ('接待员', 'Reception host', 'Empfangskraft', 'Personal de recepción', 'Assistente de receção')),
    (r'chef(?:fe)?\s+de\s+service', ('部门主管', 'Department manager', 'Abteilungsleitung', 'Jefe de departamento', 'Chefe de departamento')),
    (r'r[eé]ceptionniste', ('前台接待员', 'Receptionist', 'Rezeptionist', 'Recepcionista', 'Rececionista')),
    (r'agent(?:e)?\s+d[’\x27]\s*accueil', ('接待专员', 'Reception officer', 'Empfangsmitarbeiter', 'Agente de recepción', 'Agente de receção')),
    (r'employ[eé](?:e|\(e\))?\s+polyvalent(?:e|\(e\))?(?:\s+de\s+restauration)?', ('综合服务员工', 'General service worker', 'Allround-Servicekraft', 'Empleado polivalente', 'Funcionário polivalente')),
    (r'agent(?:e)?\s+polyvalent(?:e)?', ('综合工作人员', 'General support worker', 'Allroundkraft', 'Agente polivalente', 'Agente polivalente')),
    (r'pr[eé]parateur(?:trice)?\s+de\s+commandes', ('订单拣货员', 'Order picker', 'Kommissionierer', 'Preparador de pedidos', 'Preparador de encomendas')),
)
QUALIFIERS = (
    (r'\bextra\b', ('临时支援', 'Casual shift', 'Aushilfe', 'Refuerzo temporal', 'Reforço temporário')),
    (r'\bCDD\b', ('固定期限合同', 'Fixed-term', 'Befristet', 'Contrato temporal', 'Contrato a termo')),
    (r'\bCDI\b', ('无固定期限合同', 'Permanent', 'Unbefristet', 'Contrato indefinido', 'Contrato sem termo')),
    (r'\bde\s+nuit\b|\bnuit\b', ('夜班', 'Night shift', 'Nachtschicht', 'Turno nocturno', 'Turno noturno')),
    (r'\btournant(?:e)?\b', ('轮班', 'Rotating shifts', 'Wechselschicht', 'Turnos rotativos', 'Turnos rotativos')),
    (r'\btemps\s+partiel\b', ('兼职', 'Part-time', 'Teilzeit', 'Tiempo parcial', 'Tempo parcial')),
    (r'\btemps\s+(?:plein|complet)\b', ('全职', 'Full-time', 'Vollzeit', 'Tiempo completo', 'Tempo inteiro')),
    (r'\bpolyvalent(?:e)?\b', ('多职能', 'Multifunctional', 'Vielseitig', 'Polivalente', 'Polivalente')),
    (r'\b([0-9]+)\s*[hH]\b', (r'\1小时', r'\1h', r'\1h', r'\1h', r'\1h')),
)


def local_title(title: str, language: str) -> str | None:
    if language not in LANGUAGES:
        return title if language == 'fr' else None
    index = LANGUAGES.index(language)
    translated = title
    matched = False
    for pattern, values in TERMS:
        translated, count = re.subn(pattern, values[index], translated, flags=re.I)
        matched = matched or bool(count)
    if not matched:
        return None
    for pattern, values in QUALIFIERS:
        translated = re.sub(pattern, values[index], translated, flags=re.I)
    translated = re.sub(r'\(?\b[HF]\s*/\s*[HF](?:\s*/\s*[XNB]+)?\b\)?', '', translated, flags=re.I)
    return re.sub(r'\s+', ' ', translated).strip(' —-')


def translate_title(title: str, language: str) -> dict:
    title = title.strip()
    local = local_title(title, language)
    if local:
        return {'title': local, 'status': 'ready', 'method': 'glossary'}
    if not title or len(title.encode('utf-8')) > 450:
        return {'title': title, 'status': 'unavailable'}
    key = hashlib.sha256(f'v1:{language}:{title}'.encode()).hexdigest()
    path = CACHE_DIR / f'{key}.json'
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8'))
    try:
        query = urllib.parse.urlencode({'q': title, 'langpair': f'autodetect|{"zh-CN" if language == "zh" else language}', 'mt': 1})
        request = urllib.request.Request('https://api.mymemory.translated.net/get?' + query, headers={'User-Agent': 'JobApplyAssistant/8.4'})
        with _network_slots, urllib.request.urlopen(request, timeout=8) as response:
            result = json.load(response)
        text = html.unescape(result.get('responseData', {}).get('translatedText', '')).strip()
        if int(result.get('responseStatus', 0)) != 200 or result.get('quotaFinished') or not text or len(text) > 1500:
            raise ValueError('Translation unavailable')
        output = {'title': text, 'status': 'ready', 'method': 'machine'}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f'.{uuid4().hex}.tmp')
        temporary.write_text(json.dumps(output, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
        return output
    except (OSError, ValueError, TypeError):
        return {'title': title, 'status': 'unavailable'}


def translate_jobs(jobs: list[dict], language: str) -> dict:
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda job: translate_title(job.get('title') or '', language), jobs))
    return {str(job['id']): {**result, 'original': job.get('title') or ''} for job, result in zip(jobs, results)}
