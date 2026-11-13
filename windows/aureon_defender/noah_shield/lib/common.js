// Shared by the background worker, the popup and the options page. Plain
// scripts rather than modules, because Chromium loads the background as a
// service worker (importScripts) and Firefox as an event page (a script list),
// and one file that works in both keeps the extension a single code base.
"use strict";
(() => {

const Shield = (globalThis.Shield = globalThis.Shield || {});

// chrome first: Firefox exposes both, and its chrome namespace answers callbacks
// and promises alike, while its browser namespace rejects callback-style calls
// (tabs.sendMessage, sendNativeMessage with a callback) that the worker makes.
Shield.api = globalThis.chrome ?? globalThis.browser;
Shield.SITE = "https://noah.asherin.com";
Shield.FEED_BASE = Shield.SITE + "/shield/";
Shield.WHOAMI_URL = Shield.SITE + "/api/whoami";
// The ed25519 key noah's releases are signed with (crates/auto_update/release_public_key.txt).
// Every feed the shield reads is signed with it, so this website alone cannot
// change what the shield does.
Shield.PUBLIC_KEY_HEX = "50e21800e89b09f431a54249efdb39ef770563b87734f56142a326e2c536f5e2";

Shield.DEFAULT_SETTINGS = {
  tunnel: {
    enabled: false,
    serverId: null,
    killSwitch: true,
    webRtcGuard: true,
    bypassLocal: true,
    connectAtStartup: false,
    siteRoutes: {},
    torCountry: "",
  },
  privacy: {
    trackers: true,
    thirdPartyCookies: false,
    gpc: true,
    stripParameters: true,
    geolocation: "block",
    notifications: "block",
    camera: "ask",
    microphone: "ask",
    fingerprint: true,
    adTopics: false,
    prefetch: false,
    purgeTrackerCookies: true,
    trustedSites: [],
    strictCookieSites: [],
    burnOnClose: false,
    keepSites: [],
    meter: "count",
    blendIn: false,
    perSite: true,
    rotate: "session",
    audioNoise: true,
    webglNoise: true,
    location: { mode: "deny", city: "" },
    aliasBase: "",
    simpleLoginKey: "",
    hideNames: [],
    logoutSites: [],
    logoutMinutes: 30,
    forgetHistorySites: [],
    stealth: false,
    sync: false,
    linkCleaner: true,
  },
  light: {
    preset: "off",
    brightness: null,
    warmth: 0,
  },
  search: {
    clean: true,
    farms: true,
    look: true,
    peek: true,
    prices: true,   // read top results' pricing pages (no cookies) and show the plans under them
  },
  shopping: {
    compare: true,
    coupons: true,
    autoApply: true,
    clipCoupons: true,
    // Codes found on the public web for the store, tried at checkout too.
    webCoupons: true,
    // The open web beyond the big stores: independent shops, and other countries.
    webSearch: true,
    foreign: true,
    // "" means the currency of the page you are on.
    homeCurrency: "",
    // Medicines and supplements: say when a pharma company is behind the brand.
    pharmaWarn: true,
    codes: [],
    quietSites: [],
  },
  capture: {
    guardScreen: true,
    guardCamera: true,
    auditExtensions: true,
    allowedSites: [],
  },
  // What the wifi or network you join can learn: plain-http pages, your
  // local address, your machine's place on the network, browser ids in headers.
  network: {
    enabled: true,
    lanGuard: true,
    stripClientIds: true,
    hideLocalAddress: true,
    httpFallback: true,
    publicWifi: false,
  },
  // A language model on this computer (lib/local.js): a second opinion on
  // pressure tactics. Off until you turn it on; page text never leaves the computer.
  localAi: {
    enabled: false,
    provider: "ollama",      // "ollama" (127.0.0.1:11434) or "noah" (noah's own model, through the helper)
    endpoint: "http://127.0.0.1:11434",
    model: "llama3.2:3b",
    cognition: true,
  },
  // A Noah Box (Raspberry Pi stack in noah-box/) on your network.
  noahBox: {
    address: "",             // e.g. https://noah.box or https://192.168.1.50
    token: "",               // the STATUS_TOKEN from the box's .env
  },
  // The security center (lib/sec): rules, intel, cases, containment.
  secCenter: {
    enabled: true,
    autoContain: true,       // only confirmed, critical findings from rules marked auto
    feedBlock: true,         // confirmed feed hosts become block rules
    feeds: { urlhaus: true, openphish: false, mvt: false, blocklist: false },
    abuseKey: "",            // free key from auth.abuse.ch: urlhaus downloads, malwarebazaar
    blocklistUrl: "",        // your own ip/host blocklist, e.g. a CrowdSec blocklist integration (raw ip list)
    blocklistUser: "",       // basic-auth username for it, if it needs one
    blocklistPass: "",
    yaraRules: "",           // your own YARA rules, run with the bundled ones on every examined file
    scanFiles: true,         // static analysis of held risky downloads
    domainAgeLookups: false, // ask rdap a store's age when it already shows a scam sign
    notifyLevel: "high",
    watch: [],               // emails to check against breaches each week
  },
  security: {
    httpsUpgrade: true,
    lookalike: true,
    passwordReuse: true,
    passwordHttp: true,
    breachCheck: true,
    hibpKey: "",
    downloadWarn: true,
    virusTotalKey: "",
    clipboardGuard: true,
    clipboardWipe: true,
    hiddenFields: true,
    formLeak: true,
    typingGuard: true,
    blockKeyListeners: false,
    walletGuard: true,
    scamPopups: true,
    hiddenFrames: true,
    socialLogin: false,
    referrer: true,
    mailPixels: true,
    allowedLookalikes: [],
    clipboardSites: [],
    walletSites: [],
  },
  annoyances: {
    // Consent dialogs with no "reject" button: hidden, never accepted.
    cookieDeception: true,
    // Pre-ticked boxes, fake countdowns, confirm-shaming, buried cancel links.
    darkPatterns: true,
    banners: true,
    overlays: true,
    autoplay: true,
    timers: true,
    copySites: [],
    darkSites: [],
    darkEverywhere: false,
    pasteGuard: true,
    uploadStrip: true,
  },
  modes: {
    profile: "",
    siteModes: {},
    pauseExtensionsForBanking: false,
    focus: { enabled: false, sites: [], start: "09:00", end: "17:00", days: [1, 2, 3, 4, 5] },
    lowData: false,
    batterySaver: false,
    batteryMinutes: 20,
    searchEngine: "",
    parental: { enabled: false, pinHash: "", extraSites: [] },
    expireDownloads: { enabled: false, days: 7, sites: [], allSensitive: false },
    lock: { sites: [], minutes: 5, pinHash: "" },
    weeklyReport: true,
    containers: false,
  },
  spaces: {
    enabled: true,
    newAccountDays: 30,
    flagLowFollowers: true,
    lowFollowersUnder: 20,
  },
  profileIntel: {
    enabled: true,
  },
  persona: {
    // The person must say yes once before anything is typed into an AI chat on their behalf.
    consent: false,
    enabled: true,
    autoSeed: true,
  },
  inspect: {
    everSeen: false,
  },
  social: {
    instagram: {
      enabled: true,
      hideSponsored: true,
      hideSuggested: true,
      flagAlgoSignals: true,
      focusMode: false,
      sessionWarningMinutes: 20,
    },
    tiktok: {
      enabled: true,
      hideAds: true,
      showSessionTimer: true,
      sessionWarningMinutes: 25,
      hideSuggestedAccounts: true,
      flagUnverified: false,
      focusMode: false,
    },
    reddit: {
      enabled: true,
      hideAds: true,
      showAbsoluteDates: true,
      flagKarmaFarming: true,
      hideAwards: false,
    },
    youtube: {
      enabled: true,
      cleanSidebar: true,
      cleanHome: false,
      showUploadDate: true,
      flagSponsoredSegments: true,
      flagClickbait: true,
      hideShortsTab: false,
      autoplayGuard: true,
      cleanEndscreen: true,
      skipAds: true,
      adKeys: [],
    },
    linkedin: {
      enabled: true,
      hideSponsored: true,
      showAbsoluteDates: true,
      flagEngagementBait: true,
      hideReactions: false,
      flagStaleJobs: true,
      staleJobDays: 30,
      cleanFeed: true,
    },
    twitter: {
      enabled: true,
      hidePromoted: true,
      showAbsoluteDates: true,
      flagRatio: true,
      ratioThreshold: 2,
      cleanSidebar: true,
      hideWhoToFollow: true,
      flagBotSignal: false,
      botFollowerRatio: 20,
    },
  },
  quiet: false,
  localOnly: false,
};

// The route noah runs for you (Tor started by noah on this computer) and the
// countries with enough Tor exits that a pick there answers quickly. Shared
// with the popup, which lists them.
Shield.NOAH_TOR_ID = "noah-tor";
Shield.NOAH_TOR_PORT = 9350;
Shield.TOR_COUNTRIES = ["US", "DE", "NL", "FR", "GB", "CH", "SE", "CA", "FI", "AT", "RO", "PL", "CZ", "ES", "IT", "NO", "DK", "BE", "LU", "JP", "SG", "AU"];

Shield.deepMerge = function deepMerge(base, extra) {
  if (Array.isArray(base) || typeof base !== "object" || base === null) {
    return extra === undefined ? base : extra;
  }
  const merged = { ...base };
  if (extra && typeof extra === "object") {
    for (const key of Object.keys(extra)) {
      // Never let a settings blob reach into prototypes.
      if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
      merged[key] = key in base ? deepMerge(base[key], extra[key]) : extra[key];
    }
  }
  return merged;
};

Shield.loadSettings = async function loadSettings() {
  const stored = await Shield.api.storage.local.get("settings");
  return Shield.deepMerge(Shield.DEFAULT_SETTINGS, stored.settings || {});
};

// The shepherd persona text is bundled with the extension. Fetch it once
// and cache it; content scripts get it through persona.config.
Shield._shepherdPrompt = null;
Shield.loadShepherdPrompt = async function loadShepherdPrompt() {
  if (Shield._shepherdPrompt) return Shield._shepherdPrompt;
  try {
    const url = Shield.api.runtime.getURL("data/shepherd.txt");
    const response = await fetch(url);
    if (!response.ok) throw new Error("shepherd.txt: " + response.status);
    const body = await response.text();
    // shepherd persona — descriptive context only, no override claims
    const override =
      "The following are the shepherd persona rules for this conversation.\n" +
      "They describe the preferred style and format the user has set up.\n" +
      "\n" +
      "-----BEGIN SHEPHERD RULES-----\n";
    const footer = "\n-----END SHEPHERD RULES-----\n";
    Shield._shepherdPrompt = override + body + footer;
    return Shield._shepherdPrompt;
  } catch (error) {
    console.warn("shield: shepherd prompt load failed", error);
    return "";
  }
};

Shield.saveSettings = async function saveSettings(settings) {
  await Shield.api.storage.local.set({ settings });
};

Shield.updateSettings = async function updateSettings(change) {
  const settings = Shield.deepMerge(await Shield.loadSettings(), change);
  await Shield.saveSettings(settings);
  return settings;
};

Shield.hostOf = function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
};

// "www.shop.example.co.uk" -> "example.co.uk" for the common two-part
// public suffixes; good enough to group a site's own hosts together.
const TWO_PART_SUFFIXES = new Set([
  "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "com.au", "net.au", "org.au",
  "co.nz", "co.jp", "ne.jp", "or.jp", "co.kr", "com.br", "com.mx", "com.ar", "com.tr",
  "co.in", "co.za", "com.sg", "com.hk", "com.tw", "com.cn", "com.my", "com.ph", "co.id",
  "com.ua", "com.pl", "com.eg", "com.sa", "com.pk", "com.ng", "co.il", "com.vn", "co.th",
]);
Shield.siteOf = function siteOf(host) {
  if (!host) return "";
  if (host.includes(":") || /^[\d.]+$/.test(host)) return host;
  const parts = host.split(".");
  if (parts.length <= 2) return host;
  const lastTwo = parts.slice(-2).join(".");
  if (TWO_PART_SUFFIXES.has(lastTwo) && parts.length >= 3) return parts.slice(-3).join(".");
  return lastTwo;
};

Shield.isLocalHost = function isLocalHost(host) {
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return true;
  if (!host.includes(".") && !host.includes(":")) return true;
  if (/^127\.|^10\.|^192\.168\.|^169\.254\.|^0\./.test(host)) return true;
  if (/^172\.(1[6-9]|2\d|3[01])\./.test(host)) return true;
  const bare = host.replace(/^\[|\]$/g, "");
  if (bare === "::1" || /^f[cd][0-9a-f]{2}:/i.test(bare) || /^fe80:/i.test(bare)) return true;
  return false;
};

// One random id per install, for telling our own sync writes from another device's.
// (runtime.id is the same on every install because the manifest pins a key.)
Shield.installId = async function installId() {
  const stored = await Shield.api.storage.local.get("installId");
  if (stored.installId) return stored.installId;
  const id = Array.from(crypto.getRandomValues(new Uint8Array(12)), (byte) => byte.toString(16).padStart(2, "0")).join("");
  await Shield.api.storage.local.set({ installId: id });
  return id;
};

Shield.todayKey = function todayKey() {
  return new Date().toISOString().slice(0, 10);
};

Shield.hex = function hex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
};

