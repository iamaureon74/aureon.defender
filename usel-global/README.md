# usel — universal search engine language

**status: executable research-backed alpha, version 0.1.1 (2026-11-17).**  
**goal:** author international SEO once, generate accessible, machine-readable output, retain independent capability profiles for every discovered search engine, and continuously fill evidence gaps.

this is *working source code*, not a guarantee of rankings or a completed global audit. the sample `bosley.example` domain is reserved documentation text, not an owned or live domain.

## verified local functionality

- one YAML/JSON `.usel` file compiles to language-specific static HTML, canonical links, reciprocal `hreflang`, `WebPage` JSON-LD, robots.txt, XML sitemap(s), a global market-gap CSV, an engine-specific evidence guide and an IndexNow *plan*.
- private pages are omitted entirely from public output. public pages marked `index: false` get `noindex,nofollow` and are absent from the sitemap.
- output audit verifies sitemap references, XML parsing, page canonicalization, locale alternates, and private/noindex behavior within the scope of generated files.
- a local-only dark interface supports editing specifications, filtering engine and country profiles, and downloading compiled website files.
- the worldwide registry contains 249 ISO 3166-1 countries/territories and one additional jurisdiction (Kosovo XK), 50 search-related seed profiles, and 15 source-reviewed capability records. geography and profiles do **not** establish that all country-specific search engines have been discovered, or that all sources are current.
- 37 regression tests pass (27 original + 10 for the 0.1.1 fixes). run them again after changes.

## what changed in 0.1.1

a review found places where the compiler didn't yet do what the theory says. fixed:

- **engine research now changes the output, a little.** an optional `indexnow_key` writes the key file IndexNow needs, but only when a selected engine is a documented participant. google's hreflang support is recorded as documented, matching its own cited source (it was `null`).
- **right-to-left languages** (arabic, hebrew, persian, urdu and others) get `dir="rtl"`; before, they rendered backwards.
- **a real home page.** every page linked to `/` but nothing was there, so pages were only findable through the sitemap. the compiler now writes a hub that links every public, indexable page in every language.
- **`x-default`.** set `default_locale: en-US` (or any locale you publish) and every page tells engines which version to show people whose language you haven't covered.
- `inLanguage` keeps the full tag (`ko-KR`, not `ko`); slugs can't contain spaces or control characters; windows line endings no longer leak into pages.

what it still can't do is unchanged — see the end of this file.

## start the app

requires Python 3.11+.

```bash
cd usel-global
python -m pip install -r requirements.txt
python -m usel serve --host 127.0.0.1 --port 8090
```

open `http://127.0.0.1:8090` on your computer. **do not expose the development server to the public internet:** it has no production authentication, persistent rate limiter, request isolation, or cloud deployment security review.

## compile source directly

```bash
python -m usel compile examples/bosley.usel.yaml --output build
python -m usel audit build
python -m usel engines
python -m usel countries
python -m usel coverage --output worldwide-coverage.csv
python -m pytest -q
```

output is deployable static content. the compiler does not touch an existing bosley repository, publish a website, register search-engine accounts, or submit URLs without a separate explicit command. connect it to Bosley's actual public-post/profile backend when that repository is available. a production integration should generate page content from your database and invoke compilation or incremental page regeneration as new public content becomes available.

## language example

```yaml
usel: 1
site_name: bosley
base_url: https://your-verified-bosley-domain.example
market_targets: [US, KR, CZ]
default_locale: en-US          # optional: x-default for everyone else
engines: [all]
pages:
  - id: discussion-123
    public: true
    index: true
    lastmod: '2026-11-14'
    locales:
      en-US:
        slug: discussions/123
        title: 'a public discussion'
        description: 'a description matching the actual discussion'
        body: 'the real public discussion text, not keyword filler'
      ko-KR:
        slug: discussions/123
        title: '공개 토론'
        description: '공개 토론에 대한 설명입니다.'
        body: '실제 공개 토론 내용입니다.'
```

replace the placeholder domain, translations, content, and URL paths. only publish text your platform is authorized to expose; avoid generating indexed copies of personal messages or deleted content.

## understand the results

- **engine profile `verification: documented`:** one or more named capabilities have a primary/source-provider document. this does not validate every optimization technique or ranking factor for that engine.
- **`research_needed`:** engine/service is a research lead, possibly currently inactive; no independently verified SEO rules are asserted.
- **capability `null`:** unknown, not unsupported.
- **result sources:** many metasearch sites use other indexes, but their result UI, local content, filters, and ranking decisions may still differ. *never* duplicate every parent engine rule automatically.
- **`market-coverage.csv`:** `country_locale` means a specific locale was authored; `shared_language_only` means a source language exists without country-specific localization; `unlocalized` means a gap. none of these means ranking or traffic was confirmed.
- **static output audit:** only checks generated files, not Google/Naver/Baidu indexing or conversion outcomes.

## IndexNow, opt-in only

`build/indexnow-plan.json` is **offline**. no network submission occurs during compile.

```bash
# inspect planned URLs without sending a request
python -m usel submit-indexnow build/indexnow-plan.json --key YOUR_REAL_KEY --host https://your-domain.example

# only after hosting https://your-domain.example/YOUR_REAL_KEY.txt
python -m usel submit-indexnow build/indexnow-plan.json --key YOUR_REAL_KEY --host https://your-domain.example --execute
```

IndexNow can notify participating engines of changes but does not guarantee indexing. the host and every URL must share the exact HTTPS hostname. never put a production key in a public example. to research today's partners:

```bash
python -m usel refresh-indexnow --output indexnow-live.json
```

this explicitly invokes a network request to the official public partner-list endpoint; refreshed participants are *not* silently treated as fully verified SEO adapters.

## where expansion happens

- `data/engines.json` — versioned engine research entries, source URL, source date, capabilities and evidence state.
- `data/countries.json` — ISO/jurisdiction baseline and candidate languages from CLDR, not market statistics.
- `data/worldwide_coverage.csv` — 250 pending country-by-country discovery assignments.
- `usel/registry.py`, `usel/discovery.py` — engine registration and IndexNow participants refresh.
- `usel/compiler.py` — compiler + canonical/hreflang/sitemaps + market gap report.
- `usel/auditor.py` — generated-output static verification.
- `tests/` — tests.
- `docs/EVIDENCE_AND_COVERAGE.md` — official sources, methodology, gaps.

### what this alpha does NOT yet do

no complete enumeration of all active global engines; no independent engine crawls or live webmaster-console authentication; no automatic translation or keyword-demand research; no analytics for rankings/traffic; no real-time bosley account/post integration; no AI-answer-engine optimization guarantees; no end-to-end actual crawler tests; no cloud deployment, authentication, or continuous discovery automation. public ranking algorithms are partly proprietary and change frequently.

**research principle:** if an engine's guidance is missing, keep the field unknown and record its research status. never invent a universal trick to rank everywhere.
