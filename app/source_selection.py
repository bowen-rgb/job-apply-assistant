"""One source selection shared by legacy settings and integration-specific forms."""
from .profile_store import load_profile_raw,save_profile_raw


def enabled(key,profile=None,fallback=False):
    settings=profile if profile is not None else load_profile_raw().get('automation',{})
    keys=settings.get('enabled_sources')
    return bool(fallback) if keys is None else key in keys


def select(key,value):
    raw=load_profile_raw();settings=raw.setdefault('automation',{})
    keys=settings.get('enabled_sources')
    if keys is None:
        from .providers import SOURCES
        keys=[source.key for source in SOURCES if source.enabled_by_default]
    keys=list(keys)
    if value and key not in keys:keys.append(key)
    if not value:keys=[existing for existing in keys if existing!=key]
    settings['enabled_sources']=keys
    save_profile_raw({'automation':settings})
