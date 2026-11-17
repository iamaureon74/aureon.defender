"""Real HTML, sitemap, robots, metadata and engine strategy output."""
from __future__ import annotations
import csv
import html
import json
import re
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from .registry import load_engines, load_countries
from .models import validate_spec, SpecError

NS='http://www.sitemaps.org/schemas/sitemap/0.9'
XHTML='http://www.w3.org/1999/xhtml'
ET.register_namespace('',NS)
ET.register_namespace('xhtml',XHTML)

def url_path(locale, slug):
    slug = slug.strip('/')
    return f'/{quote(locale,safe="")}/{quote(slug,safe="/")}/'

def public_pages(spec):
    for page in spec['pages']:
        for locale, entry in page['locales'].items():
            yield page,locale,entry

RTL_LANGS={'ar','he','fa','ur','ps','sd','ug','yi','dv','ckb','syr'}

def text_direction(locale):
    parts=locale.split('-')
    if any(p.lower() in ('arab','hebr','thaa','syrc','nkoo','adlm') for p in parts[1:]):return 'rtl'
    return 'rtl' if parts[0].lower() in RTL_LANGS else 'ltr'

def as_text(content):
    content=content.replace('\r\n','\n').replace('\r','\n')
    return html.escape(content,quote=True).replace('\n','</p><p>')

def page_alternates(spec,page,base):
    """hreflang map for a public indexable page, plus x-default when the site names a default locale."""
    if not (page['public'] and page['index']):return {}
    alts={l:base+url_path(l,ent['slug']) for l,ent in page['locales'].items()}
    default=spec.get('default_locale')
    if default in alts and len(alts)>1:alts['x-default']=alts[default]
    return alts

def render_page(site_name,page,locale,entry,alternate_urls,base_url):
    url=base_url+url_path(locale,entry['slug'])
    loc_lang=locale.split('-')[0]
    head = [
        '<!doctype html>',
        f'<html lang="{html.escape(locale,quote=True)}" dir="{text_direction(locale)}"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{html.escape(entry["title"])}</title>',
        f'<meta name="description" content="{html.escape(entry["description"],quote=True)}">',
        f'<link rel="canonical" href="{html.escape(url,quote=True)}">',
    ]
    if not page['index'] or not page['public']:
        head.append('<meta name="robots" content="noindex,nofollow">')
    else:
        head.append('<meta name="robots" content="index,follow">')
        if len(alternate_urls)>1:
            head.extend(f'<link rel="alternate" hreflang="{html.escape(code,quote=True)}" href="{html.escape(target,quote=True)}">' for code,target in sorted(alternate_urls.items()))
    # WebPage is a generic schema type. No fabricated authors, reviews, or rich result promises.
    graph={'@context':'https://schema.org','@type':'WebPage','url':url,'inLanguage':locale,'name':entry['title'],'description':entry['description']}
    head.append('<script type="application/ld+json">'+json.dumps(graph,ensure_ascii=False).replace('<','\\u003c')+'</script>')
    head += ['</head><body>', f'<main><h1>{html.escape(entry["title"])}</h1>',
             f'<p>{as_text(entry["body"])}</p>', f'<p><a href="/">{html.escape(site_name)}</a></p>', '</main></body></html>']
    return '\n'.join(head)+'\n'

def render_hub(spec,base):
    items=[]
    for page in spec['pages']:
        if not (page['public'] and page['index']):continue
        for locale,entry in sorted(page['locales'].items()):
            items.append(f'<li lang="{html.escape(locale,quote=True)}" dir="{text_direction(locale)}"><a href="{html.escape(url_path(locale,entry["slug"]),quote=True)}" hreflang="{html.escape(locale,quote=True)}">{html.escape(entry["title"])}</a></li>')
    name=html.escape(spec['site_name'])
    return '\n'.join(['<!doctype html>','<html lang="und"><head>','<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',f'<title>{name}</title>',
        f'<meta name="description" content="{name}: every public page, in every language it is written in.">',
        f'<link rel="canonical" href="{html.escape(base+"/",quote=True)}">','<meta name="robots" content="index,follow">',
        '</head><body><main>',f'<h1>{name}</h1>','<ul>',*items,'</ul>','</main></body></html>'])+'\n'