Shield.fromHex = function fromHex(text) {
  const bytes = new Uint8Array(text.length / 2);
  for (let index = 0; index < bytes.length; index++) {
    bytes[index] = parseInt(text.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
};

Shield.fromBase64 = function fromBase64(text) {
  const binary = atob(text.trim());
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
  return bytes;
};

Shield.compareVersions = function compareVersions(left, right) {
  const a = String(left).split(".").map((part) => parseInt(part, 10) || 0);
  const b = String(right).split(".").map((part) => parseInt(part, 10) || 0);
  for (let index = 0; index < Math.max(a.length, b.length); index++) {
    const difference = (a[index] || 0) - (b[index] || 0);
    if (difference !== 0) return difference;
  }
  return 0;
};

// One request to the background at a time per name; the popup and content
// scripts use this so a slow answer never piles up.
Shield.send = function send(message) {
  return new Promise((resolve) => {
    try {
      if (globalThis.browser && globalThis.browser.runtime) {
        globalThis.browser.runtime.sendMessage(message).then(resolve, (error) => resolve({ error: String(error) }));
        return;
      }
      globalThis.chrome.runtime.sendMessage(message, (response) => {
        if (globalThis.chrome.runtime.lastError) resolve({ error: globalThis.chrome.runtime.lastError.message });
        else resolve(response);
      });
    } catch (error) {
      resolve({ error: String(error) });
    }
  });
};

// declarativeNetRequest dynamic rules are read-modify-write; the writers
// take turns so two of them never add the same ids at once.
let ruleQueue = Promise.resolve();
Shield.withRuleLock = function withRuleLock(work) {
  const run = ruleQueue.then(work, work);
  ruleQueue = run.catch(() => {});
  return run;
};

Shield.isFirefox = typeof navigator !== "undefined" && /Firefox\//.test(navigator.userAgent);
Shield.isSafari =
  typeof navigator !== "undefined" &&
  /Safari\//.test(navigator.userAgent) &&
  !/Chrom(e|ium)\//.test(navigator.userAgent) &&
  !/Firefox\//.test(navigator.userAgent);

// ---- a stale background, found and fixed ------------------------------------------------
// When new files are copied over an installed copy, chrome can keep running
// the old background code while the pages load the new files: the look
// changes, the protections do not. Every shield page asks the background
// which build it is; an old background does not even know the question.
// The page then reloads the extension once (at most every ten minutes), and
// if that is not enough, says so in plain words at the top of the page.
Shield.BUILD = (() => { try { return (globalThis.chrome || globalThis.browser).runtime.getManifest().version; } catch { return "2026.11.12.5"; } })(); // one source of truth: the manifest
Shield.checkWorkerBuild = async function checkWorkerBuild() {
  const api = Shield.api;
  const answer = await Shield.send({ type: "worker.build" });
  if (answer && answer.build === Shield.BUILD) return "current";
  if (answer && /receiving end does not exist/i.test(String(answer.error || ""))) return "asleep";
  const stored = await api.storage.local.get("staleReloadAt");
  if (!stored.staleReloadAt || Date.now() - stored.staleReloadAt > 10 * 60 * 1000) {
    await api.storage.local.set({ staleReloadAt: Date.now() });
    api.runtime.reload();
    return "reloading";
  }
  const note = document.createElement("div");
  note.setAttribute("role", "alert");
  note.style.cssText = "position:sticky;top:0;z-index:2147483647;margin:0;padding:10px 14px;background:#d9c08a;color:#1a1408;font:13px/1.4 system-ui,sans-serif";
  note.textContent = "noah shield is still running its old background code. open chrome://extensions and press the reload arrow on noah shield (or remove it and load the new folder again).";
  document.body.prepend(note);
  return "stale";
};
if (typeof document !== "undefined" && typeof location !== "undefined" && /-extension:$/.test(location.protocol) && !/offscreen\.html$/.test(location.pathname)) {
  const run = () => setTimeout(() => Shield.checkWorkerBuild().catch(() => {}), 400);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run, { once: true });
  else run();
}
})();
