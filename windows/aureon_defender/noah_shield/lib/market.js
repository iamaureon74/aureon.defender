// Market: the wider web for a product, beyond the handful of big stores in
// lib/shopping.js. Three things live here.
//
//   1. Money: exchange rates (two public, keyless sources, a built-in table
//      as the last resort, cached for a day) and conversion, so a price in
//      yen or złoty is shown in the currency the person is shopping in.
//   2. Finders: general web search (DuckDuckGo, Bing, Brave, Mojeek — plain
//      HTML pages fetched without cookies) with sponsored results dropped,
//      the well-known megastores set aside, and prices read out of snippets;
//      the same searches again in other countries' regions, so a cheaper
//      foreign listing is found and converted.
//   3. Coupons: codes found on the public web for a store, so the checkout
//      has something to try even when nothing was collected yet.
//
// Everything is a plain fetch of a public page with no cookies and nothing
// about the person in it but the product's name.
"use strict";
(() => {

const Shield = (globalThis.Shield = globalThis.Shield || {});
const TIMEOUT_MS = 9000;

// ---- money ----------------------------------------------------------------------

// Approximate rates against the US dollar, used only when both online
// sources fail. Marked as approximate in the card when used.
const FALLBACK_RATES = {
  at: "2026-10-01", base: "USD",
  rates: { USD: 1, EUR: 0.92, GBP: 0.78, JPY: 149, CNY: 7.2, CAD: 1.37, AUD: 1.52, NZD: 1.66, CHF: 0.88, SEK: 10.6, NOK: 10.8, DKK: 6.9, PLN: 3.95, CZK: 23.2, HUF: 365, RON: 4.6, BGN: 1.8, INR: 84, KRW: 1360, TWD: 32, HKD: 7.8, SGD: 1.34, MYR: 4.4, THB: 34, PHP: 57, IDR: 15800, VND: 25000, TRY: 34, RUB: 92, UAH: 41, BRL: 5.5, MXN: 19, ARS: 1000, CLP: 950, COP: 4200, PEN: 3.75, ZAR: 18, EGP: 48, AED: 3.67, SAR: 3.75, ILS: 3.7, NGN: 1600, KES: 129, PKR: 278, BDT: 120, LKR: 300, QAR: 3.64, KWD: 0.31, ISK: 138, HRK: 6.9 },
};

const SYMBOLS = [
  ["US$", "USD"], ["U$S", "USD"], ["CA$", "CAD"], ["C$", "CAD"], ["AU$", "AUD"], ["A$", "AUD"], ["NZ$", "NZD"], ["HK$", "HKD"], ["S$", "SGD"], ["R$", "BRL"], ["MX$", "MXN"], ["NT$", "TWD"],
  ["€", "EUR"], ["£", "GBP"], ["¥", "JPY"], ["￥", "JPY"], ["元", "CNY"], ["₹", "INR"], ["₩", "KRW"], ["₺", "TRY"], ["₽", "RUB"], ["₴", "UAH"], ["₪", "ILS"], ["₦", "NGN"], ["₱", "PHP"], ["₫", "VND"], ["฿", "THB"], ["zł", "PLN"], ["Kč", "CZK"], ["Ft", "HUF"], ["lei", "RON"], ["лв", "BGN"], ["kr", "SEK"], ["CHF", "CHF"], ["RM", "MYR"], ["Rp", "IDR"], ["Rs.", "INR"], ["Rs", "INR"], ["₨", "PKR"], ["৳", "BDT"], ["AED", "AED"], ["SAR", "SAR"], ["R", "ZAR"], ["$", "USD"],
];
const CODES = /\b(USD|EUR|GBP|JPY|CNY|CAD|AUD|NZD|CHF|SEK|NOK|DKK|PLN|CZK|HUF|RON|BGN|INR|KRW|TWD|HKD|SGD|MYR|THB|PHP|IDR|VND|TRY|RUB|UAH|BRL|MXN|ARS|CLP|COP|PEN|ZAR|EGP|AED|SAR|ILS|NGN|KES|PKR|BDT|LKR|QAR|KWD|ISK)\b/;
// Ambiguous symbols decided by where the page lives.
const TLD_CURRENCY = { uk: "GBP", de: "EUR", fr: "EUR", it: "EUR", es: "EUR", nl: "EUR", be: "EUR", at: "EUR", ie: "EUR", pt: "EUR", fi: "EUR", gr: "EUR", sk: "EUR", si: "EUR", lt: "EUR", lv: "EUR", ee: "EUR", jp: "JPY", cn: "CNY", kr: "KRW", tw: "TWD", hk: "HKD", sg: "SGD", my: "MYR", th: "THB", ph: "PHP", id: "IDR", vn: "VND", in: "INR", ca: "CAD", au: "AUD", nz: "NZD", ch: "CHF", se: "SEK", no: "NOK", dk: "DKK", pl: "PLN", cz: "CZK", hu: "HUF", ro: "RON", bg: "BGN", tr: "TRY", ru: "RUB", ua: "UAH", br: "BRL", mx: "MXN", ar: "ARS", cl: "CLP", co: "COP", pe: "PEN", za: "ZAR", eg: "EGP", ae: "AED", sa: "SAR", il: "ILS", ng: "NGN", ke: "KES", pk: "PKR", bd: "BDT", lk: "LKR", qa: "QAR", kw: "KWD", is: "ISK", us: "USD" };

Shield.currencyForHost = function currencyForHost(host) {
  const parts = String(host || "").toLowerCase().split(".");
  if (parts.length < 2) return null;
  const last = parts[parts.length - 1];
  const second = parts[parts.length - 2];
  // amazon.co.uk, amazon.com.au, shop.co.jp: the country sits after a generic label.
  if (parts.length >= 3 && /^(com|co|net|org|ac|gov|edu|or|ne)$/.test(second)) return TLD_CURRENCY[last] || null;
  if (/^(com|net|org|io|info|biz|shop|store|app|dev)$/.test(last)) return null;
  return TLD_CURRENCY[last] || null;
};

// "1.299,00 €", "¥12,800", "USD 49.99", "49,99 zł": the amount and the currency.
// The amount is the number that sits against a currency mark, never the first
// number in the text (a model number like WH-1000XM5 comes before the price).
const NUMBER = "(\\d{1,3}(?:[.,\\s]\\d{3})+(?:[.,]\\d{1,2})?|\\d+(?:[.,]\\d{1,2})?)";
const SYMBOL_ALTERNATION = SYMBOLS.map(([symbol]) => symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((left, right) => right.length - left.length).join("|");
const CODE_ALTERNATION = CODES.source.replace(/^\\b\(|\)\\b$/g, "");
const MONEY_BEFORE = new RegExp("(" + CODE_ALTERNATION + "|" + SYMBOL_ALTERNATION + ")\\s?" + NUMBER + "(?![\\d])");
const MONEY_AFTER = new RegExp(NUMBER + "\\s?(" + CODE_ALTERNATION + "|" + SYMBOL_ALTERNATION + ")(?![A-Za-z])");

function currencyOfMark(mark, hostCurrency) {
  const upper = mark.toUpperCase();
  if (CODES.test(upper) && mark.length === 3 && /^[A-Z]{3}$/i.test(mark)) return upper;
  for (const [symbol, iso] of SYMBOLS) {
    if (symbol !== mark) continue;
    if (symbol === "$" && hostCurrency && /^(CAD|AUD|NZD|HKD|SGD|MXN|ARS|CLP|COP|TWD|BRL)$/.test(hostCurrency)) return hostCurrency;
    if (symbol === "kr" && hostCurrency && /^(SEK|NOK|DKK|ISK)$/.test(hostCurrency)) return hostCurrency;
    if ((symbol === "¥" || symbol === "￥") && hostCurrency === "CNY") return "CNY";
    if (symbol === "R" && hostCurrency !== "ZAR") return null;
    return iso;
  }
  return null;
}

Shield.readMoney = function readMoney(text, host) {
  const sample = String(text || "").replace(/(\d)\s(?=\d{3}\b)/g, "$1");
  const hostCurrency = Shield.currencyForHost(host);
  const candidates = [];
  const before = MONEY_BEFORE.exec(sample);
  if (before) candidates.push({ index: before.index, mark: before[1], amount: before[2] });
  const after = MONEY_AFTER.exec(sample);
  if (after) candidates.push({ index: after.index, mark: after[2], amount: after[1] });
  candidates.sort((left, right) => left.index - right.index);
  for (const candidate of candidates) {
    const currency = currencyOfMark(candidate.mark, hostCurrency);
    const price = Shield.parsePrice(candidate.amount);
    if (currency && price) return { price, currency };
  }
  return null;
};

let ratesPromise = null;
Shield.rates = async function rates() {
  if (ratesPromise) return ratesPromise;
  ratesPromise = (async () => {
    const stored = await Shield.api.storage.local.get("fxRates");
    const cached = stored.fxRates;
    if (cached && Date.now() - cached.fetchedAt < 24 * 3600000) return cached;
    const sources = [
      async () => {
        const data = await fetchJson("https://open.er-api.com/v6/latest/USD");
        if (data && data.result === "ok" && data.rates) return { base: "USD", rates: data.rates, at: data.time_last_update_utc || "", source: "open.er-api.com" };
        return null;
      },
      async () => {
        const data = await fetchJson("https://api.frankfurter.app/latest?from=USD");
        if (data && data.rates) return { base: "USD", rates: { USD: 1, ...data.rates }, at: data.date || "", source: "frankfurter.app (ECB)" };
        return null;
      },
    ];
    for (const source of sources) {
      try {
        const result = await source();
        if (result) {
          const entry = { ...result, fetchedAt: Date.now(), approximate: false };
          await Shield.api.storage.local.set({ fxRates: entry });
          return entry;
        }
      } catch { /* next source */ }
    }
    if (cached) return cached;
    return { ...FALLBACK_RATES, fetchedAt: 0, approximate: true, source: "built-in table" };
  })();
  // A real table is reused for a minute; the built-in fallback is retried on the next ask.
  ratesPromise.then((table) => { if (table.approximate) ratesPromise = null; else setTimeout(() => { ratesPromise = null; }, 60000); }, () => { ratesPromise = null; });
  return ratesPromise;
};

Shield.convert = function convert(amount, from, to, table) {
  from = String(from || "USD").toUpperCase();
  to = String(to || "USD").toUpperCase();
  if (from === to) return amount;
  const rates = table && table.rates;
  if (!rates || !rates[from] || !rates[to]) return null;
  return (amount / rates[from]) * rates[to];
};

async function fetchJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { credentials: "omit", signal: controller.signal, headers: { accept: "application/json" } });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function fetchText(url, language) {
  if (!/^https?:\/\//i.test(String(url)) || Shield.isLocalHost(Shield.hostOf(url))) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      credentials: "omit",
      redirect: "follow",
      signal: controller.signal,
      headers: { accept: "text/html,application/xhtml+xml", "accept-language": language || "en" },
    });
    if (!response.ok) return null;
    const text = await response.text();
    return text.length > 400 ? text : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
Shield.fetchPublicText = fetchText;

function decodeEntities(text) {
  return String(text)
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'").replace(/&nbsp;/g, " ").replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)));
}
function stripTags(html) {
  return decodeEntities(String(html).replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}
Shield.stripTags = stripTags;

// ---- who is "well known" --------------------------------------------------------------
// The megastores and marketplaces everyone already checks. They are still
// searched (lib/shopping.js), but a result from one of them is never called
// an "independent" find.
const WELL_KNOWN = [
  "amazon.", "ebay.", "walmart.", "bestbuy.", "target.com", "costco.", "newegg.", "aliexpress.", "alibaba.", "temu.", "shein.", "wish.com", "etsy.com", "homedepot.", "lowes.", "wayfair.", "ikea.", "overstock.", "bhphotovideo.", "adorama.", "microcenter.", "staples.", "officedepot.", "kohls.", "macys.", "nordstrom.", "sears.", "jcpenney.", "samsclub.", "bjs.", "gamestop.", "apple.com", "samsung.com", "microsoft.com", "google.com", "dell.", "hp.com", "lenovo.", "nike.com", "adidas.", "zalando.", "otto.", "mediamarkt.", "saturn.", "fnac.", "darty.", "cdiscount.", "rakuten.", "bol.com", "coolblue.", "argos.", "currys.", "johnlewis.", "tesco.", "asda.", "sainsburys.", "very.co.uk", "ao.com", "elgiganten.", "elkjop.", "komplett.", "mercadolibre.", "mercadolivre.", "magazineluiza.", "americanas.", "casasbahia.", "flipkart.", "snapdeal.", "myntra.", "jd.com", "taobao.", "tmall.", "pinduoduo.", "suning.", "coupang.", "gmarket.", "11st.", "yodobashi.", "biccamera.", "kakaku.", "lazada.", "shopee.", "tokopedia.", "bukalapak.", "noon.com", "jumia.", "takealot.", "kogan.", "jbhifi.", "harveynorman.", "bunnings.", "thegoodguys.", "catch.com.au", "trademe.", "canadiantire.", "staples.ca", "bestbuy.ca", "ozon.", "wildberries.", "dns-shop.", "mvideo.", "allegro.", "emag.", "alza.", "mall.", "ceneo.", "idealo.", "geizhals.", "pricerunner.", "pricespy.", "google.", "bing.", "yahoo.", "facebook.", "instagram.", "pinterest.", "reddit.", "youtube.", "tiktok.", "wikipedia.", "shopping.",
];
Shield.isWellKnown = function isWellKnown(host) {
  const name = String(host || "").toLowerCase().replace(/^www\./, "");
  return WELL_KNOWN.some((entry) => name.includes(entry));
};

// Pages that are not stores at all: reviews, forums, the press, coupon mills.
const NOT_STORES = /(^|\.)(reddit|quora|wikipedia|youtube|facebook|twitter|x|instagram|tiktok|pinterest|medium|forbes|nytimes|theguardian|cnet|techradar|tomsguide|wirecutter|rtings|pcmag|consumerreports|trustpilot|sitejabber|yelp|glassdoor|linkedin|github|stackoverflow)\.(com|org|net|co\.uk|io)$/i;

// ---- finders --------------------------------------------------------------------------

// Regions for the foreign look: search engine region code, language, and
// what a price there is likely in.
const REGIONS = [
  { id: "us", kl: "us-en", cc: "US", lang: "en-US", currency: "USD", name: "United States" },
  { id: "uk", kl: "uk-en", cc: "GB", lang: "en-GB", currency: "GBP", name: "United Kingdom" },
  { id: "de", kl: "de-de", cc: "DE", lang: "de-DE", currency: "EUR", name: "Germany" },
  { id: "fr", kl: "fr-fr", cc: "FR", lang: "fr-FR", currency: "EUR", name: "France" },
  { id: "jp", kl: "jp-jp", cc: "JP", lang: "ja-JP", currency: "JPY", name: "Japan" },
  { id: "ca", kl: "ca-en", cc: "CA", lang: "en-CA", currency: "CAD", name: "Canada" },
  { id: "au", kl: "au-en", cc: "AU", lang: "en-AU", currency: "AUD", name: "Australia" },
  { id: "in", kl: "in-en", cc: "IN", lang: "en-IN", currency: "INR", name: "India" },
  { id: "cn", kl: "cn-zh", cc: "CN", lang: "zh-CN", currency: "CNY", name: "China" },
  { id: "kr", kl: "kr-kr", cc: "KR", lang: "ko-KR", currency: "KRW", name: "South Korea" },
  { id: "br", kl: "br-pt", cc: "BR", lang: "pt-BR", currency: "BRL", name: "Brazil" },
  { id: "mx", kl: "mx-es", cc: "MX", lang: "es-MX", currency: "MXN", name: "Mexico" },
  { id: "es", kl: "es-es", cc: "ES", lang: "es-ES", currency: "EUR", name: "Spain" },
  { id: "it", kl: "it-it", cc: "IT", lang: "it-IT", currency: "EUR", name: "Italy" },
  { id: "nl", kl: "nl-nl", cc: "NL", lang: "nl-NL", currency: "EUR", name: "Netherlands" },
  { id: "pl", kl: "pl-pl", cc: "PL", lang: "pl-PL", currency: "PLN", name: "Poland" },
  { id: "se", kl: "se-sv", cc: "SE", lang: "sv-SE", currency: "SEK", name: "Sweden" },
  { id: "tr", kl: "tr-tr", cc: "TR", lang: "tr-TR", currency: "TRY", name: "Turkey" },
  { id: "sg", kl: "sg-en", cc: "SG", lang: "en-SG", currency: "SGD", name: "Singapore" },
  { id: "za", kl: "za-en", cc: "ZA", lang: "en-ZA", currency: "ZAR", name: "South Africa" },
  { id: "ae", kl: "xa-ar", cc: "AE", lang: "ar-AE", currency: "AED", name: "United Arab Emirates" },
];
Shield.REGIONS = REGIONS;
const regionFor = (currency) => REGIONS.find((region) => region.currency === currency) || REGIONS[0];

// Each engine: a search URL for a query and region, and a parser that returns
// { url, title, snippet, sponsored } for every result on the page.
const ENGINES = [
  {
    id: "duckduckgo",
    url: (query, region) => `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}&kl=${region.kl}`,
    parse(html) {
      const results = [];
      // A lookahead split keeps each result's own class attribute in its block.
      for (const block of html.split(/<div(?=[^>]*class="[^"]*\bresult\b)/).slice(1, 30)) {
        const sponsored = /class="[^"]*(?:result--ad|badge--ad)|y\.js|ad_provider/i.test(block.slice(0, 600));
        const link = /class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(block);
        if (!link) continue;
        let url = decodeEntities(link[1]);
        const wrapped = /[?&]uddg=([^&]+)/.exec(url);
        if (wrapped) { try { url = decodeURIComponent(wrapped[1]); } catch { /* keep */ } }
        if (url.startsWith("//")) url = "https:" + url;
        const snippet = /class="result__snippet"[^>]*>([\s\S]*?)<\/a>/.exec(block);
        results.push({ url, title: stripTags(link[2]), snippet: snippet ? stripTags(snippet[1]) : "", sponsored });
      }
      return results;
    },
  },
  {
    id: "bing",
    url: (query, region) => `https://www.bing.com/search?q=${encodeURIComponent(query)}&cc=${region.cc}&setlang=${region.lang.split("-")[0]}`,
    parse(html) {
      const results = [];
      for (const block of html.split(/<li class="b_(?:algo|ad)/).slice(1, 30)) {
        const sponsored = block.startsWith('"') || /b_ad\b/.test(block.slice(0, 40)) || /<li class="b_ad/.test(block.slice(0, 20));
        const link = /<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(block);
        if (!link) continue;
        const snippet = /<p[^>]*>([\s\S]*?)<\/p>/.exec(block);
        results.push({ url: decodeEntities(link[1]), title: stripTags(link[2]), snippet: snippet ? stripTags(snippet[1]) : "", sponsored: sponsored && !/b_algo/.test(block.slice(0, 20)) });
      }
      return results;
    },
  },
  {
    id: "brave",
    url: (query, region) => `https://search.brave.com/search?q=${encodeURIComponent(query)}&country=${region.cc.toLowerCase()}&source=web`,
    parse(html) {
      const results = [];
      for (const block of html.split(/<div[^>]+class="snippet[^"]*"/).slice(1, 30)) {
        const sponsored = /data-type="ad"|class="ad\b|sponsored/i.test(block.slice(0, 400));
        const link = /<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(block);
        if (!link) continue;
        const title = /class="[^"]*title[^"]*"[^>]*>([\s\S]*?)<\//.exec(block);
        const snippet = /class="[^"]*(?:snippet-description|snippet-content|description)[^"]*"[^>]*>([\s\S]*?)<\/(?:div|p|span)>/.exec(block);
        results.push({ url: decodeEntities(link[1]), title: stripTags(title ? title[1] : link[2]), snippet: snippet ? stripTags(snippet[1]) : "", sponsored });
      }
      return results;
    },
  },
  {
    id: "mojeek",
    url: (query, region) => `https://www.mojeek.com/search?q=${encodeURIComponent(query)}&reg=${region.cc.toLowerCase()}`,
    parse(html) {
      const results = [];
      for (const block of html.split(/<li[^>]*>\s*<h2>/).slice(1, 30)) {
        const link = /<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(block);
        if (!link) continue;
        const snippet = /<p class="s">([\s\S]*?)<\/p>/.exec(block);
        results.push({ url: decodeEntities(link[1]), title: stripTags(link[2]), snippet: snippet ? stripTags(snippet[1]) : "", sponsored: false });
      }
      return results;
    },
  },
];

// One search across the engines until one of them answers.
async function webSearch(query, region, maxEngines = 3) {
  const seen = new Set();
  const out = [];
  let answered = 0;
  for (const engine of ENGINES) {
    if (answered >= maxEngines) break;
    const html = await fetchText(engine.url(query, region), region.lang + "," + region.lang.split("-")[0] + ";q=0.8,en;q=0.5");
    if (!html) continue;
    let results = [];
    try { results = engine.parse(html); } catch { results = []; }
    if (!results.length) continue;
    answered++;
    for (const result of results) {
      let host;
      try { host = new URL(result.url).hostname.replace(/^www\./, ""); } catch { continue; }
      const key = result.url.split("#")[0];
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ ...result, host, engine: engine.id });
    }
    // Two engines agreeing is plenty; a third only when the first two were thin.
    if (out.length >= 24) break;
  }
  return out;
}
Shield.webSearch = webSearch;