def build_sitemap(entries):
    root=ET.Element(f'{{{NS}}}urlset')
    for p in entries:
        node=ET.SubElement(root,f'{{{NS}}}url')
        # (x-default is listed like any other alternate; engines that don't use it ignore it)
        ET.SubElement(node,f'{{{NS}}}loc').text=p['url']
        if p.get('lastmod'):
            ET.SubElement(node,f'{{{NS}}}lastmod').text=p['lastmod']
        if len(p['alternates'])>1:
            for code,target in sorted(p['alternates'].items()):
                ET.SubElement(node,f'{{{XHTML}}}link',{'rel':'alternate','hreflang':code,'href':target})
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def selected_engines(spec):
    engines=load_engines()
    if spec['engines']==['all']: return engines
    selections=[]
    for i in spec['engines']:
        matches=[e for e in engines if e['id']==i]
        if not matches: raise SpecError(f'unknown engine: {i}')
        selections.extend(matches)
    return selections

def engine_report(engines):
    lines=['# engine-specific instructions','', 'a shared index or result provider does NOT imply identical SEO rules.',
           'a missing capability (null) means **unknown**, not unsupported.','',
           'indexing and rankings are not guaranteed by submissions or generated metadata.','']
    for e in engines:
        caps=e['capabilities']; status=e['verification']
        lines += [f'## {e["name"]} — {status}',
                  f'- type: {e["kind"]}; result sources: {", ".join(e.get("result_sources", [])) or "unconfirmed"}',
                  f'- XML sitemap: {caps.get("sitemap")}; IndexNow: {caps.get("indexnow")}; hreflang: {caps.get("hreflang")}',
                  f'- specific finding: {e.get("note") or "no individually verified instructions yet"}',
                  f'- sources: {", ".join(x["url"] for x in e.get("evidence", [])) or "research pending"}', '']
    return '\n'.join(lines)+'\n'

def market_coverage(spec,out):
    countries=load_countries()
    targets=spec.get('market_targets','all')
    chosen=[c for c in countries if targets=='all' or c['code'] in targets]
    rows=[]
    for c in chosen:
        languages={x['code'].split('_')[0].split('-')[0] for x in c.get('language_candidates',[])}
        for page in spec['pages']:
            if not page['public'] or not page['index']: continue
            local=set(page['locales'])
            specific=sorted(x for x in local if x.upper().endswith('-'+c['code'].upper()))
            shared=sorted(x for x in local if x.split('-')[0] in languages)
            status='country_locale' if specific else 'shared_language_only' if shared else 'unlocalized'
            rows.append({'country':c['name'],'code':c['code'],'page_id':page['id'],
                'status':status,'matched_locales':','.join(specific or shared),
                'note':'shared language alone does not verify local relevance or rankings' if status=='shared_language_only' else ''})
    with (out/'market-coverage.csv').open('w',newline='',encoding='utf-8') as file:
        w=csv.DictWriter(file,fieldnames=['country','code','page_id','status','matched_locales','note']);w.writeheader();w.writerows(rows)
    return {'targeted_markets':len(chosen),'country_locale':sum(r['status']=='country_locale' for r in rows),
        'shared_language_only':sum(r['status']=='shared_language_only' for r in rows),'unlocalized':sum(r['status']=='unlocalized' for r in rows)}

