// Search results, cleaned: on Google, Bing, DuckDuckGo, Brave, Yahoo,
// Startpage and Ecosia the paid results go, pages from known content farms
// go, and pages that read as written for the search engine rather than for a
// person are dimmed, all with a count you can open. The same pages also wear
// the look the person chose, so a search does not break the picture.
(() => {
  "use strict";
  if (window.top !== window) return;

  // Per-page token shared with the other isolated-world scripts (page cannot
  // see this window). Every id, class, attribute and css variable the shield
  // puts on the page is rewritten to it, so a fixed-name signature never
  // matches at runtime.
  const T = (() => {
    const w = window;
    if (!w.__nt) { const r = crypto.getRandomValues(new Uint32Array(2)); Object.defineProperty(w, "__nt", { value: "n" + r[0].toString(36) + r[1].toString(36), configurable: true }); }
    return w.__nt;
  })();
  const Z = (str) => String(str)
    .replace(/--noah-/g, "--" + T + "-")
    .replace(/data-noah-shield/g, "data-" + T)
    .replace(/data-noah-repaint/g, "data-" + T + "-r")
    .replace(/noah-shield-look-layer/g, T + "-ll")
    .replace(/noah-shield-look/g, T + "-lk")
    .replace(/noah-shield-search-note/g, T + "-nt")
    .replace(/noah-shield-search/g, T + "-ss")
    .replace(/noah-shield-74/g, T + "-sf")
    .replace(/noah-price-chip/g, T + "-pc")
    .replace(/noah-prices/g, T + "-pr")
    .replace(/noah-peek/g, T + "-pk");
  const api = globalThis.chrome ?? globalThis.browser;
  const host = location.hostname.toLowerCase();

  const ENGINES = [
    {
      id: "google",
      match: /(^|\.)google\.[a-z.]{2,10}$/,
      page: () => new URLSearchParams(location.search).has("q") && !/^\/(maps|flights|travel|finance|books|scholar|patents|trends)\b/.test(location.pathname),
      ads: ["#tads", "#tadsb", "#bottomads", "#taw [data-text-ad]", "[data-text-ad]", ".commercial-unit-desktop-top", ".commercial-unit-desktop-rhs", ".cu-container", "#rhs .commercial-unit", "div[aria-label='Ads']", "div[aria-label='Sponsored']", ".ads-fr", "[data-pla='1']", "#tvcap"],
      results: ["#rso > div", "#rso .MjjYud", "#rso .g", "#search .g"],
      transparent: ["#main", "#cnt", "#rcnt", "#center_col", ".main", "#searchform", "#appbar", "#hdtb", ".sfbg", "#top_nav", "#before-appbar", "#rhs", "#footcnt", "#botstuff", ".appbar", "#kp-wp-tab-overview"],
    },
    {
      id: "bing",
      match: /(^|\.)bing\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [".b_ad", "#b_pole .b_adTop", ".b_adTop", ".b_adBottom", "li.b_ad", ".b_adLastChild", "#b_results > li.b_ad", ".ad_sc"],
      results: ["#b_results > li"],
      transparent: ["#b_header", "#b_content", "#b_results", ".b_scopebar", "#b_footer", "#b_context", ".b_searchboxForm"],
    },
    {
      id: "duckduckgo",
      match: /(^|\.)duckduckgo\.com$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: ["[data-testid='ad']", "li[data-layout='ad']", ".badge--ad", "[data-layout='ad']", ".js-sponsored-results", ".results--ads", ".module--carousel-ads"],
      results: ["article[data-testid='result']", "li[data-layout='organic']", ".result"],
      transparent: ["#react-layout", "main", "header", ".header-wrap", ".results", "#links_wrapper", ".serp__results", "section"],
    },
    {
      id: "brave",
      match: /(^|\.)search\.brave\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [".ad", "[data-type='ad']", ".ad-result", ".ads", "#ads"],
      results: ["#results > .snippet", ".snippet"],
      transparent: ["#main", "main", "header", ".main-column", "#results", ".sidebar", "#side-right", ".header"],
    },
    {
      id: "yahoo",
      match: /(^|\.)search\.yahoo\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [".searchCenterTopAds", ".searchCenterBottomAds", ".searchRightTopAds", ".searchRightMiddleAds", "li.ad", ".AdTop", ".AdBttm", "#right .ads"],
      results: ["#web ol > li", "#web li"],
      transparent: ["#bd", "#main", "#web", "#right", "#header", ".sbq-w", "#ft"],
    },
    {
      id: "startpage",
      match: /(^|\.)startpage\.com$/,
      page: () => /\/(do|sp)\/search/.test(location.pathname),
      ads: [".ad", ".mainline-ad", ".css-ads"],
      results: [".w-gl__result", ".result", "[class*='w-gl__result']"],
      transparent: [".layout-web", ".w-gl", "header", "main", ".mainline", ".sidebar"],
    },
    {
      id: "ecosia",
      match: /(^|\.)ecosia\.org$/,
      page: () => location.pathname.startsWith("/search"),
      ads: ["[data-test-id='mainline-ad']", "[data-test-id='sidebar-ad']", ".card-ad", ".ad", ".ads"],
      results: ["[data-test-id='mainline-result']", ".result", ".mainline__result-wrapper article"],
      transparent: [".layout", ".layout__content", "main", "header", ".mainline", ".sidebar", ".results"],
    },
    // Engines of other countries and companies. Where the markup is less
    // known, the generic "Sponsored"-label walker below still finds the paid
    // blocks in that engine's own language.
    {
      id: "yandex",
      match: /(^|\.)(yandex\.(ru|com|com\.tr|by|kz|ua|uz|az|eu)|ya\.ru)$/,
      page: () => /\/search/.test(location.pathname) || new URLSearchParams(location.search).has("text"),
      ads: [".serp-adv-item", "[data-fast-name='adv']", ".organic_type_adv", "li.serp-item_card_adv", ".serp-adv__item", ".Organic_type_adv", "[data-cid] .serp-adv"],
      results: ["li.serp-item", ".serp-list > li", "#search-result > li"],
      transparent: [".main", ".serp-header", ".content", ".serp-list", "#search-result", ".HeaderForm", ".main__content"],
    },
    {
      id: "baidu",
      match: /(^|\.)baidu\.com$/,
      page: () => new URLSearchParams(location.search).has("wd") || new URLSearchParams(location.search).has("word"),
      ads: ["#content_left > div[cmatchid]", ".ec_tuiguang_link", "[data-tuiguang]", ".ec_ad_results", "#ec_im_container", ".result-op[tpl*='ad']", "#content_left > div[data-placeid]", ".ec-pc_ad"],
      results: ["#content_left > div.result", "#content_left > .c-container", ".result-op"],
      transparent: ["#wrapper", "#head", "#content_left", "#content_right", "#s_tab", "#foot", "#container", ".s_form"],
    },
    {
      id: "naver",
      match: /(^|\.)search\.naver\.com$/,
      page: () => new URLSearchParams(location.search).has("query"),
      ads: [".ad_section", "#power_link_body", ".sp_nsearch .ad", ".lst_type.lst_ad", ".ad_area", "#ad_group", ".spw_rerank"],
      results: [".lst_total > li", "li.bx", ".api_subject_bx"],
      transparent: ["#wrap", "#container", "#main_pack", "#content", "#header", "#sub_pack", ".api_subject_bx"],
    },
    {
      id: "daum",
      match: /(^|\.)search\.daum\.net$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: ["#adColl", "#sponsoredColl", ".ad_wrap", "#ad_bottom_wrap", "#adCollTop", "#adCollBottom", "[id*='adColl']"],
      results: ["#webColl li", ".coll_cont li", "#mainColl li"],
      transparent: ["#daumWrap", "#daumContent", "#mainColl", "#header", "#daumHead", ".coll_cont"],
    },
    {
      id: "seznam",
      match: /(^|\.)search\.seznam\.cz$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: ["[data-dot='sklik']", ".Sklik", "[data-e-b='sklik']", ".Result--sklik", "[data-dot-data*='sklik']", "[data-e-b*='Sklik']"],
      results: ["[data-dot='results'] > div", ".Result", "[data-e-b='result']"],
      transparent: [".Page", ".Page-content", ".Header", ".Layout", ".Layout--left", ".Layout--right"],
    },
    {
      id: "qwant",
      match: /(^|\.)qwant\.com$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: ["[data-testid='adResult']", ".ad"],
      results: ["[data-testid='webResult']", ".result", "[class*='webResult']"],
      transparent: ["main", "header", ".container", "[class*='Layout']", "[class*='Results']"],
    },
    {
      id: "sogou",
      match: /(^|\.)sogou\.com$/,
      page: () => new URLSearchParams(location.search).has("query"),
      ads: [".gg", "[id^='sogou_ad']", ".ad", ".sponsored", ".tg"],
      results: [".results > .vrwrap", ".results > .rb", ".results > div"],
      transparent: ["#wrapper", "#main", ".results", "#right", "#header", ".header"],
    },
    {
      id: "so360",
      match: /(^|\.)so\.com$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: [".res-gap-right-ad", ".e-ad", "[data-type='ad']", ".sponsor", ".mohe-ad"],
      results: [".res-list li.res-list", "#main li.res-list", ".result li"],
      transparent: ["#wrapper", "#main", "#container", "#header", ".res-list", "#side"],
    },
    {
      id: "yahoojapan",
      match: /(^|\.)search\.yahoo\.co\.jp$/,
      page: () => new URLSearchParams(location.search).has("p"),
      ads: [".Ad", "[class*='AdList']", ".sw-Card--ad", "#ad_top", "#ad_bottom"],
      results: [".sw-Card", ".Contents__innerGroupBody > div", ".Algo"],
      transparent: ["#contents", ".Contents", "#header", ".Header", ".Contents__inner", "#sub"],
    },
    {
      id: "coccoc",
      match: /(^|\.)coccoc\.com$/,
      page: () => new URLSearchParams(location.search).has("query"),
      ads: [".ad", "[data-ad]", ".sponsored"],
      results: [".result", "[class*='result']"],
      transparent: ["main", "header", ".content", ".results"],
    },
    {
      id: "aol",
      match: /(^|\.)search\.aol\.com$/,
      page: () => location.pathname.includes("/search"),
      ads: [".searchCenterTopAds", ".searchCenterBottomAds", ".searchRightTopAds", ".searchRightMiddleAds", "li.ad", ".AdTop", ".AdBttm"],
      results: ["#web ol > li", "#web li"],
      transparent: ["#bd", "#main", "#web", "#right", "#header", "#ft"],
    },
    {
      id: "ask",
      match: /(^|\.)ask\.com$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: [".PartialDisplayAd", "[class*='DisplayAd']", ".ad"],
      results: [".PartialSearchResults-item", "[class*='SearchResults-item']"],
      transparent: ["main", "header", ".PartialSearchResults", ".PartialPageHeader"],
    },
    {
      id: "mailru",
      match: /(^|\.)go\.mail\.ru$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: [".result__ad", ".ad", "[data-ad]"],
      results: [".result__li", "[class*='result__li']"],
      transparent: [".page", ".header", ".result", ".sidebar"],
    },
    {
      id: "rambler",
      match: /(^|\.)nova\.rambler\.ru$/,
      page: () => new URLSearchParams(location.search).has("query"),
      ads: [".ad", "[data-ad]"],
      results: ["[class*='result']", "article"],
      transparent: ["main", "header", "[class*='layout']"],
    },
    {
      id: "petal",
      match: /(^|\.)petalsearch\.com$/,
      page: () => new URLSearchParams(location.search).has("query"),
      ads: [".ad"],
      results: [".result", "[class*='result-item']", "[class*='result']"],
      transparent: ["main", "header", ".container"],
    },
    {
      id: "kagi",
      match: /(^|\.)kagi\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [],
      results: [".search-result", "._0_SRI", ".sri-group > div"],
      transparent: ["main", "header", ".app", "#main", ".center-content"],
    },
    {
      id: "you",
      match: /(^|\.)you\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [],
      results: ["[data-testid='web-result']", "[class*='webResult']"],
      transparent: ["main", "header"],
    },
    {
      id: "mojeek",
      match: /(^|\.)mojeek\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [],
      results: ["ul.results-standard > li", ".results > li"],
      transparent: ["main", "header", ".results", "#results"],
    },
    {
      id: "swisscows",
      match: /(^|\.)swisscows\.com$/,
      page: () => location.pathname.startsWith("/web"),
      ads: [".ad"],
      results: [".item", ".web-results article", "[class*='web-result']"],
      transparent: ["main", "header", ".content", ".results"],
    },
    {
      id: "presearch",
      match: /(^|\.)presearch\.com$/,
      page: () => location.pathname.startsWith("/search"),
      ads: [".ad"],
      results: [".result", "[class*='result']"],
      transparent: ["main", "header"],
    },
    {
      id: "lilo",
      match: /(^|\.)search\.lilo\.org$/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: [".ad"],
      results: [".result", "[class*='result']"],
      transparent: ["main", "header"],
    },
    {
      id: "yep",
      match: /(^|\.)yep\.com$/,
      page: () => location.pathname.startsWith("/web"),
      ads: [],
      results: ["[class*='result']", "article"],
      transparent: ["main", "header"],
    },
    {
      id: "searx",
      // Self-hosted SearXNG instances: the name is in the host.
      match: /searx|searxng/,
      page: () => new URLSearchParams(location.search).has("q"),
      ads: [],
      results: ["article.result", ".result"],
      transparent: ["main", "header", "#main_results", "#results", "#sidebar"],
    },
    {
      id: "ecosia-regional",
      match: /(^|\.)ecosia\.[a-z]{2,3}$/,
      page: () => location.pathname.startsWith("/search"),
      ads: ["[data-test-id='mainline-ad']", "[data-test-id='sidebar-ad']", ".card-ad", ".ad", ".ads"],
      results: ["[data-test-id='mainline-result']", ".result", ".mainline__result-wrapper article"],
      transparent: [".layout", ".layout__content", "main", "header", ".mainline", ".sidebar", ".results"],
    }];
  const engine = ENGINES.find((entry) => entry.match.test(host));
  if (!engine) return;

  // Kill the white flash: at document_start, before the worker is even awake,
  // paint the canopy background and pull the look straight from storage (a
  // content script reads storage without waking the service worker, so it is
  // far faster than the round-trip). The authoritative state refines this a
  // moment later. If the look turns out to be off, the base is removed.
  (function earlyPaint() {
    try {
      const base = document.createElement("style");
      base.id = Z("noah-shield-base");
      base.textContent = "html{background:#090f0c !important;color-scheme:dark}";
      (document.head || document.documentElement).append(base);
      api.storage.local.get("look").then((got) => {
        const look = got && got.look;
        if (!look || !look.image) return;
        if (state) return; // real state already arrived
        state = { look: true, image: api.runtime.getURL("looks/" + look.image), palette: look.palette || {}, early: true };
        if (document.body) { wearLook(); show74(); } else document.addEventListener("DOMContentLoaded", () => { wearLook(); show74(); }, { once: true });
      }).catch(() => {});
    } catch {}
  })();

  // Words a paid result is labelled with, in the languages the engines use most.
  const PAID = /^(sponsored|sponsored result|ad|ads|advertisement|anzeige|anzeigen|annonce|annonces|publicidad|anuncio|anuncios|anúncio|annuncio|advertentie|reklam|reklama|reklāma|reklaam|hirdetés|anunț|διαφήμιση|mainos|annons|annonse|iklan|quảng cáo|โฆษณา|إعلان|ممول|פרסומת|ממומן|विज्ञापन|प्रायोजित|广告|推广|赞助|廣告|贊助|広告|スポンサー|광고|스폰서|реклама|промо|patrocinado|patrocinat|gesponsert|sponsorisé|sponsorizzato|gesponsord|sponsrad|sponsoreret|sponsorowane|sponzorováno|спонсируемый)$/i;

  // Content farms and scraper sites: pages made to rank, not to be read.
  // Copies of Stack Overflow and GitHub, article mills, coupon clones, and
  // "answer" sites that answer nothing.
  const FARMS = [
    "stackoom.com", "codegrepper.com", "programmersought.com", "copyprogramming.com", "iditect.com", "itecnote.com", "githubmemory.com", "gitmemory.com", "gitanswer.com", "giters.com", "githubhelp.com", "coder.social", "issuehunt.io", "lightrun.com", "bleepcoder.com", "fatalerrors.org", "titanwolf.org", "debugah.com", "programmerall.com", "codeleading.com", "cxymm.net", "cxyzjd.com", "codenong.com", "javaer101.com", "ostack.cn", "qastack.cn", "qa-stack.pl", "stackovergo.com", "stackoverrun.com", "coderoad.ru", "question-it.com", "jike.in", "wsxdn.com", "codetd.com", "cdmana.com", "pythonfixing.com", "pythonrepo.com", "askpython.com", "pythonpool.com",
    "ezinearticles.com", "hubpages.com", "buzzle.com", "brighthub.com", "infobarrel.com", "streetarticles.com", "articlecity.com", "selfgrowth.com", "sooperarticles.com", "articlesfactory.com", "amazines.com", "isnare.com", "goarticles.com", "articlebiz.com", "articlesbase.com", "articlealley.com", "articledashboard.com", "helium.com", "examiner.com", "associatedcontent.com", "squidoo.com", "wisegeek.com", "wise-geek.com", "answers.com", "ask.com", "reference.com", "chacha.com", "blurtit.com", "fixya.com", "justanswer.com", "answerbag.com", "askmefast.com", "allexperts.com", "askmehelpdesk.com", "wikianswers.com", "soquestions.com", "askinglot.com", "findanyanswer.com", "treehozz.com", "greedhead.net", "handlebar-online.com", "restaurantnorman.com", "blfilm.com", "sage-answer.com", "sage-advices.com", "sage-tips.com", "short-facts.com", "mysqlpreacher.com", "thehealthyjournal.com", "wisdom-advices.com", "profound-answers.com", "profound-information.com", "profound-tips.com", "easierwithpractice.com", "yourquickadvice.com", "yourquickinfo.com", "great-american-adventures.com", "moviecultists.com", "bookvea.com", "thelastdialogue.org", "erasingdavid.com", "boardgamestips.com", "faq-blog.com", "faq-ans.com", "faq-all.com", "quick-advice.com", "quick-advices.com", "quick-adviser.com", "knowledgeburrow.com", "heimduo.org", "theknowledgeburrow.com", "atheistsforhumanrights.org", "studybuff.com", "howdoiplaythis.com", "ifsql.com", "lastfiascorun.com", "raiseupwa.com", "any-answers.com", "estebantorreshighschool.com", "philosophy-question.com", "answers-to-all.com", "answerstoall.com", "answer-all.com", "all-famous-faqs.com", "famuse.co", "coalitionbrewing.com", "ourgoodbrands.com", "authorscast.com", "juliebutlercreations.com", "thetalentedworld.net", "morethingsjapanese.com", "thecrucibleonscreen.com", "mccnsulting.web.fc2.com",
    "couponxoo.com", "couponupto.com", "couponsdoom.com", "promocodeslab.com", "coupert.com", "dealscove.com", "hotdeals.com", "couponbirds.com", "couponfollow.com", "dealspotr.com", "knoji.com", "tenereteam.com", "couponannie.com", "couponcabin.com", "wethrift.com", "dontpayfull.com", "getcouponsworld.com", "couponsplusdeals.com", "discountscat.com", "promosearcher.com", "shopper.com", "savemoneyfacts.com", "mycoupons.com", "couponchief.com", "couponsandcodes.com", "ultimatecoupons.com",
    "gearrice.com", "gamingdeputy.com", "bollyinside.com", "techviral.net", "techgenyz.com", "technewstube.com", "wsxdn.com", "solveforum.com", "errorsfixing.com", "exceptionshub.com", "fix.code-error.com", "code-examples.net", "newbedev.com", "stackoverflow.fogbugz.com", "tutorialspoint.dev", "w3cschool.cn", "javatpoint.com", "geeksforgeeks.org", "programiz.com", "delftstack.com", "linuxhint.com", "tecadmin.net", "itsfoss.com", "makeuseof.com", "howtogeek.com"];
  // The last line above is the software-tutorial mills; people disagree about
  // them, so they are dimmed as "written for the engine", never hidden.
  const DIMMED_ONLY = new Set(["javatpoint.com", "geeksforgeeks.org", "programiz.com", "delftstack.com", "linuxhint.com", "tecadmin.net", "itsfoss.com", "makeuseof.com", "howtogeek.com", "tutorialspoint.dev", "w3cschool.cn", "answers.com", "ask.com", "reference.com", "justanswer.com", "hubpages.com", "quora.com"]);
  const FARM_SET = new Set(FARMS);
  // A title that reads as a template: "Best 15 X in 2026", "X: Everything You
  // Need to Know", "Top 10 X (Updated)", "X vs Y: Which Is Better?" and so on.
  const TEMPLATE = /(\b(top|best)\s+\d+\b.*\b20\d\d\b)|(\beverything you need to know\b)|(\bultimate guide\b)|(\bupdated\s*(for)?\s*20\d\d\b)|(\b\d+\s+(best|top|amazing|incredible|surprising|mind-blowing|proven)\b)|(\bwhich is better\b)|(\byou won'?t believe\b)|(\bwhat you need to know\b)|(\bthe complete guide\b)|(\ba complete guide\b)|(\bin\s+20\d\d\s*[:(\[-]\s*(complete|full|updated|expert|honest|definitive))/i;

  const STYLE_ID = Z("noah-shield-search");
  const hidden = new WeakSet();
  const dimmed = new WeakSet();
  let counts = { paid: 0, farms: 0, dimmed: 0 };
  let reported = { paid: 0, farms: 0, dimmed: 0 };
  let state = null;

  function siteOf(hostname) {
    const parts = hostname.toLowerCase().replace(/^www\./, "").split(".");
    if (parts.length <= 2) return parts.join(".");
    const twoPart = /^(co|com|org|net|ac|gov|edu)\.[a-z]{2}$/.test(parts.slice(-2).join("."));
    return parts.slice(twoPart ? -3 : -2).join(".");
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = Z(`
      [data-noah-shield="paid"], [data-noah-shield="farm"] { display: none !important; }
      [data-noah-shield="dim"] { opacity: .42 !important; filter: saturate(.6); transition: opacity .2s; }
      [data-noah-shield="dim"]:hover { opacity: 1 !important; filter: none; }
      [data-noah-shield="dim"]::before { content: "written for the search engine · shown faded"; display: block; font: 11px/1.4 system-ui, sans-serif; color: #9aa298; margin: 0 0 2px; }
      #noah-shield-search-note { position: fixed; right: 14px; bottom: 14px; z-index: 2147483000; font: 12px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--noah-text, #d8ddd6); background: var(--noah-raise, rgba(10, 16, 12, .94)); border: 1px solid var(--noah-line, rgba(180, 210, 190, .16)); border-radius: 10px; padding: 7px 11px; box-shadow: 0 6px 24px rgba(0,0,0,.35); cursor: pointer; opacity: 0; transition: opacity .3s ease; }
      #noah-shield-search-note.on { opacity: 1; }
      #noah-shield-search-note b { font-weight: 500; color: var(--noah-accent, #a9cf9f); }
    `);
    (document.head || document.documentElement).append(style);
  }

  function mark(element, kind) {
    if (!element || hidden.has(element) || element.closest(Z("[data-noah-shield]"))) return false;
    element.setAttribute(Z("data-noah-shield"), kind);
    if (kind === "dim") dimmed.add(element); else hidden.add(element);
    return true;
  }

  function resultBlocks() {
    for (const selector of engine.results) {
      const found = document.querySelectorAll(selector);
      if (found.length) return Array.from(found);
    }
    return [];
  }

  function blockOf(element) {
    for (const selector of engine.results) {
      const block = element.closest(selector);
      if (block) return block;
    }
    return element.closest("li, article, div[data-hveid]");
  }

  function firstLink(block) {
    const anchor = block.querySelector("a[href^='http'] h3, h2 a[href^='http'], h3 a[href^='http'], a[href^='http'][data-testid='result-title-a'], a.result__a, a[href^='http']");
    if (!anchor) return null;
    return anchor.tagName === "A" ? anchor : anchor.closest("a");
  }

  function targetHost(anchor) {
    try {
      const url = new URL(anchor.href, location.href);
      // Some engines wrap the target: the real address rides in a parameter.
      for (const key of ["uddg", "url", "u", "q"]) {
        const inner = url.searchParams.get(key);
        if (inner && /^https?:\/\//.test(inner)) return new URL(inner).hostname;
      }
      if (url.hostname === location.hostname) return "";
      return url.hostname;
    } catch {
      return "";
    }
  }

  function sweep() {
    if (!state || !engine.page()) return;
    const before = { ...counts };
    if (state.clean) {
      for (const selector of engine.ads) {
        for (const element of document.querySelectorAll(selector)) {
          if (mark(element, "paid")) counts.paid++;
        }
      }
      // A "Sponsored" label with nothing else in it marks a paid block.
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
        acceptNode: (node) => (node.childElementCount === 0 && node.textContent.trim().length <= 14 && PAID.test(node.textContent.trim()) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP),
      });
      let label;
      const labels = [];
      while ((label = walker.nextNode())) labels.push(label);
      for (const node of labels) {
        const block = blockOf(node);
        if (block && !block.contains(document.querySelector("form[role='search'], input[name='q']")) && mark(block, "paid")) counts.paid++;
      }
    }
    if (state.farms) {
      for (const block of resultBlocks()) {
        if (block.hasAttribute(Z("data-noah-shield"))) continue;
        const anchor = firstLink(block);
        if (!anchor) continue;
        const target = targetHost(anchor);
        if (!target) continue;
        const site = siteOf(target);
        const title = (block.querySelector("h3, h2, [data-testid='result-title-a']") || anchor).textContent.trim();
        if (FARM_SET.has(site) && !DIMMED_ONLY.has(site)) {
          if (mark(block, "farm")) counts.farms++;
        } else if (DIMMED_ONLY.has(site) || TEMPLATE.test(title)) {
          if (mark(block, "dim")) counts.dimmed++;
        }
      }
    }
    if (counts.paid !== before.paid || counts.farms !== before.farms || counts.dimmed !== before.dimmed) {
      showNote();
      report();
    }
    addPeekButtons();
  }

  let noteTimer = null;
  function showNote() {
    ensureStyle();
    let note = document.getElementById(Z("noah-shield-search-note"));
    if (!note) {
      note = document.createElement("div");
      note.id = Z("noah-shield-search-note");
      note.title = "noah shield cleaned these results; press to see the log";
      note.addEventListener("click", () => api.runtime.sendMessage({ type: "log.open" }, () => void api.runtime.lastError));
      document.documentElement.append(note);
      if (window.__noahShieldDrag) window.__noahShieldDrag(note, note, "search-note");
    }
    const parts = [];
    if (counts.paid) parts.push(`<b>${counts.paid}</b> paid`);
    if (counts.farms) parts.push(`<b>${counts.farms}</b> content-farm`);
    if (counts.dimmed) parts.push(`<b>${counts.dimmed}</b> faded`);
    note.replaceChildren();
    const text = document.createElement("span");
    text.append("noah shield: ");
    parts.forEach((part, index) => {
      if (index) text.append(", ");
      const [count, word] = part.replace(/<\/?b>/g, "|").split("|").filter(Boolean);
      const strong = document.createElement("b");
      strong.textContent = count.trim();
      text.append(strong, " " + word.trim());
    });
    text.append(counts.paid + counts.farms === 1 && !counts.dimmed ? " result removed" : " results");
    note.append(text);
    const query = new URLSearchParams(location.search).get("q") || new URLSearchParams(location.search).get("p") || "";
    if (looksLikeAName(query)) {
      const footprint = document.createElement("a");
      footprint.href = api.runtime.getURL("footprint.html?name=" + encodeURIComponent(query.replace(/^"|"$/g, "")));
      footprint.target = "_blank";
      footprint.rel = "noopener";
      footprint.textContent = "your footprint?";
      footprint.style.cssText = "margin-left:10px;color:inherit;text-decoration:underline;text-underline-offset:3px;";
      note.append(footprint);
    }
    note.classList.add("on");
    clearTimeout(noteTimer);
    noteTimer = setTimeout(() => note.classList.remove("on"), 6000);
  }

  // Two to four capitalised words, or a quoted phrase, with no operators:
  // what someone types when they look a person up.
  function looksLikeAName(query) {
    const trimmed = query.trim();
    if (!trimmed || /[:@/.]/.test(trimmed)) return false;
    if (/^".+"$/.test(trimmed)) return true;
    const words = trimmed.split(/\s+/);
    return words.length >= 2 && words.length <= 4 && words.every((word) => /^\p{Lu}[\p{L}'’-]+$/u.test(word));
  }

  let reportTimer = null;
  function report() {
    clearTimeout(reportTimer);
    reportTimer = setTimeout(() => {
      const delta = { paid: counts.paid - reported.paid, farms: counts.farms - reported.farms, dimmed: counts.dimmed - reported.dimmed };
      reported = { ...counts };
      if (delta.paid + delta.farms + delta.dimmed <= 0) return;
      api.runtime.sendMessage({ type: "search.hidden", engine: engine.id, query: new URLSearchParams(location.search).get("q") || new URLSearchParams(location.search).get("p") || "", ...delta }, () => void api.runtime.lastError);
    }, 800);
  }

  // ---- the look -----------------------------------------------------------------------------
  // The whole results page takes the picture's palette, the shield's type and
  // its spacing: cards with the same radius and hairline, the same rhythm
  // between them, one accent where a hand goes. Whatever mode the engine was
  // in, the words are the palette's, so they always read.
  const THEME = {
    google: {
      cards: "#rso > div:has(h3), #rso .MjjYud:has(h3) > div:not(:has(.MjjYud)), .related-question-pair, #rhs .kp-blk, #rhs > div:has(h2), #botstuff > div:has(h3)",
      cardsInner: "#rso .MjjYud > div > div.g, #rso .g",
      title: "#rso h3, #rhs h2, #rhs h3, #botstuff h3",
      snippet: "#rso [data-sncf], #rso .VwiC3b, #rso div[style*='line-clamp'], #rso .ITZIwc, #rhs .kno-rdesc span, #rso span.hgKElc",
      url: "#rso cite, #rso .VuuXrf, #rso .byrV5b, #rhs cite",
      // only google's pill (.RNNXgb) gets the box; the form around it (which also
      // holds the logo) and the input row inside it stay bare, so there is one
      // outline instead of two nested ones
      searchBox: ".RNNXgb",
      searchBare: "#searchform form, #tsf, form[role='search'], form[role='search'] > div:not(.RNNXgb), .SDkEP, .a4bIc, .A8SBwf, .sfbg, #searchform .logo, .Tg7LZd, .dRYYxd",
      searchInput: "textarea[name='q'], input[name='q']",
      tabs: "#hdtb a, #top_nav a, .crJ18e a, #hdtb div[role='listitem'] a, .T47uwc a",
      tabSelected: "#hdtb .hdtb-msel, #hdtb a[aria-current], #hdtb [selected] a, .Ww4FFb[aria-selected='true']",
      chips: "#rso a[role='link'].fl, #rso .Xk52Ge a, #rso .zVvuGd a, #rso a.MXl0lf, .k8XOCe",
      quiet: "#rso .g .MUxGbd:not(.VwiC3b), #rso .fG8Fp, #rso .LEwnzc, #rhs .rhstc4, #botstuff td",
    },
    bing: { cards: "#b_results > li.b_algo, #b_results > li.b_ans, #b_context .b_ans", title: "#b_results h2, #b_context h2", snippet: "#b_results .b_caption p, #b_results .b_lineclamp2, #b_results .b_lineclamp3", url: "#b_results cite, #b_results .b_attribution", searchBox: "#sb_form, .b_searchboxForm", searchInput: "#sb_form_q", tabs: "#b_header .b_scopebar a", tabSelected: "#b_header .b_scopebar .b_active a", chips: "#b_results .b_rs a", quiet: "#b_results .b_factrow, #b_results .b_vlist2col" },
    duckduckgo: { cards: "article[data-testid='result'], li[data-layout='organic'] > article, section[data-testid='sidebar'] > div", title: "article h2, article h2 a span", snippet: "article [data-result='snippet'], article div[data-result='snippet'] span", url: "article a[data-testid='result-extras-url-link'], article p[data-testid='result-extras-url']", searchBox: "form[role='search'], #search_form, .search--header, div[data-testid='search-box-container']", searchInput: "#search_form_input, input[name='q']", tabs: "ul[data-testid='zci-tabs'] a, .zcm__link", tabSelected: ".zcm__link.is-active, ul[data-testid='zci-tabs'] a[aria-current]", chips: "article .related-searches a", quiet: "article footer" },
    brave: { cards: "#results > .snippet, #side-right > div", title: ".snippet .title, .snippet-title, #side-right h2", snippet: ".snippet .snippet-description, .snippet-content", url: ".snippet .netloc, .snippet cite, .snippet .site-name", searchBox: "#searchform, .searchbox, form#searchform > div", searchInput: "#searchbox, input[name='q']", tabs: ".tabs a, #tabs a, nav a.tab", tabSelected: ".tabs a.active, nav a.tab[aria-current]", chips: ".related a", quiet: ".snippet .footer" },
    yahoo: { cards: "#web ol > li, #right .dd", title: "#web h3, #right h3", snippet: "#web .compText p, #web .compText", url: "#web .compTitle cite, #web span.fz-ms", searchBox: "#sbq-wrap, .sbq-w, form[role='search']", searchInput: "#yschsp, input[name='p']", tabs: "#horizontal-bar a", tabSelected: "#horizontal-bar .active a", chips: "#web .compDlink a", quiet: "#web .compAttribution" },
    startpage: { cards: ".w-gl__result, .result, [class*='w-gl__result']", title: ".w-gl__result-title, .result-title, h2", snippet: ".w-gl__description, .result-description, p.description", url: ".w-gl__result-url, .result-link, a.link", searchBox: "form.search-form, .search-form", searchInput: "#q, input[name='query']", tabs: ".nav-bar a, .layout-web__header a", tabSelected: ".nav-bar a.active", chips: "", quiet: "" },
    ecosia: { cards: "[data-test-id='mainline-result'], .result, article", title: "[data-test-id='result-title'], .result-title, article h2", snippet: "[data-test-id='result-description'], .result-snippet, article p", url: "[data-test-id='result-url'], .result-url, article cite", searchBox: "form[role='search'], .search-form", searchInput: "input[name='q']", tabs: ".search-nav a, nav a", tabSelected: ".search-nav a[aria-current], nav a.active", chips: "", quiet: "" },
  };

  function themeCss(palette, image) {
    const theme = THEME[engine.id] || THEME.startpage;
    const p = {
      bg: palette.bg || "#070909", raise: palette.raise || "#0a100c", surface: palette.surface || "rgba(8, 11, 9, 0.92)", surface2: palette.surface2 || "rgba(10, 14, 11, 0.9)",
      line: palette.line || "rgba(180, 210, 190, 0.08)", lineMid: palette.lineMid || "rgba(180, 210, 190, 0.14)", text: palette.text || "#d8ddd6", sub: palette.sub || "#b9beb7",
      muted: palette.muted || "#9aa298", faint: palette.faint || "#6f766e", accent: palette.accent || "#5f8a58", accentBright: palette.accentBright || "#72a868", accentSoft: palette.accentSoft || "#a9cf9f", bright: palette.bright || "#f1f4ef",
    };
    const rule = (selector, body) => (selector ? `${selector} { ${body} }\n` : "");
    return Z(`
      :root { --noah-bg: ${p.bg}; --noah-raise: ${p.raise}; --noah-surface: ${p.surface}; --noah-surface2: ${p.surface2}; --noah-line: ${p.line}; --noah-line-mid: ${p.lineMid}; --noah-text: ${p.text}; --noah-sub: ${p.sub}; --noah-muted: ${p.muted}; --noah-faint: ${p.faint}; --noah-accent: ${p.accent}; --noah-accent-bright: ${p.accentBright}; --noah-accent-soft: ${p.accentSoft}; --noah-bright: ${p.bright}; --noah-display: Georgia, "Times New Roman", serif; --noah-body: -apple-system, "Segoe UI", system-ui, sans-serif; --noah-ease: cubic-bezier(0.2, 0.7, 0.2, 1); }
      html, body { background: transparent !important; color: var(--noah-text) !important; font-family: var(--noah-body) !important; color-scheme: dark; }
      ${engine.transparent.join(", ")} { background: transparent !important; background-color: transparent !important; box-shadow: none !important; border-color: var(--noah-line) !important; }
      #noah-shield-look-layer { position: fixed; inset: 0; z-index: -1; pointer-events: none; background-image: linear-gradient(color-mix(in srgb, ${p.bg} 82%, transparent), color-mix(in srgb, ${p.bg} 88%, transparent)), url("${image}"); background-size: cover; background-position: center; background-repeat: no-repeat; }
      ${rule(theme.cards, "background: var(--noah-surface) !important; border: 1px solid var(--noah-line) !important; border-radius: 14px !important; padding: 16px 18px !important; margin: 0 0 12px !important; box-shadow: none !important; transition: border-color .16s var(--noah-ease), transform .26s var(--noah-ease);")}
      ${rule(theme.cards ? theme.cards.split(",").map((part) => part.trim() + ":hover").join(", ") : "", "border-color: var(--noah-line-mid) !important;")}
      ${rule(theme.cardsInner, "background: transparent !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; border: 0 !important;")}
      ${rule(theme.title, "font-family: var(--noah-display) !important; font-weight: 400 !important; font-size: 21px !important; line-height: 1.25 !important; letter-spacing: .005em; color: var(--noah-bright) !important; margin: 2px 0 6px !important;")}
      ${rule(theme.title ? theme.title.split(",").map((part) => "a:hover " + part.trim().replace(/^#\w+ /, "")).join(", ") : "", "color: var(--noah-accent-soft) !important;")}
      ${rule(theme.snippet, "font-family: var(--noah-body) !important; font-size: 14px !important; line-height: 1.6 !important; color: var(--noah-sub) !important;")}
      ${rule(theme.url, "font-family: var(--noah-body) !important; font-size: 12px !important; color: var(--noah-muted) !important; letter-spacing: .01em;")}
      ${rule(theme.searchBare, "background: transparent !important; border: 0 !important; box-shadow: none !important; outline: 0 !important;")}
      ${rule(theme.searchBox, "background: color-mix(in srgb, var(--noah-bg) 78%, transparent) !important; border: 1px solid var(--noah-line-mid) !important; border-radius: 24px !important; box-shadow: 0 10px 36px rgba(0,0,0,.35) !important; backdrop-filter: blur(10px); transition: border-color .16s var(--noah-ease), box-shadow .16s var(--noah-ease);")}
      ${rule(theme.searchBox ? theme.searchBox.split(",").map((part) => part.trim() + ":focus-within").join(", ") : "", "border-color: color-mix(in srgb, var(--noah-accent-bright) 55%, transparent) !important; box-shadow: 0 10px 36px rgba(0,0,0,.4), 0 0 0 3px color-mix(in srgb, var(--noah-accent) 18%, transparent) !important;")}
      /* google draws a coloured loading line and a hairline under the bar */
      #searchform .RNNXgb ~ div[style*="background"], #searchform .gb_Pd, #searchform .Lm9tbe, #searchform .UUbT9 > div:empty { background: transparent !important; }
      #searchform, #searchform > div, .sfbg { border-bottom: 0 !important; box-shadow: none !important; }
      /* suggestions drop-down under the pill */
      .UUbT9, .aajZCb, .erkvQe { background: color-mix(in srgb, var(--noah-bg) 94%, transparent) !important; border: 1px solid var(--noah-line-mid) !important; border-top: 0 !important; border-radius: 0 0 24px 24px !important; box-shadow: 0 18px 40px rgba(0,0,0,.45) !important; }
      .UUbT9 li span, .aajZCb li span, .sbct span { color: var(--noah-sub) !important; }
      .sbhl, .sbct.sbhl, li.sbhl { background: color-mix(in srgb, var(--noah-accent) 14%, transparent) !important; }
      /* account picture: a rounded square instead of the blue ring */
      a[aria-label^="Google Account"], a[href*="SignOutOptions"], a[aria-label*="Google account"] { border-radius: 28% !important; }
      /* Google clips the photo with a round container; square every part of the
         button so the photo itself is a rounded square, not a circle in a square */
      a[aria-label^="Google Account"] *, a[href*="SignOutOptions"] *, a[aria-label*="Google account"] *, img.gbii, img.gb_Q, img.gb_P { border-radius: 28% !important; }
      a[aria-label^="Google Account"] img, a[href*="SignOutOptions"] img, a[aria-label*="Google account"] img, img.gbii, img.gb_Q, img.gb_P { overflow: hidden !important; object-fit: cover !important; box-shadow: 0 0 0 2px var(--noah-bg), 0 0 0 3.5px color-mix(in srgb, var(--noah-accent-bright) 70%, transparent) !important; }
      a[aria-label^="Google Account"] svg, a[href*="SignOutOptions"] svg, a[aria-label*="Google account"] svg { display: none !important; }
      /* scrollbars in the same leaves and shade */
      html { scrollbar-color: color-mix(in srgb, var(--noah-accent) 55%, transparent) transparent !important; scrollbar-width: thin !important; }
      * { scrollbar-color: color-mix(in srgb, var(--noah-accent) 45%, transparent) transparent; }
      ::-webkit-scrollbar { width: 10px; height: 10px; background: transparent; }
      ::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--noah-accent) 50%, transparent); border-radius: 10px; border: 3px solid transparent; background-clip: padding-box; }
      ::-webkit-scrollbar-thumb:hover { background-color: color-mix(in srgb, var(--noah-accent-bright) 70%, transparent); }
      ::-webkit-scrollbar-button { display: none; height: 0; width: 0; }
      /* boxes the shield repainted (ai overview and other grey panels) */
      [data-noah-repaint="panel"] { background-color: var(--noah-surface) !important; border-color: var(--noah-line) !important; }
      [data-noah-repaint="fade"] { background-image: linear-gradient(to bottom, transparent, color-mix(in srgb, var(--noah-bg) 92%, transparent) 70%) !important; background-color: transparent !important; }
      [data-noah-repaint="pill"] { background-color: transparent !important; border: 1px solid var(--noah-line-mid) !important; color: var(--noah-sub) !important; }
      [data-noah-repaint="pill"]:hover { border-color: var(--noah-accent) !important; color: var(--noah-bright) !important; }
      [data-noah-repaint="chip"] { background-color: color-mix(in srgb, var(--noah-accent) 12%, transparent) !important; }
      ${rule(theme.searchInput, "color: var(--noah-bright) !important; font-family: var(--noah-body) !important; font-size: 16px !important; background: transparent !important; caret-color: var(--noah-accent-soft);")}
      ${rule(theme.tabs, "color: var(--noah-muted) !important; font-family: var(--noah-body) !important; font-size: 13px !important; letter-spacing: .02em; text-decoration: none !important; border-bottom-color: transparent !important; transition: color .16s var(--noah-ease);")}
      ${rule(theme.tabs ? theme.tabs.split(",").map((part) => part.trim() + ":hover").join(", ") : "", "color: var(--noah-text) !important;")}
      ${rule(theme.tabSelected, "color: var(--noah-bright) !important; border-bottom: 2px solid var(--noah-accent-bright) !important;")}
      ${rule(theme.chips, "background: transparent !important; border: 1px solid var(--noah-line-mid) !important; border-radius: 999px !important; color: var(--noah-sub) !important; font-family: var(--noah-body) !important; font-size: 12px !important;")}
      ${rule(theme.quiet, "color: var(--noah-muted) !important;")}
      #rso, #rhs, #botstuff, #b_results, #b_context, #web, #right, #results, main, article { color: var(--noah-text) !important; }
      #rso span, #rso div, #rso em, #rso b, #rso td, #rhs span, #rhs div, #rhs td, #botstuff span, #botstuff div, #b_results span, #b_results div, #b_results p, #b_context span, #b_context div, #web span, #web div, #right span, #right div, #results span, #results div, article span, article p, article div { color: inherit; }
      #rso a, #rhs a, #botstuff a, #b_results a, #b_context a, #web a, #right a, #results a, article a { color: var(--noah-accent-soft); }
      #rso em, #b_results strong, article b { color: var(--noah-bright) !important; font-style: normal; font-weight: 500; }
      #rso img, #rhs img, #b_results img, article img { border-radius: 10px; }
      #rso svg, #rhs svg, #hdtb svg, #searchform svg { fill: var(--noah-muted); color: var(--noah-muted); }
      ::selection { background: color-mix(in srgb, var(--noah-accent) 45%, transparent); }
      #noah-shield-search-note { font-family: var(--noah-body) !important; }
      /* prices under results */
      .noah-prices { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 8px; margin: 8px 0 2px; font: 12.5px/1.5 var(--noah-body, system-ui); color: var(--noah-sub, #c6c7aa); }
      .noah-prices.quiet { color: var(--noah-faint, #676d54); font-size: 12px; }
      .noah-prices-label { font-size: 10.5px; letter-spacing: .12em; color: var(--noah-muted, #9a9f80); margin-right: 2px; }
      .noah-price-chip { padding: 2px 9px; border-radius: 999px; border: 1px solid var(--noah-line-mid, rgba(201,210,122,.18)); background: color-mix(in srgb, var(--noah-accent, #a9b45a) 8%, transparent); font-variant-numeric: tabular-nums; }
      .noah-price-chip b { font-weight: 500; color: var(--noah-bright, #f6f4e6); margin-right: 2px; }
      .noah-prices a { color: var(--noah-accent-soft, #e0e4ad) !important; text-decoration: none; }
      .noah-prices a:hover { text-decoration: underline; }
      .noah-prices-cheaper { flex-basis: 100%; color: var(--noah-accent-bright, #c9d27a); }
      .noah-prices-alt { margin-left: 4px; }
      .noah-prices-source { flex-basis: 100%; font-size: 11px; color: var(--noah-faint, #676d54); }
      /* peek */
      .noah-peek-button { display: inline-flex; align-items: center; gap: 6px; margin: 6px 0 0; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--noah-line-mid); background: transparent; color: var(--noah-muted); font: 12px var(--noah-body); cursor: pointer; transition: color .16s var(--noah-ease), border-color .16s var(--noah-ease); }
      .noah-peek-button:hover { color: var(--noah-bright); border-color: var(--noah-accent); }
      .noah-peek-button.on { color: var(--noah-accent-soft); border-color: var(--noah-accent); }
      .noah-peek { margin: 12px 0 2px; padding: 14px 16px; border-radius: 12px; background: var(--noah-surface2); border: 1px solid var(--noah-line); font: 14px/1.6 var(--noah-body); color: var(--noah-text); animation: noah-arrive .26s var(--noah-ease) both; }
      @keyframes noah-arrive { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
      .noah-peek header { display: flex; gap: 12px; align-items: baseline; margin: 0 0 8px; font: 12px var(--noah-body); color: var(--noah-muted); }
      .noah-peek header b { font: 400 16px var(--noah-display); color: var(--noah-bright); }
      .noah-peek .noah-peek-lead { color: var(--noah-sub); margin: 0 0 10px; }
      .noah-peek .noah-peek-body { display: grid; grid-template-columns: 1fr auto; gap: 16px; }
      .noah-peek .noah-peek-text { max-height: 340px; overflow: auto; padding-right: 8px; scrollbar-gutter: stable; }
      .noah-peek .noah-peek-text p { margin: 0 0 10px; }
      .noah-peek .noah-peek-text h4 { margin: 12px 0 4px; font: 400 15px var(--noah-display); color: var(--noah-bright); }
      .noah-peek img { max-width: 220px; max-height: 160px; object-fit: cover; border-radius: 10px; border: 1px solid var(--noah-line); }
      .noah-peek .noah-peek-foot { margin: 10px 0 0; font-size: 12px; color: var(--noah-faint); }
      .noah-peek .noah-peek-foot a { color: var(--noah-accent-soft); }
      .noah-peek .noah-peek-error { color: var(--noah-muted); }
      @media (prefers-reduced-motion: reduce) { .noah-peek { animation: none; } }
    `);
  }

  function wearLook() {
    if (!state || !state.look || !state.image || !engine.page()) return;
    if (document.getElementById(Z("noah-shield-look"))) return;
    const style = document.createElement("style");
    style.id = Z("noah-shield-look");
    style.textContent = themeCss(state.palette || {}, state.image);
    (document.head || document.documentElement).append(style);
    const layer = document.createElement("div");
    layer.id = Z("noah-shield-look-layer");
    document.documentElement.append(layer);
  }

  // ---- "74": the corner number that unfolds into the message ----------------------------------
  // Kept in its own closed shadow root, so the search engine's styles never
  // touch it and the page cannot read it. Hover, focus or tap to open.
  const MESSAGE_74 = "For our Father, who is the King of Heaven, sends his 10 princes over time to the realm of matter to save his children (who are you, who are mankind, not humanity), for you all are the prodigal son. For God the Father hides himself in all scriptures, in all words, in all of nature and in all books, for his words have been taken into religions, manipulated, and pushed as propaganda onto his children, so that evil can set you arguing over your own wickedness. For \u201call religions are true, and all religions are lies.\u201d Those who need to debate over who is right have lost their way with the divine. To you who are the low-hanging fruit of society: my Father is watching you, for fear has been pushed onto his children. For \u201creligion is just a product tag on humans to fight over\u201d \u2014 who would argue with those words and not see it for themselves? Who would hold to one religion and argue with another that Jesus is superior, when he is one of the 10 princes of Heaven? Hindus and Christians argue over Jesus and Krishna, yet they are the same person with different names. Fools will argue and claim that they hold the truth, but they lack patience and love. There are those who promote my Father, who is in Heaven waiting for you to return, but who lead people back to religion itself instead of to God the Father.";
  function show74() {
    if (!state || !state.look || !engine.page() || document.getElementById(Z("noah-shield-74"))) return;
    const host = document.createElement("div");
    host.id = Z("noah-shield-74");
    const shadow = host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = `
      :host { all: initial; position: fixed; right: clamp(14px, 3vw, 40px); bottom: 58px; z-index: 2147483000; }
      .box { position: relative; outline: none; cursor: default; font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; }
      .num { display: block; font-size: 22px; line-height: 1; letter-spacing: .08em; color: rgba(233,231,214,.62); text-shadow: 0 2px 14px rgba(0,0,0,.7); text-align: right; transition: opacity .35s ease, transform .5s cubic-bezier(.2,.7,.2,1), letter-spacing .5s cubic-bezier(.2,.7,.2,1), filter .35s ease; }
      .text { position: absolute; right: -6px; bottom: -8px; width: min(520px, calc(100vw - 40px)); max-height: min(70vh, 560px); overflow: auto; box-sizing: border-box; margin: 0; padding: 16px 18px 17px; border-radius: 14px; font-style: italic; font-size: 14.5px; line-height: 1.6; color: #ece9d8; background: rgba(9,15,12,.86); border: 1px solid rgba(201,210,122,.16); box-shadow: 0 18px 44px rgba(0,0,0,.55); backdrop-filter: blur(14px) saturate(1.1); -webkit-backdrop-filter: blur(14px) saturate(1.1); opacity: 0; transform: translateY(6px) scale(.97); transform-origin: 100% 100%; clip-path: inset(85% 0 0 85% round 14px); pointer-events: none; transition: opacity .35s ease, transform .55s cubic-bezier(.2,.7,.2,1), clip-path .65s cubic-bezier(.2,.7,.2,1); scrollbar-width: thin; scrollbar-color: rgba(169,180,90,.5) transparent; }
      .w { display: inline-block; opacity: 0; transform: translateY(5px); filter: blur(3px); transition: opacity .4s ease, transform .5s cubic-bezier(.2,.7,.2,1), filter .4s ease; }
      .box:hover .num, .box:focus-visible .num, .box.open .num { opacity: 0; transform: scale(.7) translateY(-4px); letter-spacing: .4em; filter: blur(2px); }
      .box:hover .text, .box:focus-visible .text, .box.open .text { opacity: 1; transform: none; clip-path: inset(0 0 0 0 round 14px); pointer-events: auto; }
      .box:hover .w, .box:focus-visible .w, .box.open .w { opacity: 1; transform: none; filter: none; transition-delay: calc(120ms + var(--i) * 7ms); }
      .box:focus-visible .text { outline: 2px solid #c9d27a; outline-offset: 3px; }
      @media (prefers-reduced-motion: reduce) { .num, .text, .w { transition: opacity .01ms !important; transform: none !important; filter: none !important; clip-path: none !important; } .box:hover .w, .box.open .w, .box:focus-visible .w { transition-delay: 0s !important; } }
    `;
    const box = document.createElement("div");
    box.className = "box";
    box.tabIndex = 0;
    box.setAttribute("role", "button");
    box.setAttribute("aria-expanded", "false");
    box.setAttribute("aria-label", "74: " + MESSAGE_74);
    const num = document.createElement("span");
    num.className = "num";
    num.setAttribute("aria-hidden", "true");
    num.textContent = "74";
    const text = document.createElement("p");
    text.className = "text";
    text.setAttribute("aria-hidden", "true");
    MESSAGE_74.split(" ").forEach((word, index) => {
      const span = document.createElement("span");
      span.className = "w";
      span.style.setProperty("--i", Math.min(index, 140));
      span.textContent = word;
      text.append(span, " ");
    });
    box.append(num, text);
    shadow.append(style, box);
    const set = (open) => { box.classList.toggle("open", open); box.setAttribute("aria-expanded", String(open)); };
    box.addEventListener("click", (event) => { event.stopPropagation(); set(!box.classList.contains("open")); });
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); set(!box.classList.contains("open")); }
      if (event.key === "Escape") { set(false); box.blur(); }
    });
    box.addEventListener("mouseleave", () => set(false));
    document.addEventListener("click", () => set(false));
    document.documentElement.append(host);
  }

  // ---- peek: the page's own words, here, without the visit --------------------------------------
  const peeked = new WeakSet();
  function addPeekButtons() {
    if (!state || !state.peek || !engine.page()) return;
    for (const block of resultBlocks()) {
      if (peeked.has(block) || block.hasAttribute(Z("data-noah-shield")) && block.getAttribute(Z("data-noah-shield")) !== "dim") continue;
      const anchor = firstLink(block);
      if (!anchor) continue;
      const target = targetHost(anchor);
      if (!target || !/^https?:$/.test(new URL(anchor.href, location.href).protocol)) continue;
      peeked.add(block);
      const button = document.createElement("button");
      button.type = "button";
      button.className = Z("noah-peek-button");
      button.textContent = "peek";
      button.title = "Read what this page says, here, without opening it";
      const titleNode = block.querySelector("h3, h2, [data-testid='result-title-a']");
      const parent = titleNode ? titleNode.closest("a") || titleNode : anchor;
      parent.parentElement ? parent.parentElement.insertBefore(button, parent.nextSibling) : block.append(button);
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        togglePeek(block, button, realHref(anchor));
      });
    }
  }

  function realHref(anchor) {
    try {
      const url = new URL(anchor.href, location.href);
      for (const key of ["uddg", "url", "u", "q"]) {
        const inner = url.searchParams.get(key);
        if (inner && /^https?:\/\//.test(inner)) return inner;
      }
      return url.href;
    } catch {
      return anchor.href;
    }
  }

  function textOf(html, url) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    for (const junk of doc.querySelectorAll("script, style, noscript, template, svg, iframe, nav, footer, aside, header, form, [role='navigation'], [role='banner'], [role='contentinfo'], [aria-hidden='true'], .cookie, .cookies, .newsletter, .sidebar, .advert, .ad")) junk.remove();
    const meta = (name) => { const node = doc.querySelector(`meta[property='${name}'], meta[name='${name}']`); return node ? node.getAttribute("content") || "" : ""; };
    const title = (meta("og:title") || (doc.querySelector("title") || {}).textContent || "").trim().slice(0, 160);
    const description = (meta("description") || meta("og:description") || "").trim().slice(0, 400);
    let image = meta("og:image") || meta("twitter:image") || "";
    try { if (image) image = new URL(image, url).href; } catch { image = ""; }
    if (!/^https:/.test(image)) image = "";
    const roots = [doc.querySelector("article"), doc.querySelector("main"), doc.querySelector("[role='main']"), doc.body].filter(Boolean);
    let best = roots[0];
    let bestScore = -1;
    for (const root of roots) {
      const score = Array.from(root.querySelectorAll("p")).reduce((sum, paragraph) => sum + (paragraph.textContent.trim().length > 60 ? paragraph.textContent.trim().length : 0), 0);
      if (score > bestScore) { best = root; bestScore = score; }
    }
    const pieces = [];
    let total = 0;
    for (const node of best.querySelectorAll("h1, h2, h3, p, li")) {
      const text = node.textContent.replace(/\s+/g, " ").trim();
      if (!text) continue;
      const heading = /^H[1-3]$/.test(node.tagName);
      // The page's own heading repeats the title line above the text.
      if (heading && title && text.toLowerCase() === title.toLowerCase()) continue;
      if (!heading && text.length < 50) continue;
      if (node.tagName === "LI" && text.length < 80) continue;
      pieces.push({ heading, text: text.slice(0, 700) });
      total += text.length;
      if (total > 6000 || pieces.length > 40) break;
    }
    const words = Math.round(best.textContent.split(/\s+/).filter(Boolean).length);
    return { title, description, image, pieces, words };
  }

  async function togglePeek(block, button, url) {
    const existing = block.querySelector(Z(".noah-peek"));
    if (existing) { existing.remove(); button.classList.remove("on"); return; }
    button.classList.add("on");
    const panel = document.createElement("div");
    panel.className = Z("noah-peek");
    panel.textContent = "reading…";
    const at = button.closest("a") ? button.closest("a").parentElement : button.parentElement;
    (at && at !== block ? at : block).append(panel);
    const answer = await new Promise((resolve) => api.runtime.sendMessage({ type: "search.peek", url }, (response) => { void api.runtime.lastError; resolve(response || { error: "no answer" }); }));
    panel.replaceChildren();
    if (answer.error) {
      const error = document.createElement("div");
      error.className = Z("noah-peek-error");
      error.textContent = "Could not read it from here: " + answer.error;
      panel.append(error);
      return;
    }
    const page = textOf(answer.html, answer.url || url);
    const head = document.createElement("header");
    const strong = document.createElement("b");
    strong.textContent = page.title || new URL(url).hostname;
    head.append(strong, document.createTextNode(`${new URL(answer.url || url).hostname} · about ${Math.max(1, Math.round(page.words / 230))} min to read`));
    panel.append(head);
    if (page.description) {
      const lead = document.createElement("p");
      lead.className = Z("noah-peek-lead");
      lead.textContent = page.description;
      panel.append(lead);
    }
    const body = document.createElement("div");
    body.className = Z("noah-peek-body");
    const text = document.createElement("div");
    text.className = Z("noah-peek-text");
    for (const piece of page.pieces) {
      const node = document.createElement(piece.heading ? "h4" : "p");
      node.textContent = piece.text;
      text.append(node);
    }
    if (!page.pieces.length) {
      const none = document.createElement("p");
      none.className = Z("noah-peek-error");
      none.textContent = "This page carries its words in scripts, so there is nothing to read without opening it.";
      text.append(none);
    }
    body.append(text);
    if (page.image) {
      const image = document.createElement("img");
      image.src = page.image;
      image.alt = "";
      image.referrerPolicy = "no-referrer";
      image.loading = "lazy";
      body.append(image);
    }
    panel.append(body);
    const foot = document.createElement("div");
    foot.className = Z("noah-peek-foot");
    const open = document.createElement("a");
    open.href = url;
    open.textContent = "open the page";
    open.rel = "noopener noreferrer";
    foot.append("Fetched once, without cookies or your address in a referrer. ", open);
    panel.append(foot);
  }

  // ---- google's own grey panels (ai overview, "show more" fades) -------------------------------
  // Their class names change every few weeks, so they are found by what they
  // look like: an opaque, colourless grey box, or a fade from one. Those are
  // marked and the look's css repaints them in its own surfaces.
  const GREY = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)/g;
  // google greys start near #1f1f1f; the look's own surfaces are darker
  function greyish(r, g, b) { const max = Math.max(r, g, b), min = Math.min(r, g, b); return max - min <= 22 && max >= 24 && max <= 90; }
  function repaintGreys() {
    if (!state || !state.look || !engine.page()) return;
    const scope = document.querySelector("#rcnt") || document.querySelector("#center_col") || document.querySelector("main") || document.body;
    if (!scope) return;
    const nodes = scope.querySelectorAll("div, span, g-expandable-container, g-inner-card, button, [role='button'], a[role='button']");
    let looked = 0;
    for (const el of nodes) {
      if (++looked > 7000) break;
      if (el.getAttribute(Z("data-noah-repaint")) || el.closest(Z("[data-noah-shield], .noah-peek, .noah-prices"))) continue;
      const style = getComputedStyle(el);
      const image = style.backgroundImage;
      if (image && image !== "none" && /gradient/.test(image)) {
        const stops = [...image.matchAll(GREY)];
        if (stops.length && stops.every((m) => greyish(+m[1], +m[2], +m[3]) || (m[4] !== undefined && +m[4] < 0.05))) { el.setAttribute(Z("data-noah-repaint"), "fade"); continue; }
      }
      GREY.lastIndex = 0;
      const color = GREY.exec(style.backgroundColor);
      GREY.lastIndex = 0;
      if (!color) continue;
      const alpha = color[4] === undefined ? 1 : +color[4];
      if (alpha < 0.55 || !greyish(+color[1], +color[2], +color[3])) continue;
      const rect = el.getBoundingClientRect();
      const roundish = parseFloat(style.borderTopLeftRadius) >= Math.min(16, rect.height / 2 - 1);
      if (el.matches("button, [role='button'], a[role='button']") || (roundish && rect.height < 64 && rect.width > 120)) el.setAttribute(Z("data-noah-repaint"), "pill");
      else if (rect.height < 36 && rect.width < 320) el.setAttribute(Z("data-noah-repaint"), "chip");
      else el.setAttribute(Z("data-noah-repaint"), "panel");
    }
  }
  let repaintTimer = null, repaints = 0;
  function repaintSoon() {
    if (repaintTimer || repaints > 40) return;
    repaintTimer = setTimeout(() => { repaintTimer = null; repaints++; try { repaintGreys(); } catch {} }, 500);
  }

  // ---- prices on results: what a site costs, without opening it ------------------------------
  // For the first results of a search, the shield reads each site's own
  // pricing page once (no cookies, cached a week) and shows its plans under the
  // result. Results that both have prices are compared: the cheaper paid
  // options on this same page are named, so the competitors are the ones the
  // search itself found. Prices are what the sites show; nothing is estimated.
  const priced = new WeakSet();
  const pricedSites = new Map(); // site -> { block, answer }
  async function showPrices() {
    if (!state || !state.prices || !engine.page() || engine.id !== "google") return;
    const blocks = Array.from(document.querySelectorAll("#rso .MjjYud, #rso > div > div.g, #rso .g")).filter((block) => block.querySelector("h3") && block.querySelector("a[href^='http']"));
    let asked = 0;
    for (const block of blocks) {
      if (priced.has(block) || asked >= 6 || pricedSites.size >= 8) continue;
      if (block.closest("[data-text-ad], #tads, #bottomads")) continue;
      const link = block.querySelector("a[href^='http']");
      let site;
      try { site = new URL(link.href).hostname.replace(/^www\./, ""); } catch { continue; }
      if (/google\.|youtube\.com|wikipedia\.org|reddit\.com|facebook\.com|instagram\.com|x\.com|twitter\.com|linkedin\.com|quora\.com|medium\.com/.test(site)) { priced.add(block); continue; }
      if ([...pricedSites.values()].some((entry) => entry.site === site)) { priced.add(block); continue; }
      priced.add(block);
      asked++;
      const holder = document.createElement("div");
      holder.className = Z("noah-prices");
      holder.setAttribute(Z("data-noah-shield"), "prices");
      holder.textContent = "checking " + site + " pricing…";
      // inside the result's own card, under its snippet
      const heading = block.querySelector("h3");
      const home = (heading && (heading.closest(".g") || heading.closest(".MjjYud > div"))) || block;
      home.append(holder);
      const entry = { site, block, holder, answer: null };
      pricedSites.set(holder, entry);
      api.runtime.sendMessage({ type: "search.prices", url: link.href }, (answer) => {
        void api.runtime.lastError;
        entry.answer = answer || { error: "no answer" };
        renderPrices();
      });
    }
  }
  function money(value, currency) {
    try { return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD", maximumFractionDigits: value % 1 ? 2 : 0 }).format(value); } catch { return (currency || "$") + value; }
  }
  function renderPrices() {
    const entries = [...pricedSites.values()];
    const paid = entries.filter((e) => e.answer && e.answer.plans && e.answer.plans.some((p) => p.monthly > 0));
    for (const entry of entries) {
      const { holder, answer, site } = entry;
      if (!answer) continue;
      holder.replaceChildren();
      if (answer.error || !answer.plans || !answer.plans.length) {
        if (answer.error === "off") { holder.remove(); continue; }
        holder.className = Z("noah-prices") + " quiet";
        holder.textContent = answer.plans && !answer.plans.length ? "no prices published on " + site + "'s pricing page" : "";
        if (!holder.textContent) holder.remove();
        continue;
      }
      holder.className = Z("noah-prices");
      const label = document.createElement("span");
      label.className = Z("noah-prices-label");
      label.textContent = "pricing";
      holder.append(label);
      for (const plan of answer.plans.slice(0, 5)) {
        const chip = document.createElement("span");
        chip.className = Z("noah-price-chip");
        const name = document.createElement("b");
        name.textContent = plan.name || "plan";
        const cost = plan.price === 0 ? "free" : money(plan.price, answer.currency) + (plan.period ? "/" + plan.period : "");
        if (plan.price === 0 && /^free\b/i.test(plan.name || "")) name.textContent = "free";
        else chip.append(name, " " + cost);
        if (!chip.childNodes.length) chip.append(name);
        holder.append(chip);
      }
      const open = document.createElement("a");
      open.href = answer.url; open.rel = "noopener noreferrer"; open.textContent = "see plans";
      holder.append(open);
      const alt = document.createElement("a");
      alt.className = Z("noah-prices-alt");
      alt.title = "search for competitors of " + site;
      alt.href = "/search?q=" + encodeURIComponent(site.split(".")[0] + " alternatives pricing");
      alt.textContent = "alternatives";
      holder.append(alt);
      const mine = Math.min(...answer.plans.filter((p) => p.monthly > 0).map((p) => p.monthly));
      if (Number.isFinite(mine)) {
        const cheaper = paid.filter((other) => other !== entry && (other.answer.currency || "USD") === (answer.currency || "USD")).map((other) => ({ site: other.site, from: Math.min(...other.answer.plans.filter((p) => p.monthly > 0).map((p) => p.monthly)), url: other.answer.url })).filter((o) => o.from < mine).sort((a, b) => a.from - b.from).slice(0, 3);
        if (cheaper.length) {
          const line = document.createElement("div");
          line.className = Z("noah-prices-cheaper");
          line.append("cheaper on this page: ");
          cheaper.forEach((o, i) => { if (i) line.append(" · "); const a = document.createElement("a"); a.href = o.url; a.rel = "noopener noreferrer"; a.textContent = o.site + " from " + money(o.from, answer.currency) + "/mo"; line.append(a); });
          holder.append(line);
        }
      }

      const source = document.createElement("span");
      source.className = Z("noah-prices-source");
      source.textContent = answer.cached ? "from " + site + "'s pricing page, read " + answer.age : "from " + site + "'s pricing page";
      holder.append(source);
    }
  }

  // A small, satisfying response to typing: the search box breathes a ring of
  // light on each keystroke, and the text settles in with a tiny rise. Done
  // with the Web Animations API, so it leaves no class or style on the page to
  // fingerprint, and it honours "reduce motion".
  let typingWired = false;
  let typingInput = null;
  function wireTyping() {
    if (typingWired || !state || !state.look || !engine.page()) return;
    const t = (engine && THEME[engine.id]) || null;
    const box = t && t.searchBox ? document.querySelector(t.searchBox) : null;
    const input = (t && t.searchInput ? document.querySelector(t.searchInput) : null) || document.querySelector("input[name='q'], textarea[name='q']");
    if (!input) return;
    typingWired = true;
    typingInput = input;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let last = 0;
    input.addEventListener("input", () => {
      if (reduce) return;
      const now = performance.now();
      if (now - last < 45) return; // never fight fast typing
      last = now;
      const target = box || input;
      try {
        target.animate(
          [{ boxShadow: "0 10px 36px rgba(0,0,0,.4), 0 0 0 2px color-mix(in srgb, var(--" + (window.__nt || "noah") + "-accent-bright, #c9d27a) 60%, transparent)" },
           { boxShadow: "0 10px 36px rgba(0,0,0,.4), 0 0 0 7px color-mix(in srgb, var(--" + (window.__nt || "noah") + "-accent, #a9b45a) 0%, transparent)" }],
          { duration: 420, easing: "cubic-bezier(.2,.7,.2,1)" }
        );
      } catch {}
    }, { passive: true });
  }

  function start() {
    ensureStyle();
    sweep();
    wearLook();
    show74();
    wireTyping();
    repaintSoon();
    showPrices();
    const observer = new MutationObserver(() => {
      clearTimeout(start.timer);
      start.timer = setTimeout(() => { sweep(); repaintSoon(); showPrices(); if (typingWired && !document.contains(typingInput)) typingWired = false; wireTyping(); }, 400);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    // Engines that stay on one page while the query changes.
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href === lastUrl) return;
      lastUrl = location.href;
      counts = { paid: 0, farms: 0, dimmed: 0 };
      reported = { paid: 0, farms: 0, dimmed: 0 };
      const old = document.getElementById(Z("noah-shield-look"));
      if (old) { old.remove(); const layer = document.getElementById(Z("noah-shield-look-layer")); if (layer) layer.remove(); }
      sweep();
      wearLook();
      repaints = 0;
      pricedSites.clear();
      repaintSoon();
      showPrices();
    }, 700);
  }

  api.runtime.sendMessage({ type: "search.state" }, (response) => {
    void api.runtime.lastError;
    // Look turned out to be off: undo the early paint and stop.
    if (!response || response.error || !response.look) {
      for (const id of [Z("noah-shield-base"), Z("noah-shield-look"), Z("noah-shield-look-layer"), Z("noah-shield-74")]) { const el = document.getElementById(id); if (el) el.remove(); }
    }
    if (!response || response.error || !(response.clean || response.farms || response.look || response.peek || response.prices)) return;
    state = response;
    if (document.body) start();
    else document.addEventListener("DOMContentLoaded", start, { once: true });
  });
})();
