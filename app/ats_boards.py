from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BoardConfig:
    ats: str
    board: str
    company: str = ''


def parse_board_configs(rows) -> list[BoardConfig]:
    out: list[BoardConfig] = []
    for row in rows or []:
        if isinstance(row, dict):
            ats = str(row.get('ats', '')).strip().lower()
            board = str(row.get('board', '') or row.get('slug', '') or row.get('token', '')).strip()
            company = str(row.get('company', '')).strip()
        else:
            parts = [x.strip() for x in str(row).split(':', 2)]
            ats = parts[0].lower() if parts else ''
            board = parts[1] if len(parts) > 1 else ''
            company = parts[2] if len(parts) > 2 else ''
        if ats in {'greenhouse', 'ashby', 'lever'} and board:
            out.append(BoardConfig(ats, board, company))
    return out[:200]


def _json_get(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 JobApplyAssistant/7.0',
        'Accept': 'application/json,text/plain,*/*',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def _gh(cfg: BoardConfig) -> Iterable[dict]:
    url = f'https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(cfg.board)}/jobs'
    data = _json_get(url)
    for j in data.get('jobs', []) or []:
        href = j.get('absolute_url') or ''
        if not href:
            continue
        yield {
            'url': href,
            'title': j.get('title') or '',
            'snippet': (j.get('location') or {}).get('name', ''),
            'source': 'boards-api.greenhouse.io',
            'provider_key': 'greenhouse_board',
            'query': f'ats-board:greenhouse:{cfg.board}',
        }


def _ashby(cfg: BoardConfig) -> Iterable[dict]:
    url = 'https://api.ashbyhq.com/posting-api/job-board/' + urllib.parse.quote(cfg.board)
    data = _json_get(url)
    for j in data.get('jobs', []) or []:
        if j.get('isListed') is False:
            continue
        href = j.get('jobUrl') or (f'https://jobs.ashbyhq.com/{cfg.board}/{j.get("id")}' if j.get('id') else '')
        if not href:
            continue
        yield {
            'url': href,
            'title': j.get('title') or '',
            'snippet': j.get('location') or '',
            'source': 'api.ashbyhq.com',
            'provider_key': 'ashby_board',
            'query': f'ats-board:ashby:{cfg.board}',
        }


def _lever(cfg: BoardConfig) -> Iterable[dict]:
    url = f'https://api.lever.co/v0/postings/{urllib.parse.quote(cfg.board)}?mode=json'
    data = _json_get(url)
    for j in data if isinstance(data, list) else []:
        href = j.get('hostedUrl') or j.get('applyUrl') or ''
        if not href:
            continue
        cats = j.get('categories') or {}
        location = cats.get('location') or ''
        yield {
            'url': href,
            'title': j.get('text') or '',
            'snippet': location,
            'source': 'api.lever.co',
            'provider_key': 'lever_board',
            'query': f'ats-board:lever:{cfg.board}',
        }


def discover_boards(rows, report=None) -> Iterable[dict]:
    from .discovery_diagnostics import emit
    for cfg in parse_board_configs(rows):
        source = cfg.ats + '_board'
        emit(report, source, 'board', 'running', query=cfg.board)
        try:
            count = 0
            if cfg.ats == 'greenhouse':
                found = _gh(cfg)
            elif cfg.ats == 'ashby':
                found = _ashby(cfg)
            elif cfg.ats == 'lever':
                found = _lever(cfg)
            for row in found:
                count += 1
                yield row
            emit(report, source, 'board', 'success' if count else 'empty', results=count)
        except Exception as exc:
            emit(report, source, 'board', 'failed', error=str(exc))
            # One broken/renamed company board must not abort the global scan.
            continue
