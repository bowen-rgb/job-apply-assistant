from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    domain: str
    enabled_by_default: bool = True


@dataclass(frozen=True)
class DirectSeedSpec:
    """Public listing page that can be crawled before search-engine discovery.

    page_url supports ``{page}``. The link_pattern is matched against the absolute
    URL discovered on the listing page. These adapters only discover public offer
    URLs; the normal extractor/scorer still validates every detail page.
    """
    provider_key: str
    page_url: str
    link_pattern: str
    default_pages: int = 1


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec('france_travail', 'France Travail', 'francetravail.fr'),
    SourceSpec('hellowork', 'HelloWork', 'hellowork.com'),
    SourceSpec('indeed', 'Indeed', 'indeed.com'),
    SourceSpec('wttj', 'Welcome to the Jungle', 'welcometothejungle.com'),
    SourceSpec('linkedin', 'LinkedIn Jobs', 'linkedin.com', False),
    SourceSpec('glassdoor', 'Glassdoor', 'glassdoor.com', False),
    SourceSpec('cityone', 'City One', 'cityone.fr'),
    SourceSpec('plany', 'Plany', 'plany.jobs'),
    SourceSpec('staffme', 'StaffMe', 'staffme.fr'),
    SourceSpec('adecco', 'Adecco', 'adecco.fr'),
    SourceSpec('manpower', 'Manpower', 'manpower.fr'),
    SourceSpec('randstad', 'Randstad', 'randstad.fr'),
    SourceSpec('synergie', 'Synergie', 'synergie.fr'),
    SourceSpec('meteojob', 'Meteojob', 'meteojob.com'),
    SourceSpec('crit', 'CRIT', 'crit-job.com'),
    SourceSpec('samsic', 'Samsic Emploi', 'samsic-emploi.fr'),
    SourceSpec('actual', 'Groupe Actual', 'groupeactual.eu'),
    SourceSpec('greenhouse_board', 'Greenhouse boards', 'greenhouse.io', False),
    SourceSpec('ashby_board', 'Ashby boards', 'ashbyhq.com', False),
    SourceSpec('lever_board', 'Lever boards', 'lever.co', False),
)


# Direct adapters are deliberately limited to sources whose public listing URLs are
# simple and stable enough to crawl without a private API/login. Other sources are
# still discovered through targeted web search and then processed identically.
DIRECT_SEEDS: tuple[DirectSeedSpec, ...] = (
    DirectSeedSpec(
        'plany',
        'https://www.plany.jobs/offres-emploi?page={page}',
        r'^https?://(?:www\.)?plany\.jobs/offres-emploi/\d+-',
        3,
    ),
    DirectSeedSpec(
        'cityone',
        'https://www.cityone.fr/rejoignez-nous/?_sfm_geo_region=Ile-de-France&sf_paged={page}',
        r'^https?://(?:www\.)?cityone\.fr/(?:job/|rejoignez-nous/[^/?]+-\d+)',
        3,
    ),
)


def _custom_key(domain: str) -> str:
    import re
    slug = re.sub(r'[^a-z0-9]+', '_', (domain or '').lower()).strip('_')[:60]
    return 'custom_' + slug if slug else ''


def custom_sources(profile: dict) -> list[SourceSpec]:
    out: list[SourceSpec] = []
    seen = set()
    for row in profile.get('custom_sources', []) or []:
        if isinstance(row, str):
            parts = [x.strip() for x in row.split('|', 1)]
            label = parts[0] if len(parts) > 1 else parts[0]
            domain = parts[1] if len(parts) > 1 else parts[0]
        elif isinstance(row, dict):
            label = str(row.get('label', '')).strip()
            domain = str(row.get('domain', '')).strip()
        else:
            continue
        domain = domain.removeprefix('https://').removeprefix('http://').strip('/').split('/')[0].lower()
        if not domain or '.' not in domain or domain in seen:
            continue
        seen.add(domain)
        out.append(SourceSpec(_custom_key(domain), label or domain, domain, True))
    return out[:100]