// Offers from the open web: a result whose snippet or title carries a price,
// from a page that looks like a store and not a review or a forum.
function offersFromResults(results, query, here) {
  const offers = [];
  for (const result of results) {
    if (result.sponsored) continue;
    const site = Shield.siteOf(result.host);
    if (site === here || NOT_STORES.test(result.host)) continue;
    const money = Shield.readMoney(result.snippet + " " + result.title, result.host);
    if (!money) continue;
    const score = Shield.similarity(query, result.title + " " + result.snippet.slice(0, 200));
    if (score < 0.5) continue;
    offers.push({
      title: result.title.slice(0, 140),
      url: result.url,
      store: result.host,
      price: money.price,
      currency: money.currency,
      score,
      independent: !Shield.isWellKnown(result.host),
      sponsored: false,
      source: result.engine,
    });
  }
  return offers;
}

// The web, at home and abroad. Returns offers with `total` in the home
// currency and the native price kept beside it.
Shield.marketOffers = async function marketOffers(product, options = {}) {
  const home = String(options.homeCurrency || product.currency || "USD").toUpperCase();
  const query = Shield.searchQuery(product);
  const here = Shield.siteOf(Shield.hostOf(product.url || ""));
  const table = await Shield.rates();
  const homeRegion = regionFor(home);
  const abroad = options.foreign === false ? [] : REGIONS.filter((region) => region.id !== homeRegion.id && region.currency !== home)
    .slice(0, Number(options.foreignRegions) || 4);
  const searches = [
    webSearch(query + " price", homeRegion, 3).then((results) => ({ region: homeRegion, results })),
    ...abroad.map((region) => webSearch(query + " " + (region.id === "jp" ? "価格" : region.id === "cn" ? "价格" : region.id === "kr" ? "가격" : region.id === "de" ? "preis" : region.id === "fr" ? "prix" : region.id === "es" || region.id === "mx" ? "precio" : region.id === "br" ? "preço" : region.id === "it" ? "prezzo" : region.id === "pl" ? "cena" : region.id === "tr" ? "fiyat" : region.id === "ae" ? "سعر" : "price"), region, 2).then((results) => ({ region, results }))),
  ];
  const answers = await Promise.all(searches.map((promise) => promise.catch(() => null)));
  const offers = [];
  const seen = new Set();
  for (const answer of answers) {
    if (!answer) continue;
    for (const offer of offersFromResults(answer.results, query, here)) {
      if (seen.has(offer.url)) continue;
      seen.add(offer.url);
      const converted = Shield.convert(offer.price, offer.currency, home, table);
      offers.push({
        ...offer,
        foreign: answer.region.id !== homeRegion.id && offer.currency !== home,
        country: answer.region.name,
        total: converted === null ? null : converted,
        nativeTotal: offer.price,
        converted: offer.currency !== home && converted !== null,
        shippingKnown: false,
      });
    }
  }
  return {
    home,
    query,
    rates: { source: table.source, at: table.at, approximate: Boolean(table.approximate) },
    offers: offers.filter((offer) => offer.total !== null).sort((left, right) => left.total - right.total),
    regions: [homeRegion, ...abroad].map((region) => region.name),
  };
};