def compile_site(spec, destination):
    validate_spec(spec)
    base=spec['base_url'].rstrip('/')
    out=Path(destination)
    out.mkdir(parents=True,exist_ok=True)
    engines=selected_engines(spec)
    metas=[]
    for page in spec['pages']:
        if not page['public']:
            continue  # private data must never be emitted to a public static build
        alternates=page_alternates(spec,page,base)
        for locale,entry in page['locales'].items():
            path=url_path(locale,entry['slug'])
            # Write to a restricted output root; slug segments validated against traversal.
            target=(out / path.strip('/') / 'index.html').resolve()
            if not target.is_relative_to(out.resolve()): raise SpecError('unsafe path')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(render_page(spec['site_name'],page,locale,entry,alternates,base),encoding='utf-8')
            if page['public'] and page['index']:
                metas.append({'id':page['id'],'locale':locale,'url':base+path,'alternates':alternates,
                              'lastmod':page.get('lastmod')})
    # A crawlable home page: every generated page was linking to "/" but nothing was there, so pages were only
    # discoverable through the sitemap. The hub links each public, indexable page in every language.
    hub=render_hub(spec,base)
    (out/'index.html').write_text(hub,encoding='utf-8')
    metas.insert(0,{'id':'_home','locale':None,'url':base+'/','alternates':{},'lastmod':None})
    sitemaps=[]
    # Respect both URL count and a conservative 9 MB XML size limit.
    batches=[];batch=[]
    empty_size=len(build_sitemap([]))
    batch_size=empty_size
    for item in metas:
        item_size=len(build_sitemap([item]))-empty_size
        if item_size+empty_size>9_000_000:
            raise SpecError('one sitemap entry exceeds conservative size limit')
        if batch and (len(batch)>=10000 or batch_size+item_size>9_000_000):
            batches.append(batch)
            batch=[];batch_size=empty_size
        batch.append(item)
        batch_size+=item_size
    if batch:batches.append(batch)
    for i,part in enumerate(batches,1):
        name=f'sitemap-{i}.xml' if len(batches)>1 else 'sitemap.xml'
        (out/name).write_bytes(build_sitemap(part))
        sitemaps.append(name)
    if len(sitemaps)>1:
        root=ET.Element(f'{{{NS}}}sitemapindex')
        for name in sitemaps:
            sm=ET.SubElement(root,f'{{{NS}}}sitemap')
            ET.SubElement(sm,f'{{{NS}}}loc').text=base+'/'+name
        (out/'sitemap.xml').write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
    if not sitemaps:
        (out/'sitemap.xml').write_bytes(build_sitemap([]))
    (out/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+base+'/sitemap.xml\n',encoding='utf-8')
    (out/'engine-guide.md').write_text(engine_report(engines),encoding='utf-8')
    market=market_coverage(spec,out)
    (out/'manifest.json').write_text(json.dumps({
        'compiler':'usel-0.1.1','base_url':base,
        'rendered_pages':sum(len(p['locales']) for p in spec['pages'] if p['public']),
        'indexed_pages':len(metas),'home_page':True,'engines_selected':len(engines),
        'documented_profiles':len([e for e in engines if e['verification']=='documented']),
        'market_coverage':market,
        'unverified_profiles':[e['id'] for e in engines if e['verification']!='documented'],
        'note':'generated SEO hints do not guarantee inclusion, ranking, or submission'
    },ensure_ascii=False,indent=2),encoding='utf-8')
    # Engine research drives output: the IndexNow key file is only written when a selected engine is a documented
    # participant and the author supplied a key. Hosting it is what lets those engines accept the site's pings.
    participants=[e['id'] for e in engines if e['capabilities'].get('indexnow') is True]
    if spec.get('indexnow_key') and participants:
        (out/f"{spec['indexnow_key']}.txt").write_text(spec['indexnow_key'],encoding='utf-8')
    # Offline-ready payload only; NO network calls or automatic exposure.
    (out/'indexnow-plan.json').write_text(json.dumps({
        'supported_participants':[e['id'] for e in engines if e['capabilities'].get('indexnow') is True],
        'hosts_to_notify':'submissions are opt-in; see CLI submit-indexnow',
        'urlList':[p['url'] for p in metas]
    },ensure_ascii=False,indent=2),encoding='utf-8')
    return {'files':len(list(out.rglob('*'))),'indexed_pages':len(metas),
            'rendered_pages':sum(len(p['locales']) for p in spec['pages'] if p['public']),
            'documented_profiles':len([e for e in engines if e['verification']=='documented']),
            'engine_profiles':len(engines),'market_coverage':market,'location':str(out)}
