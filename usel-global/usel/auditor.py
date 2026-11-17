"""Static compiler-output audit. Cannot certify search-engine indexing or ranking."""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit,unquote
import json

class PageInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical=[]; self.alternates={}; self.robots=[]; self.titles=0; self.description=[]; self.lang=None; self.dir=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html': self.lang=a.get('lang'); self.dir=a.get('dir')
        if tag=='title': self.titles+=1
        if tag=='link' and a.get('rel')=='canonical': self.canonical.append(a.get('href'))
        if tag=='link' and a.get('rel')=='alternate' and a.get('hreflang'):
            self.alternates[a['hreflang']]=a.get('href')
        if tag=='meta' and a.get('name')=='robots': self.robots.append(a.get('content',''))
        if tag=='meta' and a.get('name')=='description': self.description.append(a.get('content',''))

def audit_site(root):
    root=Path(root); errors=[]; warnings=[]
    if not root.is_dir(): return {'ok':False,'errors':['output directory absent'],'warnings':[]}
    try:
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        base=manifest['base_url'].rstrip('/')
    except Exception as exc:
        return {'ok':False,'errors':[f'invalid manifest: {exc}'],'warnings':[]}
    pages={}
    for path in root.rglob('index.html'):
        parser=PageInspector()
        try: parser.feed(path.read_text(encoding='utf-8'))
        except Exception as exc: errors.append(f'{path}: invalid html: {exc}');continue
        relative=path.relative_to(root).as_posix()
        if relative!='index.html' and not relative.endswith('/index.html'): continue
        url=base+'/'+relative[:-len('index.html')]
        pages[url]=parser
        if len(parser.canonical)!=1 or parser.canonical[0]!=url: errors.append(f'{relative}: missing/mismatched self canonical')
        if len(parser.description)!=1: errors.append(f'{relative}: missing description')
        if not parser.lang: errors.append(f'{relative}: missing document language')
        if parser.dir not in ('ltr','rtl') and relative!='index.html': errors.append(f'{relative}: missing text direction')
        if parser.titles!=1: errors.append(f'{relative}: expected one title')
        if not parser.robots: errors.append(f'{relative}: robots meta missing')
        if 'noindex' in ','.join(parser.robots) and parser.alternates: warnings.append(f'{relative}: noindex has alternates')
    for url,parser in pages.items():
        if not parser.alternates: continue
        if parser.lang not in parser.alternates or parser.alternates[parser.lang]!=url:
            errors.append(f'{url}: no reciprocal self hreflang')
        if 'x-default' in parser.alternates and parser.alternates['x-default'] not in pages:
            errors.append(f'{url}: x-default points to a page that was not generated')
        for locale,otherurl in parser.alternates.items():
            if locale=='x-default':continue
            other=pages.get(otherurl)
            if other is None or other.alternates.get(parser.lang)!=url:
                errors.append(f'{url}: {locale} does not reciprocate {otherurl}')
    try:
        xml=ET.parse(root/'sitemap.xml')
        ns='{http://www.sitemaps.org/schemas/sitemap/0.9}'
        sitemaps=[]
        if xml.getroot().tag==ns+'sitemapindex':
            for node in xml.getroot().findall(ns+'sitemap'):
                link=node.findtext(ns+'loc')
                if not link or not link.startswith(base+'/'): errors.append('bad sitemap index loc');continue
                sitemaps.append(root/link.rsplit('/',1)[-1])
        else:sitemaps=[root/'sitemap.xml']
        seen=set()
        for f in sitemaps:
            tree=ET.parse(f)
            for item in tree.getroot().findall(ns+'url'):
                loc=item.findtext(ns+'loc')
                if loc in seen: errors.append(f'duplicate sitemap URL {loc}')
                seen.add(loc)
                if loc not in pages: errors.append(f'sitemap URL missing generated HTML: {loc}')
                elif 'noindex' in ','.join(pages[loc].robots): errors.append(f'noindex URL in sitemap: {loc}')
        if len(seen)!=manifest['indexed_pages']: errors.append('indexed pages count differs from sitemap')
    except Exception as exc: errors.append(f'invalid sitemap XML: {exc}')
    try:
        robots=(root/'robots.txt').read_text(encoding='utf-8')
        if 'Sitemap: '+base+'/sitemap.xml' not in robots: errors.append('robots sitemap URL missing')
    except Exception: errors.append('robots.txt unavailable')
    if manifest['indexed_pages']==0: warnings.append('there are no indexable pages; expected if everything is noindex')
    return {'ok':not errors,'errors':errors,'warnings':warnings,'rendered_files':len(pages),
            'indexed_pages':manifest['indexed_pages'],'tested_scope':'generated HTML, sitemap, robots and reciprocal alternates only'}