// ---- coupons from the public web ------------------------------------------------------

const CODE_WORD = /\b(?:code|coupon|promo|voucher|discount|rabatt|gutschein|código|codice|réduction|cupom|cupón|промокод|クーポン|优惠码|쿠폰)\b/i;
const NOT_A_CODE = /^(CODE|PROMO|COUPON|HERE|NOW|SAVE|FREE|SHOP|ONLY|WITH|YOUR|THIS|THAT|FROM|SALE|DEAL|DEALS|OFF|GET|THE|AND|FOR|NEW|ALL|BEST|TODAY|VERIFIED|EXPIRED|SHIPPING|ORDER|ORDERS|STORE|ONLINE|CLICK|COPY|APPLY|SHOW|SEE|MORE|LESS|USE|EXTRA|UP|TO|ON|OFFER|OFFERS|FIRST|JOIN|SIGN|EMAIL|TEXT|APP|GIFT|CARD|CARDS|BUY|ONE|TWO|HALF|PRICE|ENDS|LIMITED|TIME|SITEWIDE|SELECT|ITEMS|STUDENT|MEMBER|MEMBERS|REWARDS|CLEARANCE|BLACK|FRIDAY|CYBER|MONDAY|HOLIDAY|SUMMER|WINTER|SPRING|FALL|FLASH|WEEKEND|UNLOCK|EXCLUSIVE|BONUS|PLUS|VIP|PRO|HTML|HTTP|HTTPS|JSON|API|USD|EUR|GBP|UTC|GMT)$/;
// A token that looks like a code: letters and digits, 4-20 long, at least
// one letter, not a plain word (a plain word has no digit and reads as English).
function looksLikeCode(token) {
  if (!/^[A-Z0-9][A-Z0-9-]{3,19}$/.test(token)) return false;
  if (!/[A-Z]/.test(token) || NOT_A_CODE.test(token)) return false;
  if (!/\d/.test(token) && !/^[A-Z]{4,12}$/.test(token)) return false;
  return true;
}
function codesFromText(text, limit = 20) {
  const found = new Map();
  const words = String(text).replace(/\s+/g, " ");
  // "code SAVE20", "coupon: FREESHIP", "SPRING10 at checkout"
  // The keyword in any capitalisation, the code itself in capitals.
  const near = /(?:[Cc]ode|CODE|[Cc]oupon|COUPON|[Pp]romo|PROMO|[Vv]oucher|VOUCHER|[Gg]utschein|[Cc]ódigo|[Cc]odice|[Cc]upom|[Cc]upón)\s*[:\-–]?\s*["“']?([A-Z0-9][A-Z0-9-]{3,19})\b|\b([A-Z0-9][A-Z0-9-]{3,19})\s+(?:at checkout|for \d+%|to (?:get|save|take))/g;
  let match;
  while ((match = near.exec(words)) && found.size < limit) {
    const token = (match[1] || match[2] || "").toUpperCase();
    if (looksLikeCode(token)) found.set(token, (found.get(token) || 0) + 2);
  }
  // Codes shown on their own in coupon sites' markup come through stripTags as lone tokens.
  const lone = /\b([A-Z][A-Z0-9]{2,}\d[A-Z0-9]{0,15}|\d{1,3}[A-Z]{3,12})\b/g;
  while ((match = lone.exec(words)) && found.size < limit * 2) {
    const token = match[1].toUpperCase();
    if (looksLikeCode(token) && CODE_WORD.test(words.slice(Math.max(0, match.index - 160), match.index + 160))) found.set(token, (found.get(token) || 0) + 1);
  }
  return Array.from(found.entries()).sort((left, right) => right[1] - left[1]).map(([code]) => code);
}
Shield.codesFromText = codesFromText;

const COUPON_PAGES = [
  (site) => `https://couponfollow.com/site/${site}`,
  (site) => `https://www.retailmenot.com/view/${site}`,
  (site) => `https://www.dealspotr.com/promo-codes/${site}`,
  (site) => `https://www.knoji.com/promo-codes/${site.split(".")[0]}/`,
  (site) => `https://www.coupons.com/coupon-codes/${site.split(".")[0]}`,
  (site) => `https://www.wethrift.com/${site.split(".")[0]}`,
];

// Codes for a store found on the public web, cached for six hours. Every
// one is a guess until the checkout proves it: the content script tries
// them one by one and only keeps what lowered the total.
Shield.findCoupons = async function findCoupons(site) {
  site = String(site || "").toLowerCase().replace(/^www\./, "");
  if (!site || Shield.isLocalHost(site)) return [];
  const stored = await Shield.api.storage.local.get("webCoupons");
  const cache = stored.webCoupons || {};
  const cached = cache[site];
  if (cached && Date.now() - cached.at < 6 * 3600000) return cached.codes;
  const tally = new Map();
  const bump = (code, weight) => tally.set(code, (tally.get(code) || 0) + weight);
  // 1. Coupon pages, in parallel.
  const pages = await Promise.all(COUPON_PAGES.map((build) => fetchText(build(site), "en").catch(() => null)));
  for (const html of pages) {
    if (!html) continue;
    // Codes in data attributes or dedicated spans come first.
    for (const match of html.matchAll(/data-(?:code|coupon-code|clipboard-text)="([A-Za-z0-9-]{4,20})"/g)) {
      const code = match[1].toUpperCase();
      if (looksLikeCode(code)) bump(code, 3);
    }
    for (const match of html.matchAll(/class="[^"]*\b(?:code|coupon-code|promo-code|coupon_code)\b[^"]*"[^>]*>\s*([A-Za-z0-9-]{4,20})\s*</g)) {
      const code = match[1].toUpperCase();
      if (looksLikeCode(code)) bump(code, 3);
    }
    for (const code of codesFromText(stripTags(html).slice(0, 120000), 25)) bump(code, 1);
  }
  // 2. A web search; snippets often carry the code itself.
  try {
    const results = await webSearch(`"${site}" coupon code`, regionFor("USD"), 2);
    for (const result of results) {
      if (result.sponsored) continue;
      for (const code of codesFromText(result.title + " " + result.snippet, 6)) bump(code, 1);
    }
  } catch { /* nothing from the web today */ }
  const codes = Array.from(tally.entries()).sort((left, right) => right[1] - left[1]).slice(0, 14).map(([code]) => code);
  cache[site] = { at: Date.now(), codes };
  const keys = Object.keys(cache);
  if (keys.length > 300) delete cache[keys[0]];
  await Shield.api.storage.local.set({ webCoupons: cache });
  return codes;
};

})();
