import json, pycountry
from babel.core import get_global
from pathlib import Path
ROOT=Path(__file__).parent
DATE='2026-11-14'
# Maps a seed service to its primary-source SEO documentation. NO assumed support inheritance.
DOCS={
'google':('https://developers.google.com/search/docs/specialty/international/localized-versions','hreflang self and reciprocal alternates, international URLs; sitemap and crawlability.',True,None),
'bing':('https://www.bing.com/webmasters/help/?topicid=62f2860b','IndexNow strongly recommended; sitemaps and webmaster tools.',True,True),
'yandex':('https://yandex.com/support/webmaster/en/yandex-indexing/site-indexing','XML sitemaps aid discovery; regionalized experiences should be crawlable independent of bot IP.',True,True),
'naver':('https://searchadvisor.naver.com/guide/indexnow-about','Naver supports IndexNow; its Search Advisor also documents robots.txt and sitemaps.',True,True),
'seznam':('https://www.indexnow.org/searchengines.json','Seznam is a documented IndexNow participant; also has own URL addition and verification forms.',None,True),
'baidu':('https://ziyuan.baidu.com/college/articleinfo?id=3076','Baidu resource platform describes API, manual, and sitemap submission; verification/quotas may apply.',True,None),
'sogou':('https://zhanzhang.sogou.com/index.php/help/sitemap','Sogou supports sitemaps but its submission access may be invitation-only.',True,None),
'so360':('https://bbs.360.cn/thread-15979727-1-1.html','360 official community recommends verified sitemap submission and URL submission, not a generic API.',True,None),
'brave':('https://search.brave.com/help/brave-search-crawler','Brave crawler is independent and uses eligibility based on Googlebot crawlability; no invented submissions.',None,None),
'mojeek':('https://community.mojeek.com/t/crawling-and-webmaster/215','Mojeek representative said in 2022 that sitemaps were not used for discovery; current support remains UNVERIFIED.',None,None),
'duckduckgo':('https://safe.duckduckgo.com/duckduckgo-help-pages/results/sources','Traditional web links largely sourced from Bing, with other own and third-party sources; do not equate ranking.',None,None),
'ecosia':('https://support.ecosia.org/article/579-search-results-providers','Search results can come from Bing, Google, or EUSP depending on region/device/permissions.',None,None),
'yep':('https://www.indexnow.org/searchengines.json','Yep is a documented IndexNow participant. Other SEO rules pending.',None,True),
'internetarchive':('https://www.indexnow.org/searchengines.json','Internet Archive crawler receives IndexNow notifications; not the same as a general search engine.',None,True),
'amazonbot':('https://www.indexnow.org/searchengines.json','Amazonbot is an IndexNow participant crawler, not a public general search engine.',None,True),
}
SEEDS=[
# id, name, kind, home, country_origin, result providers (only when primary-source confirms)
('google','Google Search','general','https://www.google.com','US',[]),
('bing','Bing','general','https://www.bing.com','US',[]),
('yandex','Yandex','general','https://yandex.com','RU',[]),
('naver','Naver','general','https://search.naver.com','KR',[]),
('seznam','Seznam','general','https://search.seznam.cz','CZ',[]),
('baidu','Baidu','general','https://www.baidu.com','CN',[]),
('sogou','Sogou','general','https://www.sogou.com','CN',[]),
('so360','360 Search (so.com)','general','https://www.so.com','CN',[]),
('brave','Brave Search','general','https://search.brave.com','US',[]),
('mojeek','Mojeek','general','https://www.mojeek.com','GB',[]),
('duckduckgo','DuckDuckGo','metasearch','https://duckduckgo.com','US',['bing','duckduckbot','other sources']),
('ecosia','Ecosia','metasearch','https://www.ecosia.org','DE',['bing','google','eusp']),
('yep','Yep','general','https://yep.com','SG',[]),
('internetarchive','Internet Archive crawler','crawler','https://archive.org','US',[]),
('amazonbot','Amazonbot crawler','crawler','https://www.amazon.com','US',[]),
('coccoc','Cốc Cốc','general','https://coccoc.com/search','VN',[]),
('yahoo','Yahoo Search','metasearch','https://search.yahoo.com','US',[]),
('yahoojp','Yahoo! Japan Search','metasearch','https://search.yahoo.co.jp','JP',[]),
('qwant','Qwant','metasearch','https://www.qwant.com','FR',[]),
('startpage','Startpage','metasearch','https://www.startpage.com','NL',[]),
('kagi','Kagi','metasearch','https://kagi.com','US',[]),
('swisscows','Swisscows','metasearch','https://swisscows.com','CH',[]),
('metager','MetaGer','metasearch','https://metager.org','DE',[]),
('lilo','Lilo','metasearch','https://www.lilo.org','FR',[]),
('presearch','Presearch','metasearch','https://presearch.com','CA',[]),
('you','You.com','answer_engine','https://you.com','US',[]),
('perplexity','Perplexity','answer_engine','https://www.perplexity.ai','US',[]),
('ask','Ask.com','metasearch','https://www.ask.com','US',[]),
('aol','AOL Search','metasearch','https://search.aol.com','US',[]),
('lycos','Lycos','metasearch','https://www.lycos.com','US',[]),
('dogpile','Dogpile','metasearch','https://www.dogpile.com','US',[]),
('webcrawler','WebCrawler','metasearch','https://www.webcrawler.com','US',[]),
('excite','Excite','metasearch','https://www.excite.com','US',[]),
('daum','Daum Search','general','https://search.daum.net','KR',[]),
('nate','Nate Search','general','https://search.nate.com','KR',[]),
('zum','ZUM Search','general','https://search.zum.com','KR',[]),
('goo','goo Japan','metasearch','https://search.goo.ne.jp','JP',[]),
('petal','Petal Search','general','https://petalsearch.com','CN',[]),
('rambler','Rambler','metasearch','https://www.rambler.ru','RU',[]),
('mailru','Mail.ru Search','metasearch','https://go.mail.ru','RU',[]),
('yaani','Yaani','general','https://www.yaani.com.tr','TR',[]),
('marginalia','Marginalia Search','independent','https://search.marginalia.nu','SE',[]),
('wiby','Wiby','independent','https://wiby.me','US',[]),
('yacy','YaCy','self_hosted','https://yacy.net','DE',[]),
('searxng','SearXNG','self_hosted','https://docs.searxng.org','DE',[]),
('eusp','European Search Perspective','index_provider','https://www.eusp.org','FR',[]),
('wikipedia','Wikipedia search','vertical','https://www.wikipedia.org','US',[]),
('pubmed','PubMed','vertical','https://pubmed.ncbi.nlm.nih.gov','US',[]),
('wolframalpha','WolframAlpha','computational','https://www.wolframalpha.com','US',[]),
('internetarchive_search','Internet Archive Search','vertical','https://archive.org/search','US',[]),
]
engines=[]
for id_,name,kind,url,country,sources in SEEDS:
    evidence=[]
    info=DOCS.get(id_)
    note='not yet source-verified; investigate own crawler, discovery, index provider, local product features, regional requirements'
    caps={'sitemap':None,'indexnow':None,'direct_submit':None,'hreflang':None}
    if info:
        url_source,note,sitemap,indexnow=info
        evidence=[{'url':url_source,'checked_on':DATE,'scope':'specific publicly documented capability'}]
        caps.update({'sitemap':sitemap,'indexnow':indexnow})
    engines.append({'lifecycle':'reported_discontinued' if id_ in ('goo','ask','excite') else 'unverified', 'id':id_,'name':name,'kind':kind,'site':url,'origin_country':country,
        'market_countries_verified':[], 'result_sources':sources,'verification':'documented' if info else 'research_needed',
        'capabilities':caps,'note':note,'evidence':evidence,
        'discovered_on':DATE, 'last_rule_check':DATE if info else None})
