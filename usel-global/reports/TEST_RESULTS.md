# test report — usel 0.1.1

executed 2026-11-17: `python -m pytest -q` → **37 passed** (27 original + 10 covering the 0.1.1 fixes: rtl direction,
home hub links, x-default + full language tag, unknown default locale rejected, whitespace slugs rejected, crlf bodies,
indexnow key file only for participants, google hreflang matching its evidence). the demo build was regenerated and its
static audit passed with no errors.

---

# test report — usel 0.1.0

executed 2026-11-14 in this container runtime.

## passed

- `python -m pytest -q`: **27 tests passed**.
- registry integrity: 250 unique jurisdictions, 50 seed service/crawler records, 15 documentation-reviewed capability profiles.
- YAML parser validation and unsafe URL/slug rejection.
- eight generated example localized public pages with valid reciprocal language alternatives.
- XML sitemap, robots and canonical matching; country coverage report created for 250 jurisdictions.
- private content excluded from all static outputs, including search manifests, and public noindex pages excluded from sitemap.
- HTML/script input escaped in public output.
- engine selection rejects unknown providers; no invented capabilities.
- IndexNow CLI dry run does not contact the network; host mismatch rejected.
- FastAPI TestClient: `/api/summary` succeeds, `/api/compile` returns an actual ZIP, invalid source is rejected.
- browser interface: JavaScript syntax confirmed with `node --check`, desktop visual rendering, country/engine counts, engine filter, YAML editor and mobile overflow checks pass using static API fixtures (screenshots in project root).

## not tested / no claim of success

- browser direct access to the local HTTP server: Chromium navigation blocked by the container administrator. the HTTP API was independently exercised by Python TestClient and curl; UI render was exercised in Chromium with its API fixtures.
- live search-engine indexing/ranking, webmaster login, live IndexNow submissions, SEO performance or actual Bosley domain integration.
- worldwide verification of all search engines, languages and legal/regional constraints.
- high-scale incremental indexing, production cloud security, adversarial network-load tests.

passing static file tests does not establish search ranking or production security.
