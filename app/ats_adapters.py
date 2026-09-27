from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .form_engine import (
    fill_exact_selectors,
    generic_click_apply,
    generic_confirmation,
    generic_fill,
    upload_resume,
)


@dataclass(frozen=True)
class AdapterInfo:
    key: str
    label: str
    mode: str
    notes: str = ''


class BaseAdapter:
    info = AdapterInfo('generic', 'Generic form', 'deterministic+fallback')
    field_map: dict[str, list[str]] = {}
    resume_selectors: list[str] = []

    def prepare(self, page) -> bool:
        return generic_click_apply(page)

    def fill(self, page, profile: dict, resume_path: Path | None, job: dict[str, Any]) -> dict[str, Any]:
        report: dict[str, Any] = {
            'adapter': self.info.key,
            'adapter_mode': self.info.mode,
            'agent_recommended': self.info.mode == 'agent-assisted',
            'filled': [],
            'actions': [],
            'skipped_sensitive': [],
            'skipped_ambiguous': [],
            'errors': [],
        }
        fill_exact_selectors(page, self.field_map, profile, report)
        upload_resume(page, resume_path, self.resume_selectors, report)
        generic = generic_fill(page, profile, resume_path)
        for key in ('filled', 'actions', 'skipped_sensitive', 'skipped_ambiguous', 'errors'):
            report[key].extend(generic.get(key, []))
        report['filled'] = list(dict.fromkeys(report['filled']))
        report['skipped_sensitive'] = list(dict.fromkeys(report['skipped_sensitive']))
        report['skipped_ambiguous'] = list(dict.fromkeys(report['skipped_ambiguous']))[:100]
        return report

    def confirmation(self, page) -> tuple[bool, str]:
        return generic_confirmation(page)


class GreenhouseAdapter(BaseAdapter):
    info = AdapterInfo('greenhouse', 'Greenhouse', 'deterministic', 'Known stable contact/resume fields, generic fallback for custom questions.')
    field_map = {
        'first_name': ['input[name="first_name"]', '#first_name'],
        'last_name': ['input[name="last_name"]', '#last_name'],
        'email': ['input[name="email"]', '#email'],
        'phone': ['input[name="phone"]', '#phone'],
        'linkedin': ['input[name*="linkedin" i]', 'input[id*="linkedin" i]'],
        'portfolio': ['input[name*="website" i]', 'input[name*="portfolio" i]'],
    }
    resume_selectors = ['input[type="file"][name*="resume" i]', 'input[type="file"][id*="resume" i]']


class LeverAdapter(BaseAdapter):
    info = AdapterInfo('lever', 'Lever', 'deterministic', 'Uses Lever contact/url fields then generic fallback.')
    field_map = {
        '__full_name__': ['input[name="name"]'],
        'email': ['input[name="email"]'],
        'phone': ['input[name="phone"]'],
        'linkedin': ['input[name*="LinkedIn" i]', 'input[name*="linkedin" i]'],
        'portfolio': ['input[name*="Portfolio" i]', 'input[name*="website" i]'],
        'current_company': ['input[name="org"]'],
    }
    resume_selectors = ['input[type="file"][name="resume"]', 'input[type="file"][name*="resume" i]']


class AshbyAdapter(BaseAdapter):
    info = AdapterInfo('ashby', 'Ashby', 'deterministic+fallback', 'React controls vary by company; fills only stable contact fields automatically.')
    field_map = {
        'first_name': ['input[name*="firstName" i]', 'input[name*="first_name" i]'],
        'last_name': ['input[name*="lastName" i]', 'input[name*="last_name" i]'],
        'email': ['input[type="email"]', 'input[name*="email" i]'],
        'phone': ['input[type="tel"]', 'input[name*="phone" i]'],
        'linkedin': ['input[name*="linkedin" i]'],
    }
    resume_selectors = ['input[type="file"]']


