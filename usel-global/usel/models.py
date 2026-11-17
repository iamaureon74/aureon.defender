"""Validate an intentionally small USEL declarative language, YAML or JSON."""
from __future__ import annotations
import json
import re
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlsplit, quote

LOCALE_RE = re.compile(r'^[a-z]{2,3}(?:-[A-Za-z]{2,8}){0,2}$')
SLUG_RE = re.compile(r'^[^?#\\\\\s\x00-\x1f\x7f]+$')   # no query, fragment, backslash, whitespace or control chars

class SpecError(ValueError):
    pass

def read_spec(text):
    if len(text.encode('utf-8')) > 1024 * 1024:
        raise SpecError('input exceeds 1 MB')
    try:
        import yaml
    except ImportError:
        yaml = None
    try:
        obj = json.loads(text) if text.lstrip().startswith('{') else yaml.safe_load(text) if yaml else None
    except Exception as ex:
        raise SpecError(f'cannot parse source: {ex}') from ex
    if not isinstance(obj, dict): raise SpecError('specification must be an object (YAML or JSON)')
    return validate_spec(obj)

def require_https(url, label):
    if not isinstance(url, str): raise SpecError(f'{label}: expected URL')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise SpecError(f'{label}: expected absolute https URL without query, fragment or credentials')
    if parts.path not in ('','/'):
        raise SpecError(f'{label}: base_url must have no path')
    return url.rstrip('/')

def validate_spec(spec):
    if spec.get('usel') != 1: raise SpecError('usel must be 1')
    require_https(spec.get('base_url'), 'base_url')
    if not isinstance(spec.get('site_name'), str) or not spec['site_name'].strip(): raise SpecError('site_name required')
    # Geographic targeting is independent of which translations actually exist.
    from .registry import load_countries
    allowed_markets={c['code'] for c in load_countries()}
    markets=spec.get('market_targets','all')
    if markets != 'all' and (not isinstance(markets,list) or not markets or any(not isinstance(m,str) or m not in allowed_markets for m in markets)):
        raise SpecError('market_targets must be all or an array of known ISO/jurisdiction codes')
    pages = spec.get('pages')
    if not isinstance(pages,list) or not pages: raise SpecError('pages must be a nonempty list')
    ids, paths = set(), set()
    for page in pages:
        if not isinstance(page, dict): raise SpecError('invalid page')
        pid = page.get('id')
        if not isinstance(pid,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}',pid): raise SpecError('bad page id')
        if pid in ids: raise SpecError(f'duplicate page id: {pid}')
        ids.add(pid)
        if not isinstance(page.get('public'),bool): raise SpecError(f'page {pid}: public must be boolean')
        if not isinstance(page.get('index'),bool): raise SpecError(f'page {pid}: index must be boolean')
        if not page['public'] and page['index']: raise SpecError(f'page {pid}: private content cannot be indexed')
        if page.get('lastmod') is not None:
            try:
                parsed=date.fromisoformat(page['lastmod'])
                if parsed.isoformat()!=page['lastmod']: raise ValueError('non-canonical date')
            except (ValueError,TypeError):
                raise SpecError(f'page {pid}: lastmod must be a valid YYYY-MM-DD date')
        locales = page.get('locales')
        if not isinstance(locales,dict) or not locales: raise SpecError(f'page {pid}: locales must be nonempty')
        for locale, content in locales.items():
            if not isinstance(locale,str) or not LOCALE_RE.fullmatch(locale): raise SpecError(f'invalid locale: {locale}')
            if not isinstance(content,dict): raise SpecError(f'{pid}:{locale}: missing fields')
            for key in ('slug','title','description','body'):
                if not isinstance(content.get(key),str) or not content[key].strip():
                    raise SpecError(f'{pid}:{locale}: {key} must be nonempty text')
            slug=content['slug'].strip('/')
            if (not slug or not SLUG_RE.fullmatch(slug) or '..' in PurePosixPath(slug).parts
                or any(s in ('.','') for s in slug.split('/')) or slug.startswith('.')):
                raise SpecError(f'{pid}:{locale}: invalid slug')
            path = f'/{quote(locale, safe="")}/{quote(slug, safe="/")}/'
            if path in paths: raise SpecError(f'URL collision {path}')
            paths.add(path)
    default=spec.get('default_locale')
    if default is not None:
        if not isinstance(default,str) or not LOCALE_RE.fullmatch(default):
            raise SpecError('default_locale must be a locale code such as en-US')
        if not any(default in p['locales'] for p in pages if p['public'] and p['index']):
            raise SpecError('default_locale is not used by any public, indexable page')
    key=spec.get('indexnow_key')
    if key is not None and (not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9-]{8,128}',key)):
        raise SpecError('indexnow_key must be 8-128 letters, digits or hyphens')
    engines = spec.get('engines',['all'])
    if not isinstance(engines,list) or not engines or not all(isinstance(s,str) for s in engines):
        raise SpecError('engines must be an array')
    if 'all' in engines and len(engines)>1: raise SpecError('use all alone or explicit engine ids')
    return spec