def all_sources(profile: dict | None = None) -> list[SourceSpec]:
    return list(SOURCES) + (custom_sources(profile or {}) if profile is not None else [])


def source_map(profile: dict | None = None) -> dict[str, SourceSpec]:
    return {s.key: s for s in all_sources(profile)}


def enabled_sources(profile: dict) -> list[SourceSpec]:
    configured = profile.get('enabled_sources', None)
    if configured is None:
        builtins = [s for s in SOURCES if s.enabled_by_default]
    else:
        wanted = set(configured)
        builtins = [s for s in SOURCES if s.key in wanted]
    # Custom domains are explicit user entries; presence means enabled.
    return builtins + custom_sources(profile)


def enabled_direct_seeds(profile: dict) -> list[DirectSeedSpec]:
    if profile.get('direct_source_discovery', True) is False:
        return []
    wanted = {s.key for s in enabled_sources(profile)}
    explicit = profile.get('direct_sources')
    if explicit:
        wanted &= set(explicit)
    return [s for s in DIRECT_SEEDS if s.provider_key in wanted]


def _role_expr(profile: dict, max_roles: int = 12) -> str:
    roles = [r.strip() for r in profile.get('preferred_roles', []) if str(r).strip()]
    if not roles:
        return ''
    return '(' + ' OR '.join(f'"{r}"' for r in roles[:max_roles]) + ')'


def _contract_expr(profile: dict) -> str:
    cs = [c.strip() for c in profile.get('contracts', []) if str(c).strip()]
    return '(' + ' OR '.join(cs) + ')' if cs else ''


def _location_expr(profile: dict) -> str:
    locs = [x.strip() for x in profile.get('locations', []) if str(x).strip()]
    if not locs:
        return ''
    # Keep search-engine queries compact. The evaluator handles the full location list later.
    return '(' + ' OR '.join(f'"{x}"' for x in locs[:3]) + ')'



def _exclude_expr(profile: dict, max_terms: int = 4) -> str:
    terms = [str(x).strip() for x in profile.get('exclude_terms', []) if str(x).strip()]
    # Search engines treat leading '-' as a negative term. Hard filtering still happens locally.
    return ' '.join(f'-"{x}"' for x in terms[:max_terms])


def _industry_expr(profile: dict, max_terms: int = 2) -> str:
    xs = [str(x).strip() for x in profile.get('industries', []) if str(x).strip()]
    return '(' + ' OR '.join(f'"{x}"' for x in xs[:max_terms]) + ')' if xs else ''

def build_queries(profile: dict) -> list[tuple[str, str]]:
    """Return (provider_key, web-search-query) pairs.

    Public search engines remain the broad discovery layer, while direct adapters
    provide a fast path for sources such as Plany and City One. We avoid depending
    on undocumented/private job-board APIs.
    """
    role_expr = _role_expr(profile)
    contract_expr = _contract_expr(profile)
    location_expr = _location_expr(profile)
    exclude_expr = _exclude_expr(profile)
    industry_expr = _industry_expr(profile)
    queries: list[tuple[str, str]] = []

    # Global discovery catches employer career sites and smaller agencies.
    include_terms = [x.strip() for x in profile.get('include_terms', []) if str(x).strip()]
    extra = '(' + ' OR '.join(f'"{x}"' for x in include_terms[:3]) + ')' if include_terms else ''
    base = ' '.join(x for x in [role_expr, contract_expr, location_expr, industry_expr, extra, exclude_expr, '(job OR emploi OR careers)'] if x).strip()
    # One focused query per source gives broad coverage without exploding query count.
    for src in enabled_sources(profile):
        focused = ' '.join(x for x in [f'site:{src.domain}', role_expr, location_expr, '(job OR emploi)'] if x)
        queries.append((src.key, focused))

    # Optional keywords and contract details rank results locally, rather than
    # requiring every indexed page to repeat the candidate's wording.
    queries.extend([
        ('global', ' '.join(x for x in [role_expr, location_expr, '(recrutement OR hiring OR careers)'] if x)),
        ('global', base),
    ])

    cap = int(profile.get('search_queries_per_run', 18))
    return queries[:max(1, cap)]