class SmartRecruitersAdapter(BaseAdapter):
    info = AdapterInfo('smartrecruiters', 'SmartRecruiters', 'deterministic+fallback')
    field_map = {
        'first_name': ['input[id*="first-name" i]', 'input[name*="firstName" i]'],
        'last_name': ['input[id*="last-name" i]', 'input[name*="lastName" i]'],
        'email': ['input[type="email"]'],
        'phone': ['input[type="tel"]'],
    }
    resume_selectors = ['input[type="file"]']


class WorkableAdapter(BaseAdapter):
    info = AdapterInfo('workable', 'Workable', 'deterministic+fallback')
    field_map = {
        'first_name': ['input[name*="firstname" i]', 'input[name*="first_name" i]'],
        'last_name': ['input[name*="lastname" i]', 'input[name*="last_name" i]'],
        'email': ['input[type="email"]'],
        'phone': ['input[type="tel"]'],
    }
    resume_selectors = ['input[type="file"]']


class WorkdayAdapter(BaseAdapter):
    info = AdapterInfo('workday', 'Workday', 'agent-assisted', 'Multi-step/login-heavy flow: deterministic fill is limited; MCP/agent fallback is recommended.')
    field_map = {
        'email': ['input[type="email"]'],
        'phone': ['input[type="tel"]'],
        'first_name': ['input[data-automation-id*="firstName" i]', 'input[name*="firstName" i]'],
        'last_name': ['input[data-automation-id*="lastName" i]', 'input[name*="lastName" i]'],
    }
    resume_selectors = ['input[type="file"]']


class ICIMSAdapter(BaseAdapter):
    info = AdapterInfo('icims', 'iCIMS', 'agent-assisted', 'Portal variants and iframes differ widely; deterministic fill plus human/agent fallback.')


class TaleoAdapter(BaseAdapter):
    info = AdapterInfo('taleo', 'Taleo / Oracle Recruiting', 'agent-assisted', 'Long multi-step forms are intentionally not auto-advanced.')


class JobviteAdapter(BaseAdapter):
    info = AdapterInfo('jobvite', 'Jobvite', 'deterministic+fallback')


class BreezyAdapter(BaseAdapter):
    info = AdapterInfo('breezy', 'Breezy HR', 'deterministic+fallback')


class RipplingAdapter(BaseAdapter):
    info = AdapterInfo('rippling', 'Rippling ATS', 'agent-assisted', 'Dynamic multi-step variants benefit from MCP/browser-agent fallback.')


class TeamtailorAdapter(BaseAdapter):
    info = AdapterInfo('teamtailor', 'Teamtailor', 'deterministic+fallback')


class RecruiteeAdapter(BaseAdapter):
    info = AdapterInfo('recruitee', 'Recruitee', 'deterministic+fallback')


class GemAdapter(BaseAdapter):
    info = AdapterInfo('gem', 'Gem', 'deterministic+fallback')


class SuccessFactorsAdapter(BaseAdapter):
    info = AdapterInfo('successfactors', 'SAP SuccessFactors', 'agent-assisted', 'Multi-step flows vary by tenant; keep final navigation under human/agent control.')


_REGISTRY: dict[str, BaseAdapter] = {
    'greenhouse': GreenhouseAdapter(),
    'lever': LeverAdapter(),
    'ashby': AshbyAdapter(),
    'smartrecruiters': SmartRecruitersAdapter(),
    'workable': WorkableAdapter(),
    'workday': WorkdayAdapter(),
    'icims': ICIMSAdapter(),
    'taleo': TaleoAdapter(),
    'jobvite': JobviteAdapter(),
    'breezy': BreezyAdapter(),
    'rippling': RipplingAdapter(),
    'teamtailor': TeamtailorAdapter(),
    'recruitee': RecruiteeAdapter(),
    'gem': GemAdapter(),
    'successfactors': SuccessFactorsAdapter(),
    'generic': BaseAdapter(),
}


def get_adapter(key: str | None) -> BaseAdapter:
    return _REGISTRY.get((key or '').lower(), _REGISTRY['generic'])


def adapter_catalog() -> list[dict[str, str]]:
    return [
        {'key': key, 'label': adapter.info.label, 'mode': adapter.info.mode, 'notes': adapter.info.notes}
        for key, adapter in _REGISTRY.items()
    ]