(ROOT/'data/engines.json').write_text(json.dumps({'version':'0.1.0','as_of':DATE,
    'coverage_note':'seeds for research, not a claim of total global search-engine coverage; each candidate needs independent verification',
    'engines':engines},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lang_coverage=get_global('territory_languages')
countries=[]
for c in pycountry.countries:
    c2=c.alpha_2
    raw=lang_coverage.get(c2,{})
    possible=[{'code':lang,'estimated_population_share_percent':round(v.get('population_percent',0),2),'official_status':v.get('official_status')}
        for lang,v in raw.items() if v.get('official_status') or v.get('population_percent',0)>=5]
    possible.sort(key=lambda x: (-x['estimated_population_share_percent'],x['code']))
    countries.append({'code':c2,'alpha3':c.alpha_3,'name':c.name,'registry':'ISO 3166-1',
        'language_candidates':possible, 'engines_verified':[],
        'search_engine_discovery_status':'not_audited',
        'note':'language data is a CLDR starting point, not an official SEO market assessment'})
countries.append({'code':'XK','alpha3':None,'name':'Kosovo','registry':'additional jurisdiction (not ISO 3166-1 alpha-2)',
    'language_candidates':[{'code':'sq','estimated_population_share_percent':None,'official_status':'official'},
                             {'code':'sr','estimated_population_share_percent':None,'official_status':'official'}],
    'engines_verified':[],'search_engine_discovery_status':'not_audited'})
countries.sort(key=lambda x:x['code'])
(ROOT/'data/countries.json').write_text(json.dumps({'version':'0.1.0','as_of':DATE,'source':'pycountry ISO-3166-1 snapshot, Babel/CLDR territory language candidates, plus Kosovo XK jurisdiction',
    'note':'all countries and territories are registry records, NOT verified as having individual domestic search engines',
    'countries':countries},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'data/indexnow_participants_snapshot.json').write_text(json.dumps({'checked_on':DATE,
    'source':'https://www.indexnow.org/searchengines.json',
    'participants':{'bing':'https://www.bing.com/indexnow/meta.json','yandex':'https://www.yandex.com/indexnow/meta.json',
    'seznam':'https://search.seznam.cz/indexnow/meta.json','naver':'https://searchadvisor.naver.com/indexnow/meta.json',
    'yep':'https://indexnow.yep.com/indexnow/meta.json','internetarchive':'https://web-static.archive.org/indexnow/meta.json',
    'amazonbot':'https://indexnow.amazonbot.amazon/indexnow/meta.json'},
    'note':'participant status changes over time; use refresh-indexnow for current list'},indent=2)+'\n')
print('created',len(countries),'countries and jurisdictions and',len(engines),'engine/service profiles,',len(DOCS),'documented profiles')
