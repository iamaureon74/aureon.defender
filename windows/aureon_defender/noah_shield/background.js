// The background of noah shield. Chromium runs it as a service worker and
// pulls the pieces in with importScripts; Firefox lists the same files in the
// manifest and runs them as one event page.
"use strict";

if (typeof importScripts === "function") {
  importScripts("lib/common.js", "lib/feeds.js", "lib/host.js", "lib/tunnel.js", "lib/privacy.js", "lib/watch.js", "lib/shopping.js", "lib/market.js", "lib/pharma.js", "lib/brands.js", "lib/safety.js", "lib/owners.js", "lib/cities.js", "lib/tracking.js", "lib/tools.js", "lib/look.js", "lib/network.js", "lib/sec/events.js", "lib/sec/rules.js", "lib/sec/intel.js", "lib/sec/graph.js", "lib/sec/cases.js", "lib/sec/filescan.js", "lib/sec/yara.js", "lib/sec/center.js", "lib/sec/audit.js", "lib/sec/vectors.js", "lib/media/clean.js", "lib/pricing.js", "lib/local.js");
}

const api = Shield.api;
const ALARMS = { feeds: 6 * 60, cookies: 12 * 60, tunnel: 10 };

async function applyAll(reason) {
  const settings = await Shield.loadSettings();
  await Shield.applyPrivacy(settings);
  await Shield.applyTunnel(settings);
  await Shield.applyHeaderRules(settings);
  await Shield.applyNetwork(settings).catch((error) => console.warn("shield: network", error));
  await applyModes(settings);
  if (reason === "install" || reason === "startup") {
    await Shield.refreshFeeds();
    const status = await Shield.updateStatus();
    if (status.newer) await noteUpdate(status);
  }
}

Shield.notifyUser = (...args) => notify(...args);
async function notify(id, title, message) {
  // Every notice is in the log too, so one that flashed by can be read again.
  await Shield.log({ kind: "notice", text: title, detail: message });
  const settings = await Shield.loadSettings();
  if (settings.quiet || !api.notifications) return;
  try {
    await api.notifications.create(id, { type: "basic", iconUrl: "icons/128.png", title, message });
  } catch {
    // A browser that refuses notifications is not worth failing over.
  }
}

function openLog(filter = {}) {
  const query = new URLSearchParams(Object.entries(filter).filter(([, value]) => value)).toString();
  return api.tabs.create({ url: api.runtime.getURL("log.html") + (query ? "?" + query : "") });
}

async function noteUpdate(status) {
  const stored = await api.storage.local.get("updateNoted");
  if (stored.updateNoted === status.latest) return;
  await api.storage.local.set({ updateNoted: status.latest });
  await notify("shield-update", "noah shield " + status.latest + " is out", "You run " + status.running + ". Open the shield to get it.");
}

if (api.notifications && api.notifications.onClicked) {
  api.notifications.onClicked.addListener((id) => {
    (async () => {
      const session = await api.storage.session.get("reminderLinks");
      const url = (session.reminderLinks || {})[id];
      if (url && /^https?:\/\//.test(url)) await api.tabs.create({ url });
      else await openLog();
      api.notifications.clear(id);
    })().catch(() => {});
  });
}

api.runtime.onInstalled.addListener((details) => {
  applyAll("install").catch((error) => console.error("shield: install", error));
  if (details.reason === "install") {
    api.tabs.create({ url: Shield.SITE + "/shield?installed" }).catch?.(() => {});
  }
});
api.runtime.onStartup.addListener(() => {
  (async () => {
    const settings = await Shield.loadSettings();
    if (settings.tunnel.connectAtStartup && settings.tunnel.serverId && !settings.tunnel.enabled) {
      await Shield.updateSettings({ tunnel: { enabled: true } });
    }
    await applyAll("startup");
  })().catch((error) => console.error("shield: startup", error));
});

// Alarms are created once; recreating them on every worker start would push
// each period back to "from now", and the weekly report would never arrive.
const ALARM_PLANS = {
  feeds: { periodInMinutes: ALARMS.feeds },
  cookies: { delayInMinutes: 2, periodInMinutes: ALARMS.cookies },
  tunnel: { periodInMinutes: ALARMS.tunnel },
  watchlist: { delayInMinutes: 30, periodInMinutes: 6 * 60 },
  battery: { periodInMinutes: 5 },
  focus: { periodInMinutes: 1 },
  weekly: { delayInMinutes: 24 * 60, periodInMinutes: 7 * 24 * 60 },
  secFeeds: { delayInMinutes: 1, periodInMinutes: 6 * 60 },
  secIdentity: { delayInMinutes: 60, periodInMinutes: 7 * 24 * 60 },
  secSync: { delayInMinutes: 10, periodInMinutes: 60 },
};
(async () => {
  for (const [name, plan] of Object.entries(ALARM_PLANS)) {
    try {
      const existing = await api.alarms.get(name);
      if (!existing || existing.periodInMinutes !== plan.periodInMinutes) await api.alarms.create(name, plan);
    } catch {
      api.alarms.create(name, plan);
    }
  }
})();

// The watchlist alarm runs in a worker that may have restarted; the notifier is re-attached on every start.
Shield._watchlistNotify = (entry, from, to) => announceDrop(entry, from, to);
async function announceDrop(entry, from, to) {
  await notify("shield-drop-" + entry.key, "Price drop: " + entry.title.slice(0, 60), `${from} → ${to}. Open the shield's purchases page for the link.`);
}
api.alarms.onAlarm.addListener((alarm) => {
  (async () => {
    const settings = await Shield.loadSettings();
    if (alarm.name === "secFeeds") { await Shield.sec.refreshFeeds(settings); return; }
    if (alarm.name === "secIdentity") { if (settings.secCenter.watch.length) await Shield.sec.checkIdentities(settings); return; }
    if (alarm.name === "secSync") { if (settings.privacy.sync) await Shield.sec.syncIndicators().catch(() => {}); return; }
    if (alarm.name === "feeds") {
      await Shield.refreshFeeds();
      const status = await Shield.updateStatus();
      if (status.newer) await noteUpdate(status);
      if (settings.tunnel.enabled) await Shield.applyTunnel(settings);
    } else if (alarm.name === "cookies") {
      await Shield.purgeTrackerCookies(settings);
    } else if (alarm.name === "battery") {
      await Shield.discardIdleTabs(settings);
    } else if (alarm.name === "focus") {
      if (settings.modes.focus.enabled) await Shield.applyFocusHours(settings);
    } else if (alarm.name === "weekly") {
      if (settings.modes.weeklyReport) {
        const report = await Shield.weeklyReport();
        await notify("shield-weekly", "Your week with noah shield", report.text);
      }
    } else if (alarm.name.startsWith("expire-")) {
      const entry = await Shield.expireDownload(alarm.name.slice("expire-".length));
      if (entry) await notify(alarm.name, "A download expired", entry.name + " from " + entry.source + " was deleted as you asked.");
    } else if (alarm.name === "watchlist") {
      if (!settings.localOnly) await Shield.checkWatchlist(announceDrop);
    } else if (alarm.name.startsWith("reminder-")) {
      const reminder = await Shield.dueReminder(alarm.name);
      if (reminder) {
        const session = await api.storage.session.get("reminderLinks");
        const reminderLinks = session.reminderLinks || {};
        reminderLinks[reminder.id] = reminder.url;
        await api.storage.session.set({ reminderLinks });
        await notify(reminder.id, reminder.kind === "trial" ? "A trial is about to charge" : reminder.kind === "warranty" ? "A warranty is ending" : "You asked to be reminded", reminder.label + " (press to open)");
      }
    } else if (alarm.name === "tunnel" && settings.tunnel.enabled) {
      const before = await Shield.tunnelStatus();
      const after = await Shield.applyTunnel(settings);
      if (after.state === "held" && before.state !== "held") {
        await notify("shield-held", "The tunnel is holding your traffic", after.error + ". Nothing leaves until the server answers or you turn the tunnel off.");
      }
    }
  })().catch((error) => console.error("shield: alarm", alarm.name, error));
});

// Settings changed anywhere (popup, options, another window): apply again.
// Settings changes are applied one after another, each against the newest
// settings, so a slow earlier change cannot undo a later one with stale values.
let settingsQueue = Promise.resolve();
api.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !changes.settings) return;
  const before = changes.settings.oldValue || {};
  const after = changes.settings.newValue || {};
  settingsQueue = settingsQueue.then(async () => {
    const settings = await Shield.loadSettings();
    if (JSON.stringify(before.privacy) !== JSON.stringify(after.privacy) || JSON.stringify(before.security) !== JSON.stringify(after.security)) await Shield.applyPrivacy(settings);
    if (JSON.stringify(before.tunnel) !== JSON.stringify(after.tunnel)) await Shield.applyTunnel(settings);
    await Shield.applyHeaderRules(settings);
    await Shield.applyNetwork(settings).catch((error) => console.warn("shield: network", error));
    if (JSON.stringify(before.modes) !== JSON.stringify(after.modes)) await applyModes(settings);
    await Shield.pushSync(settings).catch((error) => console.warn("shield: sync", error));
  }).catch((error) => console.error("shield: settings", error));
});

// Requests the rulesets stopped show up here; that is the badge count.
// Counted in batches: one storage write per blocked request made busy pages
// (hundreds of trackers) queue thousands of writes in the worker.
const blockedBatch = new Map();
let blockedBatchTimer = null;
function queueBlockedCount(kind, tabId) {
  const key = kind + "|" + tabId;
  blockedBatch.set(key, (blockedBatch.get(key) || 0) + 1);
  if (blockedBatchTimer) return;
  blockedBatchTimer = setTimeout(() => {
    blockedBatchTimer = null;
    const batch = Array.from(blockedBatch.entries());
    blockedBatch.clear();
    for (const [entry, amount] of batch) {
      const [batchKind, batchTab] = entry.split("|");
      Shield.count(batchKind, amount, Number(batchTab)).catch(() => {});
    }
  }, 400);
}
if (api.webRequest && api.webRequest.onErrorOccurred) {
  api.webRequest.onErrorOccurred.addListener(
    (details) => {
      if (details.error !== "net::ERR_BLOCKED_BY_CLIENT" && details.error !== "NS_ERROR_ABORT") return;
      if (details.type === "main_frame") return;
      const lan = Boolean(Shield.PRIVATE_HOST_RE && Shield.PRIVATE_HOST_RE.test(details.url));
      queueBlockedCount(lan ? "lan" : "trackers", details.tabId);
      secSeen(details.tabId, (lan ? details.url : Shield.hostOf(details.url)), () => Shield.sec.record("blocked", { tab: details.tabId, url: details.url, data: { lan, type: details.type, pageSite: secPageSite.get(details.tabId) || "" } }));
      if (details.tabId >= 0) Shield.noteBlocked(details.tabId, details.url, details.type).catch(() => {});
      const tabSite = Shield.siteOf(Shield.hostOf(details.initiator || details.documentUrl || ""));
      if (tabSite) Shield.noteThirdParty(details.tabId, tabSite, Shield.hostOf(details.url), true).catch(() => {});
    },
    { urls: ["<all_urls>"] },
  );
}

if (api.webRequest && api.webRequest.onAuthRequired) {
  try {
    api.webRequest.onAuthRequired.addListener((details) => Shield.proxyCredentials(details), { urls: ["<all_urls>"] }, ["blocking"]);
  } catch (error) {
    console.warn("shield: proxy credentials unavailable", error);
  }
}

if (api.webNavigation) {
  api.webNavigation.onCommitted.addListener((details) => {
    if (details.frameId === 0) {
      Shield.resetTabCount(details.tabId).catch(() => {});
      Shield.forgetBlocked(details.tabId).catch(() => {});
      secNavCommitted(details).catch(() => {});
    }
    if (/^https?:/.test(details.url || "")) hideAds(details).catch(() => {});
  });
}

// ---- the sound host ----------------------------------------------------------------------------
// Chrome plays through an offscreen document that lives as long as the sound;
// Firefox has none, so the tools page hosts the sound there.
async function toneHost(message, create = true) {
  if (api.offscreen) {
    const contexts = api.runtime.getContexts ? await api.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] }) : [];
    if (!contexts.length) {
      if (!create) return { playing: false };
      await api.offscreen.createDocument({ url: "offscreen.html", reasons: ["AUDIO_PLAYBACK"], justification: "plays the frequency the person chose under their videos" });
    }
    const state = await new Promise((resolve) => api.runtime.sendMessage({ target: "tone-host", ...message }, (response) => { void api.runtime.lastError; resolve(response || {}); }));
    if (message.action === "stop" && api.offscreen.closeDocument) await api.offscreen.closeDocument().catch(() => {});
    return state;
  }
  const url = api.runtime.getURL("tools.html");
  let [tab] = await api.tabs.query({ url });
  if (!tab) {
    if (!create) return { playing: false };
    tab = await api.tabs.create({ url, active: false });
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return new Promise((resolve) => api.tabs.sendMessage(tab.id, { target: "tone-host", ...message }, (response) => { void api.runtime.lastError; resolve(response || {}); }));
}

// Firefox wears the look on its frame; elsewhere the pages and the new tab do.
async function wearLook(look) {
  if (!api.theme || !api.theme.update) return;
  try {
    if (look) await api.theme.update(Shield.themeFromPalette(look.palette));
    else if (api.theme.reset) await api.theme.reset();
  } catch (error) {
    console.warn("shield: theme", error);
  }
}

// ---- ad slots ---------------------------------------------------------------------------------
// The network rules stop ad requests; what the page reserved for them (the
// boxes, the "sponsored" rails) is hidden with EasyList's element rules: one
// stylesheet of generic selectors on every page, plus the site's own.
let cosmeticTable = null;
async function siteHidingCss(host) {
  if (!cosmeticTable) {
    const response = await fetch(api.runtime.getURL("rules/cosmetic.json"));
    cosmeticTable = await response.json();
  }
  const labels = host.split(".");
  const allowed = new Set();
  const selectors = [];
  for (let index = 0; index < labels.length - 1; index++) {
    const domain = labels.slice(index).join(".");
    for (const selector of cosmeticTable.allow[domain] || []) allowed.add(selector);
  }
  for (let index = 0; index < labels.length - 1; index++) {
    const domain = labels.slice(index).join(".");
    for (const selector of cosmeticTable.hide[domain] || []) if (!allowed.has(selector)) selectors.push(selector);
  }
  if (!selectors.length) return "";
  const rules = [];
  for (let start = 0; start < selectors.length; start += 250) {
    rules.push(":is(" + selectors.slice(start, start + 250).join(", ") + ") { display: none !important; }");
  }
  return rules.join("\n");
}

async function hideAds(details) {
  if (!api.scripting || !api.scripting.insertCSS) return;
  const settings = await Shield.loadSettings();
  if (!settings.privacy.trackers) return;
  const host = Shield.hostOf(details.url);
  if (settings.privacy.trustedSites.includes(Shield.siteOf(host))) return;
  const target = { tabId: details.tabId, frameIds: [details.frameId] };
  const insert = async (what) => {
    try {
      await api.scripting.insertCSS({ target, origin: "USER", ...what });
    } catch {
      // Firefox has no USER origin for extension pages' styles; the sheet still applies.
      await api.scripting.insertCSS({ target, ...what }).catch(() => {});
    }
  };
  await insert({ files: ["rules/cosmetic.css"] });
  const css = await siteHidingCss(host);
  if (css) await insert({ css });
}
api.tabs.onRemoved.addListener((tabId) => {
  Shield.resetTabCount(tabId).catch(() => {});
  Shield.forgetBlocked(tabId).catch(() => {});
  api.storage.session.get("mediaTabs").then((session) => {
    const mediaTabs = session.mediaTabs || {};
    if (mediaTabs[tabId]) { delete mediaTabs[tabId]; return api.storage.session.set({ mediaTabs }); }
    return null;
  }).catch(() => {});
  Shield.loadSettings().then((settings) => Shield.tabClosed(tabId, settings)).catch(() => {});
});

const proxyErrors = api.proxy && (api.proxy.onProxyError || api.proxy.onError);
if (proxyErrors) {
  proxyErrors.addListener((details) => {
    api.storage.session.set({ tunnelError: { at: new Date().toISOString(), details: String(details && (details.details || details.message) || details) } }).catch?.(() => {});
  });
}

async function siteState(tabId, url) {
  const settings = await Shield.loadSettings();
  const host = Shield.hostOf(url || "");
  const site = Shield.siteOf(host);
  return {
    host,
    site,
    web: /^https?:/.test(url || ""),
    trusted: settings.privacy.trustedSites.includes(site),
    strictCookies: settings.privacy.strictCookieSites.includes(site),
    captureAllowed: settings.capture.allowedSites.includes(site),
    shoppingQuiet: settings.shopping.quietSites.includes(site),
    blocked: tabId === undefined ? 0 : await Shield.tabCount(tabId),
  };
}

function toggleInList(list, value, present) {
  const set = new Set(list);
  if (present) set.add(value);
  else set.delete(value);
  return Array.from(set);
}

async function onceAllowed(site, kind) {
  const session = await api.storage.session.get("captureOnce");
  const grants = session.captureOnce || {};
  const grant = grants[site + "|" + kind];
  return Boolean(grant && Date.now() - grant < 10 * 60 * 1000);
}

// SSRF prevention: only fetch external https URLs that are not RFC-1918 / loopback.
function isSafeExternalUrl(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== "https:") return false;
    const h = u.hostname;
    if (/^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|::1)/i.test(h)) return false;
    return true;
  } catch { return false; }
}

// Token buckets per tab and kind: a page that floods the worker with lookups
// (breach prefixes, store searches) gets a quiet refusal, not a queue that
// runs on its behalf.
// The hosts content/search.js works on; search.peek answers nobody else.
const SEARCH_ENGINE_HOST = /(^|\.)(google\.[a-z.]{2,10}|bing\.com|duckduckgo\.com|search\.brave\.com|search\.yahoo\.com|search\.yahoo\.co\.jp|startpage\.com|ecosia\.[a-z]{2,3}|yandex\.(ru|com|com\.tr|by|kz|ua|uz|az|eu)|ya\.ru|baidu\.com|search\.naver\.com|search\.daum\.net|search\.seznam\.cz|qwant\.com|sogou\.com|so\.com|coccoc\.com|search\.aol\.com|ask\.com|go\.mail\.ru|nova\.rambler\.ru|petalsearch\.com|kagi\.com|you\.com|mojeek\.com|swisscows\.com|presearch\.com|search\.lilo\.org|yep\.com)$|searx/i;
const rateBuckets = new Map();
function allowRate(kind, sender, perMinute) {
  const key = kind + "|" + (sender && sender.tab ? sender.tab.id : "popup");
  const now = Date.now();
  let bucket = rateBuckets.get(key);
  if (!bucket || now - bucket.start > 60000) {
    bucket = { start: now, used: 0 };
    rateBuckets.set(key, bucket);
  }
  if (rateBuckets.size > 500) {
    for (const [otherKey, other] of rateBuckets) if (now - other.start > 60000) rateBuckets.delete(otherKey);
  }
  bucket.used += 1;
  return bucket.used <= perMinute;
}

const handlers = {
  async state(message, sender) {
    const [settings, tunnel, stats, update, feeds] = await Promise.all([
      Shield.loadSettings(), Shield.tunnelStatus(), Shield.statsSummary(), Shield.updateStatus(), Shield.loadFeeds(),
    ]);
    const tab = message.tabId !== undefined ? { id: message.tabId, url: message.url } : sender.tab ? { id: sender.tab.id, url: sender.tab.url } : null;
    const site = tab ? await siteState(tab.id, tab.url) : null;
    const servers = await Shield.allServers();
    return { settings, tunnel, stats, update, site, servers, feeds: Object.fromEntries(Object.entries(feeds).map(([name, entry]) => [name, { fetched: entry.fetched, error: entry.error, count: entry.data && (entry.data.servers || entry.data.coupons || []).length }])) };
  },
  async "settings.update"(message) {
    return { settings: await Shield.updateSettings(message.change) };
  },
  async "site.set"(message) {
    const settings = await Shield.loadSettings();
    const site = String(message.site || "");
    if (!site) return { error: "no site" };
    const change = {};
    if (message.field === "trusted") change.privacy = { trustedSites: toggleInList(settings.privacy.trustedSites, site, message.value) };
    else if (message.field === "strictCookies") change.privacy = { strictCookieSites: toggleInList(settings.privacy.strictCookieSites, site, message.value) };
    else if (message.field === "captureAllowed") change.capture = { allowedSites: toggleInList(settings.capture.allowedSites, site, message.value) };
    else if (message.field === "shoppingQuiet") change.shopping = { quietSites: toggleInList(settings.shopping.quietSites, site, message.value) };
    else return { error: "unknown field" };
    return { settings: await Shield.updateSettings(change) };
  },
  async "tunnel.apply"() {
    const settings = await Shield.loadSettings();
    const status = await Shield.applyTunnel(settings);
    await Shield.applyHeaderRules(settings);
    return { status };
  },
  async "tunnel.connect"(message) {
    const serverId = String(message.serverId || "");
    if (serverId === Shield.NOAH_TOR_ID) {
      // The popup closes long before Tor is up; the connect goes on without it.
      Shield.connectNoahTor(message.country).catch((error) => console.warn("shield: noah tor", error));
      await new Promise((resolve) => setTimeout(resolve, 300));
      return { status: await Shield.tunnelStatus() };
    }
    const settings = await Shield.updateSettings({ tunnel: { enabled: true, serverId } });
    return { status: await Shield.applyTunnel(settings) };
  },
  async "tunnel.disconnect"() {
    return { status: await Shield.disconnectTunnel() };
  },
  async "tunnel.speedTest"(message) {
    const settings = await Shield.loadSettings();
    const results = await Shield.speedTest(settings, Array.isArray(message.ids) ? message.ids : null);
    if (message.pickFastest) {
      const best = results.find((result) => result.state === "up");
      if (best) await Shield.updateSettings({ tunnel: { enabled: true, serverId: best.id } });
      return { results, picked: best ? best.id : null };
    }
    return { results };
  },
  async "tunnel.route"(message) {
    const settings = await Shield.loadSettings();
    const site = String(message.site || "");
    if (!site) return { error: "no site" };
    const siteRoutes = { ...settings.tunnel.siteRoutes };
    if (!message.serverId) delete siteRoutes[site];
    else siteRoutes[site] = String(message.serverId);
    const updated = await Shield.updateSettings({ tunnel: { siteRoutes } });
    await Shield.applyTunnel(updated);
    return { siteRoutes };
  },
  async "media.state"(message, sender) {
    if (!sender.tab) return { ok: true };
    const session = await api.storage.session.get("mediaTabs");
    const mediaTabs = session.mediaTabs || {};
    if (message.camera || message.microphone) {
      mediaTabs[sender.tab.id] = { camera: Boolean(message.camera), microphone: Boolean(message.microphone), site: Shield.siteOf(Shield.hostOf(sender.url || "")), title: sender.tab.title || "", since: (mediaTabs[sender.tab.id] || {}).since || Date.now() };
    } else {
      delete mediaTabs[sender.tab.id];
    }
    await api.storage.session.set({ mediaTabs });
    return { ok: true };
  },
  async "media.list"() {
    const session = await api.storage.session.get("mediaTabs");
    return { tabs: Object.entries(session.mediaTabs || {}).map(([tabId, entry]) => ({ tabId: Number(tabId), ...entry })) };
  },
  // Media files the current page loaded that noah can strip + shrink.
  async "media.assets"(message) {
    let tabId = message && message.tabId;
    if (tabId === undefined) { const tabs = (await api.tabs.query({})).filter((t) => t.url && /^https?:/.test(t.url) && !t.url.startsWith(api.runtime.getURL(""))).sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0)); if (tabs[0]) tabId = tabs[0].id; }
    const store = (await api.storage.session.get("dlAssets")).dlAssets || {};
    const bucket = store[tabId] || {};
    const items = Object.values(bucket).filter((i) => i.type === "image" || /\.(jpe?g|png|gif|webp)(\?|$)/i.test(i.url) || /^image\/(jpeg|png|gif|webp)/i.test(i.mimeType || ""));
    return { tabId, items: items.slice(0, 100) };
  },
  // For the tools page: where traffic comes out and who steers the route.
  async "network.state"() {
    const settings = await Shield.loadSettings();
    const tunnel = await Shield.tunnelStatus();
    let control = null;
    let systemProxy = null;
    if (api.proxy && api.proxy.settings) {
      try {
        const current = await api.proxy.settings.get({});
        control = current.levelOfControl;
        const value = current.value || {};
        if (value.mode === "system" || value.mode === "auto_detect") systemProxy = null;
        else if (value.mode === "fixed_servers" && control !== "controlled_by_this_extension") {
          const rules = value.rules || {};
          const server = rules.singleProxy || rules.proxyForHttps || rules.proxyForHttp;
          systemProxy = server ? `${server.host}:${server.port}` : "a fixed proxy";
        } else if (value.mode === "pac_script" && control !== "controlled_by_this_extension") systemProxy = "a proxy script";
      } catch (error) {
        control = null;
      }
    }
    let exit = null;
    if (!settings.localOnly && tunnel.state !== "up") {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        const response = await fetch(Shield.WHOAMI_URL, { cache: "no-store", credentials: "omit", signal: controller.signal });
        clearTimeout(timer);
        if (response.ok) {
          const body = await response.json();
          exit = { ip: String(body.ip || ""), country: String(body.country || ""), city: String(body.city || "") };
        }
      } catch (error) {
        exit = null;
      }
    }
    return { tunnel, control, systemProxy, exit };
  },
  // ---- light: the screen's real brightness, through noah -------------------------------------
  async "light.state"() {
    const settings = await Shield.loadSettings();
    return settings.light;
  },
  async "light.read"() {
    const info = await Shield.hostInfo();
    if (!info.present) return { present: false, error: info.error };
    const answer = await Shield.host({ type: "brightness.get" });
    return { present: true, supported: !answer.error, level: answer.level, error: answer.error };
  },
  async "light.set"(message) {
    const settings = await Shield.loadSettings();
    const light = {
      preset: String(message.preset || "custom").slice(0, 20),
      brightness: message.brightness === null || message.brightness === undefined ? null : Math.min(100, Math.max(0, Math.round(Number(message.brightness) || 0))),
      warmth: Math.min(1, Math.max(0, Number(message.warmth === undefined ? settings.light.warmth : message.warmth) || 0)),
    };
    let outcome = { ok: true };
    if (light.brightness !== null) {
      const info = await Shield.hostInfo();
      if (!info.present) outcome = { ok: false, error: "the screen's brightness needs noah on this computer" };
      else {
        const answer = await Shield.host({ type: "brightness.set", level: light.brightness });
        outcome = answer.error ? { ok: false, error: answer.error } : { ok: true };
      }
    }
    await Shield.updateSettings({ light });
    const tabs = await api.tabs.query({ url: ["http://*/*", "https://*/*"] });
    for (const tab of tabs) api.tabs.sendMessage(tab.id, { type: "light.apply", light }, () => void api.runtime.lastError);
    await Shield.log({
      kind: "light",
      text: light.brightness === null ? "light: scene off" : outcome.ok ? `screen brightness set to ${light.brightness}%` : `screen brightness could not be set`,
      detail: [light.preset !== "custom" ? "scene: " + light.preset : "", light.warmth ? `warm tint ${Math.round(light.warmth * 100)}%` : "", outcome.error || ""].filter(Boolean).join(" · "),
    });
    return { light, ...outcome };
  },
  // ---- the log: what the shield did, in words ---------------------------------------------------
  async "log.list"(message) {
    return { entries: await Shield.logEntries({ kind: String(message.kind || ""), site: String(message.site || ""), tabId: Number.isInteger(message.tabId) ? message.tabId : null, limit: Math.min(3000, Number(message.limit) || 500) }) };
  },
  async "log.clear"() {
    await Shield.clearLog();
    return { ok: true };
  },
  async "log.open"(message, sender) {
    // A page can ask for the log only a few times a minute: the button under
    // the search counter is a person's click, a loop is not.
    if (sender && sender.tab && !allowRate("logopen", sender, 3)) return { ok: false };
    await openLog({ site: sender && sender.tab ? Shield.siteOf(Shield.hostOf(sender.tab.url || "")) : String(message.site || "") });
    return { ok: true };
  },
  // What was stopped on one tab, grouped by who was on the other end.
  async "tab.blocked"(message) {
    const tabId = Number(message.tabId);
    const entries = await Shield.blockedOnTab(tabId);
    const groups = new Map();
    for (const entry of entries) {
      const key = Shield.siteOf(entry.host) || entry.host;
      const group = groups.get(key) || { site: key, hosts: new Set(), count: 0, types: new Set(), owner: Shield.ownerOf ? Shield.ownerOf(entry.host) : null, last: 0 };
      group.hosts.add(entry.host);
      group.count += 1;
      group.types.add(entry.type);
      group.last = Math.max(group.last, entry.at);
      groups.set(key, group);
    }
    const list = Array.from(groups.values()).map((group) => ({ ...group, hosts: Array.from(group.hosts).slice(0, 6), types: Array.from(group.types) })).sort((left, right) => right.count - left.count);
    return { total: entries.length, groups: list };
  },
  // ---- search: cleaned results ---------------------------------------------------------------
  async "search.state"() {
    const settings = await Shield.loadSettings();
    const stored = await api.storage.local.get("look");
    // a fresh install has stored no look yet: green pastures, the default
    const look = stored.look || Shield.DEFAULT_LOOK || null;
    const image = look && look.image ? (look.image.startsWith("data:") ? look.image : api.runtime.getURL("looks/" + look.image)) : null;
    const palette = look && look.id === "pasture" && Shield.PASTURE_PALETTE ? Shield.PASTURE_PALETTE : look ? look.palette : null;
    return { clean: settings.search.clean, farms: settings.search.farms, look: settings.search.look && Boolean(image), peek: settings.search.peek, prices: settings.search.prices && !settings.localOnly, image, palette };
  },
  // A search result's own pricing page, read once a week without cookies, so
  // its plans show under the result. Only from search pages, only top results
  // (the page asks for at most six), never local addresses.
  async "search.prices"(message, sender) {
    if (!SEARCH_ENGINE_HOST.test(Shield.hostOf(sender.url || ""))) return { error: "not a search page" };
    const settings = await Shield.loadSettings();
    if (!settings.search.prices || settings.localOnly) return { error: "off" };
    if (!allowRate("prices", sender, 30)) return { error: "too many" };
    let target;
    try { target = new URL(String(message.url || "")); } catch { return { error: "not a web address" }; }
    if (!/^https?:$/.test(target.protocol) || Shield.isLocalHost(target.hostname)) return { error: "not a web address" };
    const site = Shield.siteOf(target.hostname);
    const stored = await api.storage.local.get("priceCache");
    const cache = stored.priceCache || {};
    const hit = cache[site];
    const WEEK = 7 * 24 * 3600 * 1000;
    if (hit && Date.now() - hit.at < WEEK) {
      const days = Math.floor((Date.now() - hit.at) / 86400000);
      return Object.assign({}, hit, { cached: true, age: days ? days + (days === 1 ? " day ago" : " days ago") : "today" });
    }
    const hosts = [...new Set([target.hostname, "www." + site, site])];
    const paths = ["/pricing", "/plans", "/prices", "/pricing/"];
    let result = { plans: [], currency: "USD", url: target.origin + "/pricing" };
    outer: for (const host of hosts.slice(0, 2)) {
      for (const path of paths.slice(0, 3)) {
        const url = "https://" + host + path;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 7000);
        try {
          const response = await fetch(url, { credentials: "omit", referrerPolicy: "no-referrer", redirect: "follow", signal: controller.signal, headers: { accept: "text/html" } });
          if (!response.ok || !/html/.test(response.headers.get("content-type") || "")) continue;
          if (Shield.isLocalHost(Shield.hostOf(response.url))) continue;
          const reader = response.body.getReader();
          const chunks = []; let size = 0;
          while (size < 1500000) { const { value, done } = await reader.read(); if (done) break; chunks.push(value); size += value.byteLength; }
          reader.cancel().catch(() => {});
          const parsed = Shield.parsePricing(new TextDecoder().decode(await new Blob(chunks).arrayBuffer()));
          if (parsed.plans.length) { result = Object.assign(parsed, { url: response.url }); break outer; }
        } catch { /* next path */ } finally { clearTimeout(timer); }
      }
    }
    result.at = Date.now();
    cache[site] = result;
    const keys = Object.keys(cache);
    if (keys.length > 400) for (const key of keys.sort((a, b) => cache[a].at - cache[b].at).slice(0, keys.length - 400)) delete cache[key];
    await api.storage.local.set({ priceCache: cache });
    return result;
  },
  // A result's page, fetched once without cookies or a referrer, for the
  // "peek" under it. Only when asked, only web pages, never local addresses.
  async "search.peek"(message, sender) {
    // content/search.js runs everywhere and leaves unless the host is an engine;
    // the worker checks the same thing, so no other page can use this as a fetch proxy.
    if (!SEARCH_ENGINE_HOST.test(Shield.hostOf(sender.url || ""))) return { error: "not a search page" };
    const settings = await Shield.loadSettings();
    if (!settings.search.peek || settings.localOnly) return { error: "peeking is off" };
    if (!allowRate("peek", sender, 20)) return { error: "too many in a minute; a moment" };
    if (!isSafeExternalUrl(String(message.url || ""))) return { error: "not a web address" };
    let url;
    try { url = new URL(String(message.url || "")); } catch { return { error: "not a web address" }; }
    if (!/^https?:$/.test(url.protocol) || Shield.isLocalHost(url.hostname)) return { error: "not a web address" };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const response = await fetch(url.href, { credentials: "omit", referrerPolicy: "no-referrer", redirect: "follow", cache: "default", signal: controller.signal, headers: { accept: "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5" } });
      if (!response.ok) return { error: "the site answered " + response.status };
      const type = response.headers.get("content-type") || "";
      if (!/html|xml/.test(type)) return { error: "not a page (" + type.split(";")[0] + ")" };
      if (Shield.isLocalHost(Shield.hostOf(response.url))) return { error: "the page moved somewhere local" };
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      while (size < 1500000) {
        const { value, done } = await reader.read();
        if (done) break;
        chunks.push(value);
        size += value.byteLength;
      }
      reader.cancel().catch(() => {});
      const html = new TextDecoder().decode(await new Blob(chunks).arrayBuffer());
      await Shield.count("peeks", 1, sender.tab ? sender.tab.id : null);
      return { html, url: response.url };
    } catch (error) {
      return { error: controller.signal.aborted ? "no answer in nine seconds" : String(error.message || error) };
    } finally {
      clearTimeout(timer);
    }
  },
  async "search.hidden"(message, sender) {
    if (!allowRate("search", sender, 30)) return { ok: false };
    const paid = Math.min(100, Math.max(0, Number(message.paid) || 0));
    const farms = Math.min(100, Math.max(0, Number(message.farms) || 0));
    const dimmed = Math.min(100, Math.max(0, Number(message.dimmed) || 0));
    if (paid) await Shield.count("paidResults", paid, sender.tab ? sender.tab.id : null);
    if (farms) await Shield.count("farmResults", farms, sender.tab ? sender.tab.id : null);
    const parts = [paid && `${paid} paid result${paid === 1 ? "" : "s"} hidden`, farms && `${farms} content-farm page${farms === 1 ? "" : "s"} hidden`, dimmed && `${dimmed} faded as written for the engine`].filter(Boolean);
    await Shield.log({ kind: "search", site: Shield.siteOf(Shield.hostOf(sender.url || "")), tabId: sender.tab ? sender.tab.id : null, text: `${String(message.engine || "search")}: ${parts.join(", ")}`, detail: message.query ? `search: ${String(message.query).slice(0, 120)}` : "" });
    return { ok: true };
  },
  // ---- noah on this computer ----------------------------------------------------------------------
  async "host.info"(message) {
    return Shield.hostInfo(Boolean(message.fresh));
  },
  // ---- frequency: a tone or a binaural beat under whatever plays ------------------------------
  async "tone.play"(message) {
    const state = await toneHost({ action: "play", hz: message.hz, volume: message.volume });
    await api.storage.session.set({ tone: state });
    return state;
  },
  async "tone.volume"(message) {
    const state = await toneHost({ action: "volume", volume: message.volume });
    await api.storage.session.set({ tone: state });
    return state;
  },
  async "tone.stop"() {
    const state = await toneHost({ action: "stop" }, false);
    await api.storage.session.set({ tone: state });
    return state;
  },
  async "tone.state"() {
    const session = await api.storage.session.get("tone");
    return session.tone || { playing: false, hz: 432, volume: 0.15 };
  },
  // ---- the look ---------------------------------------------------------------------------------
  async "look.set"(message) {
    const look = message.look;
    if (!look || typeof look !== "object" || !look.palette) return { error: "not a look" };
    const image = typeof look.image === "string" ? look.image : null;
    if (image && !image.startsWith("data:image/jpeg;base64,") && !/^[a-z]+\.jpg$/.test(image)) return { error: "not a picture" };
    if (image && image.length > 6 * 1024 * 1024) return { error: "the picture is too large; it is shrunk before saving, so try a smaller file" };
    const clean = { id: String(look.id || "custom").slice(0, 40), name: String(look.name || "").slice(0, 80), image, palette: {} };
    for (const [key, value] of Object.entries(look.palette)) {
      if (/^[a-zA-Z]+$/.test(key) && (typeof value === "string" && value.length < 60 || typeof value === "number" || typeof value === "boolean")) clean.palette[key] = value;
    }
    await api.storage.local.set({ look: clean });
    await wearLook(clean);
    return { look: clean };
  },
  async "look.reset"() {
    await api.storage.local.remove("look");
    await wearLook(null);
    return { ok: true };
  },
  async "stats.today"() {
    return Shield.statsSummary();
  },
  async "tunnel.check"() {
    const server = Shield.activeServer();
    if (!server) return { status: await Shield.tunnelStatus() };
    return { status: await Shield.checkExit(server) };
  },
  async "tunnel.addServer"(message) {
    try {
      return { server: await Shield.addServer(message.server) };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  async "tunnel.removeServer"(message) {
    await Shield.removeServer(String(message.id));
    const settings = await Shield.loadSettings();
    if (settings.tunnel.serverId === message.id) await Shield.updateSettings({ tunnel: { enabled: false, serverId: null } });
    return { ok: true };
  },
  async "privacy.purgeCookies"() {
    return { removed: await Shield.purgeTrackerCookies(await Shield.loadSettings()) };
  },
  async "feeds.refresh"() {
    await Shield.refreshFeeds();
    return { update: await Shield.updateStatus() };
  },
  async "watch.audit"() {
    return Shield.auditExtensions();
  },
  async "watch.setEnabled"(message) {
    try {
      await Shield.setExtensionEnabled(String(message.id), Boolean(message.enabled));
      return { ok: true };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  // The page-side guard asks what this site may do, once per document.
  async "guard.config"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || (sender.tab && sender.tab.url) || ""));
    const trusted = settings.privacy.trustedSites.includes(site);
    const security = settings.security;
    const config = {
      site,
      trusted,
      geolocation: trusted ? "ask" : settings.privacy.geolocation,
      fingerprint: settings.privacy.fingerprint && !trusted,
      guardScreen: settings.capture.guardScreen,
      guardCamera: settings.capture.guardCamera,
      shopping: settings.shopping.compare || settings.shopping.coupons,
      shoppingQuiet: settings.shopping.quietSites.includes(site),
      autoApply: settings.shopping.autoApply,
      clipCoupons: settings.shopping.clipCoupons,
      pharmaWarn: settings.shopping.pharmaWarn,
      homeCurrency: settings.shopping.homeCurrency || "",
      lookalike: security.lookalike,
      passwordReuse: security.passwordReuse,
      passwordHttp: security.passwordHttp,
      breachCheck: security.breachCheck && !settings.localOnly,
      clipboardGuard: security.clipboardGuard && !security.clipboardSites.includes(site),
      clipboardWipe: security.clipboardWipe,
      hiddenFields: security.hiddenFields,
      typingGuard: security.typingGuard && !trusted,
      blockKeyListeners: security.blockKeyListeners && !trusted,
      formLeak: security.formLeak && !trusted,
      walletGuard: security.walletGuard && !security.walletSites.includes(site),
      scamPopups: security.scamPopups,
      hiddenFrames: security.hiddenFrames,
      seed: await Shield.fingerprintSeed(site, settings),
      blendIn: settings.privacy.blendIn && !trusted,
      audioNoise: settings.privacy.audioNoise && settings.privacy.fingerprint && !trusted,
      webglNoise: settings.privacy.webglNoise && settings.privacy.fingerprint && !trusted,
      location: await locationFor(settings, trusted),
      hideNames: settings.privacy.hideNames,
      linkCleaner: settings.privacy.linkCleaner,
      tag: await elementTag(settings),
      annoyances: {
        banners: settings.annoyances.banners,
        overlays: settings.annoyances.overlays,
        autoplay: settings.annoyances.autoplay,
        timers: settings.annoyances.timers,
        copy: settings.annoyances.copySites.includes(site),
        dark: settings.annoyances.darkEverywhere || settings.annoyances.darkSites.includes(site),
      },
      pasteGuard: settings.annoyances.pasteGuard,
      uploadStrip: settings.annoyances.uploadStrip,
      lockMinutes: settings.modes.lock.sites.includes(site) && settings.modes.lock.pinHash ? settings.modes.lock.minutes : 0,
      mode: settings.modes.siteModes[site] || settings.modes.profile || "",
    };
    // Count each page load where fingerprint spoofing is active.
    // Tallied as today.fingerprint and surfaced in the popup tracker-defense counter.
    if (config.fingerprint) {
      await Shield.count("fingerprint", 1, sender.tab ? sender.tab.id : null);
    }
    return config;
  },
  async "lock.check"(message, sender) {
    // Six tries a minute per tab: a four-digit PIN cannot be walked from a page.
    if (!allowRate("lock", sender, 6)) return { ok: false, error: "too many tries; wait a minute" };
    const settings = await Shield.loadSettings();
    // Accepts pre-hashed pinHash (from updated content/lock.js) or legacy plaintext pin.
    const hash = message.pinHash ? String(message.pinHash) : await Shield.hashPin(String(message.pin || ""));
    return { ok: Boolean(settings.modes.lock.pinHash) && hash === settings.modes.lock.pinHash };
  },
  async "pin.set"(message) {
    const pin = String(message.pin || "");
    if (pin && !/^\d{4,12}$/.test(pin)) return { error: "a PIN is 4 to 12 digits" };
    const hash = pin ? await Shield.hashPin(pin) : "";
    if (message.target === "parental") {
      const settings = await Shield.loadSettings();
      if (settings.modes.parental.pinHash && (await Shield.hashPin(String(message.current || ""))) !== settings.modes.parental.pinHash) return { error: "the current PIN is needed to change it" };
      await Shield.updateSettings({ modes: { parental: { pinHash: hash } } });
    } else {
      await Shield.updateSettings({ modes: { lock: { pinHash: hash } } });
    }
    return { ok: true };
  },
  async "parental.set"(message) {
    const settings = await Shield.loadSettings();
    if (settings.modes.parental.pinHash && (await Shield.hashPin(String(message.pin || ""))) !== settings.modes.parental.pinHash) return { error: "the parental PIN is needed" };
    await Shield.updateSettings({ modes: { parental: { enabled: Boolean(message.enabled) } } });
    return { ok: true };
  },
  async "profile.apply"(message) {
    try {
      const settings = await Shield.applyProfile(String(message.name || ""));
      return { settings };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  async "report.weekly"() {
    return Shield.weeklyReport();
  },
  async "tools.unshorten"(message) {
    const settings = await Shield.loadSettings();
    if (settings.localOnly) return { error: "local-only mode: no lookups leave the browser" };
    const url = String(message.url || "");
    if (!/^https?:\/\//i.test(url)) return { error: "not a web address" };
    const result = await Shield.unshorten(url);
    result.lookalike = Shield.lookalike(Shield.hostOf(result.final));
    result.shortener = Shield.SHORTENERS.test(Shield.hostOf(url));
    return result;
  },
  async "tools.hops"(message) {
    return { hops: await Shield.hopsFor(Number(message.tabId)) };
  },
  async "vault.save"(message) {
    if (String(message.passphrase || "").length < 6) return { error: "use at least six characters" };
    await Shield.vaultSave(String(message.passphrase), Array.isArray(message.notes) ? message.notes.slice(0, 500) : []);
    return { ok: true };
  },
  async "vault.open"(message) {
    try {
      return { notes: await Shield.vaultOpen(String(message.passphrase || "")) };
    } catch {
      return { error: "wrong passphrase, or no vault yet" };
    }
  },
  async "tools.letter"(message) {
    return { text: Shield.deletionLetter({ name: String(message.name || ""), email: String(message.email || ""), company: String(message.company || ""), law: String(message.law || "") }), brokers: Shield.BROKERS };
  },
  async "tools.policy"(message) {
    const tabId = Number(message.tabId);
    let text = String(message.text || "");
    if (!text && tabId) {
      try {
        const [result] = await api.scripting.executeScript({ target: { tabId }, func: () => document.body ? document.body.innerText.slice(0, 400000) : "" });
        text = result && result.result ? result.result : "";
      } catch (error) {
        return { error: String(error.message || error) };
      }
    }
    return Shield.readPolicy(text);
  },
  async "tools.throwaway"(message) {
    const url = String(message.url || "");
    if (!/^https?:\/\//i.test(url)) return { error: "not a web address" };
    let allowed = false;
    try { allowed = await api.extension.isAllowedIncognitoAccess(); } catch { allowed = false; }
    if (allowed) {
      await api.windows.create({ url, incognito: true });
      return { ok: true, incognito: true };
    }
    const window = await api.windows.create({ url });
    return { ok: true, incognito: false, windowId: window.id, note: "Allow the shield in incognito (browser's extension page) for a truly throwaway window; this one is a normal window whose site cookies burn when it closes." };
  },
  async "container.open"(message) {
    const identities = api.contextualIdentities;
    if (!identities) return { error: "only Firefox has containers" };
    const url = String(message.url || "");
    const site = Shield.siteOf(Shield.hostOf(url));
    const existing = (await identities.query({ name: "shield: " + site }))[0];
    const identity = existing || (await identities.create({ name: "shield: " + site, color: "green", icon: "fence" }));
    await api.tabs.create({ url, cookieStoreId: identity.cookieStoreId });
    return { ok: true };
  },
  async "site.burn"(message) {
    return Shield.burnSite(String(message.site || ""), Array.isArray(message.origins) ? message.origins.map(String) : []);
  },
  async "site.watchers"(message) {
    return { watchers: await Shield.watchers(Number(message.tabId), String(message.site || "")) };
  },
  async "site.score"(message) {
    return Shield.privacyScore(Number(message.tabId), String(message.url || ""));
  },
  // Is this site worth trusting: has it leaked its users' data before, is it
  // a lookalike, is it plain http. For the popup only.
  async "site.trust"(message) {
    const url = String(message.url || "");
    const host = Shield.hostOf(url);
    const site = Shield.siteOf(host);
    if (!site) return { error: "not a site" };
    const settings = await Shield.loadSettings();
    const lookalike = settings.security.allowedLookalikes.includes(site) ? null : Shield.lookalike(host);
    let breaches = null;
    let breachError = null;
    if (settings.localOnly) breachError = "not checked in local-only mode";
    else if (!settings.security.breachCheck) breachError = "breach checks are off in settings";
    else {
      try {
        breaches = await Shield.breachHistory(site);
      } catch (error) {
        breachError = String(error.message || error);
      }
    }
    return { site, https: url.startsWith("https:"), lookalike, breaches, breachError };
  },
  async "alias.make"(message) {
    const settings = await Shield.loadSettings();
    const site = String(message.site || "");
    if (settings.privacy.simpleLoginKey && !settings.localOnly) {
      try {
        return { alias: await Shield.simpleLoginAlias(settings.privacy.simpleLoginKey, "noah shield for " + site), source: "SimpleLogin" };
      } catch (error) {
        return { error: String(error.message || error) };
      }
    }
    if (!settings.privacy.aliasBase) return { error: "set your email address under settings first; aliases are plus-addresses at it" };
    return { alias: Shield.makeAlias(settings.privacy.aliasBase, site), source: "plus address" };
  },
  async "decoy.fill"(message) {
    const settings = await Shield.loadSettings();
    const identity = Shield.decoyIdentity(settings.privacy.aliasBase, String(message.site || ""));
    const tabId = Number(message.tabId);
    try {
      await api.scripting.executeScript({ target: { tabId }, func: fillDecoy, args: [identity] });
    } catch (error) {
      return { error: String(error.message || error), identity };
    }
    return { identity };
  },
  async "fingerprint.rotate"() {
    await Shield.rotateFingerprint();
    return { ok: true };
  },
  async "sync.set"(message) {
    const passphrase = String(message.passphrase || "");
    if (passphrase.length < 8 && passphrase.length !== 0) return { error: "use at least eight characters" };
    if (!passphrase) {
      await api.storage.local.remove("syncPassphrase");
      await Shield.updateSettings({ privacy: { sync: false } });
      return { ok: true };
    }
    // TODO: F-02 — passphrase stored plaintext, should be derived not stored
    await api.storage.local.set({ syncPassphrase: passphrase });
    const settings = await Shield.updateSettings({ privacy: { sync: true } });
    await Shield.pushSync(settings);
    return { ok: true };
  },
  async "sync.pull"() {
    try {
      const pulled = await Shield.pullSync();
      if (!pulled) return { error: "nothing synced yet, or no passphrase" };
      await Shield.saveSettings(Shield.deepMerge(Shield.DEFAULT_SETTINGS, pulled.settings));
      return { ok: true, at: pulled.at };
    } catch (error) {
      return { error: "could not decrypt: wrong passphrase or damaged data (" + String(error.message || error) + ")" };
    }
  },
  async "permissions.log"() {
    const stored = await api.storage.local.get("permissionLog");
    return { log: stored.permissionLog || [] };
  },
  async "panic"() {
    await panic();
    return { ok: true };
  },
  // ---- screenshots and the recorder --------------------------------------------------------------
  // The popup starts a capture for the active tab; the tab's content script
  // drives it and comes back here for each shot and for the file. A tab may
  // only do that while a capture the person started is open for it.
  async "capture.start"(message) {
    const [tab] = await api.tabs.query({ active: true, currentWindow: true });
    if (!tab || !/^https?:/.test(tab.url || "")) return { error: "open a web page first; the browser's own pages cannot be captured" };
    const session = await api.storage.session.get("captureTabs");
    const captureTabs = session.captureTabs || {};
    captureTabs[tab.id] = Date.now() + 5 * 60 * 1000;
    await api.storage.session.set({ captureTabs });
    const mode = ["visible", "full", "area"].includes(message.mode) ? message.mode : "visible";
    try {
      // A tab open since before the shield was installed or updated has no
      // capture script yet; it is put in now rather than asking for a reload.
      const ready = !message.inject && await new Promise((resolve) => {
        api.tabs.sendMessage(tab.id, { type: "capture.ping" }, (response) => {
          void api.runtime.lastError;
          resolve(Boolean(response && response.ready));
        });
      });
      if (!ready) {
        if (!api.scripting || !api.scripting.executeScript) throw new Error("reload the page once, then try again");
        try {
          await api.scripting.executeScript({ target: { tabId: tab.id }, files: ["content/capture.js"] });
        } catch (error) {
          throw new Error("this page does not let extensions in (" + String(error.message || error).replace(/^Error: /, "") + ")");
        }
      }
      const result = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("the page did not answer; reload it and try again")), 6 * 60 * 1000);
        api.tabs.sendMessage(tab.id, { type: "capture.run", mode, blur: Boolean(message.blur) }, (response) => {
          clearTimeout(timer);
          if (api.runtime.lastError) reject(new Error("the page did not answer; reload it and try again"));
          else resolve(response || {});
        });
      });
      const site = Shield.siteOf(Shield.hostOf(tab.url));
      if (result.error) await Shield.log({ kind: "capture", site, tabId: tab.id, text: `screenshot (${mode}) failed`, detail: result.error });
      else if (!result.cancelled) await Shield.log({ kind: "capture", site, tabId: tab.id, text: `screenshot (${mode === "full" ? "whole page" : mode === "area" ? "an area" : "what was on screen"}) saved to Downloads/noah-shield`, detail: result.blurred ? `${result.blurred} private detail(s) blurred first` : "nothing needed blurring" });
      return result;
    } catch (error) {
      await Shield.log({ kind: "capture", site: Shield.siteOf(Shield.hostOf(tab.url)), tabId: tab.id, text: `screenshot (${mode}) failed`, detail: String(error.message || error) });
      return { error: String(error.message || error) };
    } finally {
      const after = await api.storage.session.get("captureTabs");
      const remaining = after.captureTabs || {};
      delete remaining[tab.id];
      await api.storage.session.set({ captureTabs: remaining });
    }
  },
  async "capture.shot"(message, sender) {
    if (!sender.tab) return { error: "not a tab" };
    const session = await api.storage.session.get("captureTabs");
    const until = (session.captureTabs || {})[sender.tab.id];
    if (!until || until < Date.now()) return { error: "no capture is open for this page" };
    try {
      const dataUrl = await api.tabs.captureVisibleTab(sender.tab.windowId, { format: "png" });
      return { dataUrl };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  async "capture.save"(message, sender) {
    if (!sender.tab) return { error: "not a tab" };
    const session = await api.storage.session.get("captureTabs");
    const until = (session.captureTabs || {})[sender.tab.id];
    if (!until || until < Date.now()) return { error: "no capture is open for this page" };
    const dataUrl = String(message.dataUrl || "");
    const filename = String(message.filename || "");
    if (!dataUrl.startsWith("data:image/png;base64,")) return { error: "not a picture" };
    if (!/^noah-shield\/[A-Za-z0-9 ._-]+\.png$/.test(filename)) return { error: "bad file name" };
    try {
      const id = await api.downloads.download({ url: dataUrl, filename, saveAs: false, conflictAction: "uniquify" });
      return { ok: true, id };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  async "record.open"() {
    const url = api.runtime.getURL("record.html");
    // FIX: type:"popup" windows fail getDisplayMedia() in Chrome 116+ because
    // the screen-capture picker pulls focus away from the popup window and Chrome
    // drops the pending call. type:"normal" is a full window — getDisplayMedia()
    // is reliable there. Use tabs.query for the dedup check (more reliable than
    // windows.getAll which may not populate tab URLs for all window types).
    try {
      const existing = await api.tabs.query({ url });
      if (existing && existing.length > 0) {
        const tab = existing[0];
        await api.windows.update(tab.windowId, { focused: true });
        await api.tabs.update(tab.id, { active: true });
        return { ok: true, reused: true };
      }
    } catch {
      // tabs.query may fail if the URL is not in the allowed set; fall through.
    }
    await api.windows.create({ url, type: "normal", width: 520, height: 820, focused: true });
    return { ok: true };
  },
  async "capture.ask"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    const kind = ["screen", "camera", "clipboard", "wallet"].includes(message.kind) ? message.kind : "camera";
    const guarded = {
      screen: settings.capture.guardScreen,
      camera: settings.capture.guardCamera,
      clipboard: settings.security.clipboardGuard,
      wallet: settings.security.walletGuard,
    }[kind];
    if (!guarded) return { decision: "allow" };
    const allowed = {
      screen: settings.capture.allowedSites,
      camera: settings.capture.allowedSites,
      clipboard: settings.security.clipboardSites,
      wallet: settings.security.walletSites,
    }[kind];
    if (allowed.includes(site) || (await onceAllowed(site, kind))) return { decision: "allow" };
    pendingCaptureAsks.set(captureAskKey(sender, kind), Date.now());
    return { decision: "ask", site };
  },
  // A decision counts only as the answer to a question this worker asked
  // that tab; a script that never asked cannot grant itself the capture.
  async "capture.decide"(message, sender) {
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    const kind = ["screen", "camera", "clipboard", "wallet"].includes(message.kind) ? message.kind : "camera";
    const key = captureAskKey(sender, kind);
    const askedAt = pendingCaptureAsks.get(key);
    pendingCaptureAsks.delete(key);
    if (!askedAt || Date.now() - askedAt > 10 * 60 * 1000) return { error: "nothing was asked" };
    if (message.always) {
      const settings = await Shield.loadSettings();
      if (kind === "clipboard") await Shield.updateSettings({ security: { clipboardSites: toggleInList(settings.security.clipboardSites, site, true) } });
      else if (kind === "wallet") await Shield.updateSettings({ security: { walletSites: toggleInList(settings.security.walletSites, site, true) } });
      else await Shield.updateSettings({ capture: { allowedSites: toggleInList(settings.capture.allowedSites, site, true) } });
    } else if (message.allow) {
      const session = await api.storage.session.get("captureOnce");
      const grants = session.captureOnce || {};
      grants[site + "|" + kind] = Date.now();
      await api.storage.session.set({ captureOnce: grants });
    }
    if (!message.allow) await Shield.count(kind === "wallet" ? "wallets" : kind === "clipboard" ? "clipboard" : "captures", 1, sender.tab ? sender.tab.id : null);
    return { ok: true };
  },
  async "safety.event"(message, sender) {
    if (!allowRate("safety", sender, 120)) return { ok: false, limited: true };
    const kinds = new Set(["phishing", "passwordHttp", "reuse", "breached", "hiddenFields", "frames", "popups", "leaks", "keylog", "wallets", "clipboard", "fees", "darkPatterns", "traps", "reviewsChecked", "banners", "overlays", "autoplay", "timers", "pastes", "uploads", "fingerprint", "social_sponsored_hidden", "social_suggested_hidden", "social_ad_hidden", "social_promoted_hidden", "social_karma_farm", "social_time_warning", "social_session_expired", "tiktok_session_warning", "tiktok_session_closed", "yt_autoplay_disabled", "yt_sidebar_cleaned", "yt_endscreen_cleaned"]);
    const kind = kinds.has(message.kind) ? message.kind : "other";
    const amount = Math.min(50, Math.max(1, Number(message.amount) || 1));
    await Shield.count(kind, amount, sender.tab ? sender.tab.id : null);
    Shield.sec.record("safety", { tab: sender.tab ? sender.tab.id : -1, url: sender.url || "", source: "shield guard", data: { kind, detail: typeof message.detail === "string" ? message.detail.slice(0, 200) : "" } }).catch(() => {});
    const words = {
      phishing: "a page that imitates another site was stopped",
      passwordHttp: "a password field on a page without https was flagged",
      reuse: "a password you use elsewhere was typed here",
      breached: "a password known from a breach was typed here",
      hiddenFields: "hidden form fields were cleared before sending",
      frames: "hidden frames were removed",
      popups: "a scam pop-up was closed",
      leaks: "a form leak to a third party was stopped",
      keylog: "a script recording keystrokes was caught",
      wallets: "a page reached for a crypto wallet",
      clipboard: "a page read the clipboard without being asked",
      fees: "a hidden fee was pointed out at checkout",
      darkPatterns: "a dark pattern was flagged",
      traps: "a subscription trap was flagged",
      reviewsChecked: "reviews were checked",
      banners: "a cookie banner was answered with no",
      overlays: "an overlay was removed",
      autoplay: "autoplay was stopped",
      timers: "a fake countdown was removed",
      pastes: "a paste was checked",
      uploads: "an upload had its hidden data stripped",
    };
    const detail = message.detail && typeof message.detail === "object" ? Object.entries(message.detail).map(([key, value]) => `${key}: ${String(value).slice(0, 120)}`).join(" · ") : String(message.detail || "").slice(0, 300);
    await Shield.log({ kind, site: Shield.siteOf(Shield.hostOf(sender.url || "")), tabId: sender.tab ? sender.tab.id : null, text: (amount > 1 ? amount + "× " : "") + (words[kind] || kind), detail });
    return { ok: true };
  },
  async "lookalike.check"(message) {
    const host = String(message.host || "");
    const found = Shield.lookalike(host);
    if (!found) return { brand: null };
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(host);
    const allowed = settings.security.allowedLookalikes.includes(site) || (await onceAllowed(site, "lookalike"));
    if (!allowed) Shield.sec.record("safety", { host, source: "lookalike check", data: { kind: "phishing", detail: "looks like " + (found.brand || "a known brand") } }).catch(() => {});
    return { ...found, site, allowed };
  },
  async "lookalike.allow"(message) {
    const site = String(message.site || "");
    const session = await api.storage.session.get("captureOnce");
    const grants = session.captureOnce || {};
    grants[site + "|lookalike"] = Date.now() + 10 * 60 * 60 * 1000;
    await api.storage.session.set({ captureOnce: grants });
    return { ok: true };
  },
  async "password.salt"() {
    return { salt: await Shield.installSalt() };
  },
  async "password.seen"(message, sender) {
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    return Shield.passwordSeen(String(message.hash || ""), site);
  },
  async "password.breach"(message, sender) {
    const settings = await Shield.loadSettings();
    if (settings.localOnly || !settings.security.breachCheck) return { count: 0, skipped: true };
    if (!allowRate("breach", sender, 5)) return { count: 0, skipped: true, limited: true };
    try {
      return { count: await Shield.breachCount(String(message.prefix || ""), String(message.suffix || "")) };
    } catch (error) {
      return { count: 0, error: String(error.message || error) };
    }
  },
  async "passwords.forget"() {
    await Shield.forgetPasswords();
    return { ok: true };
  },
  async "breach.email"(message) {
    const settings = await Shield.loadSettings();
    try {
      return { breaches: await Shield.breachedEmail(String(message.email || ""), settings.security.hibpKey) };
    } catch (error) {
      return { error: String(error.message || error) };
    }
  },
  async "scam.close"(message, sender) {
    if (sender.tab) await api.tabs.remove(sender.tab.id);
    return { ok: true };
  },
  // ---- security center ----------------------------------------------------------------------
  async "sec.brands"() {
    return (Shield.BRANDS || []).map((brand) => ({ name: brand.name, domains: brand.domains }));
  },
  async "sec.sense"(message, sender) {
    if (!sender.tab || !allowRate("sec", sender, 90)) return { ok: false };
    const event = message.event || {};
    const allowedKinds = new Set(["page.scan", "form.submit", "clipboard.write", "page.tabnab", "shop.scan"]);
    if (!allowedKinds.has(event.kind)) return { error: "unknown event" };
    const settings = await Shield.loadSettings();
    if (!settings.secCenter.enabled) return { ok: false };
    const data = event.data && typeof event.data === "object" ? event.data : {};
    if (event.kind === "shop.scan") {
      const signals = Array.isArray(data.signals) ? data.signals.slice(0, 8).map(String) : [];
      // the store's age is asked only when it already shows a scam sign, and only if you allow lookups
      if (signals.length && settings.secCenter.domainAgeLookups && !settings.localOnly) {
        const age = await Shield.sec.domainAge(Shield.hostOf(sender.url)).catch(() => null);
        if (age && age.ageDays !== null && age.ageDays < 180) signals.push(`domain registered ${age.ageDays} days ago (rdap)`);
      }
      data.signals = signals;
      data.signalCount = signals.length;
    }
    await Shield.sec.record(event.kind, { tab: sender.tab.id, url: sender.url, source: "page sensor", data });
    return { ok: true };
  },
  async "sec.overview"() {
    const cases = await Shield.sec.listCases();
    const since = Date.now() - 24 * 3600 * 1000;
    const events = await Shield.sec.query({ since });
    const intel = await Shield.sec.intelSummary();
    const open = cases.filter((c) => c.status === "open");
    return {
      open: open.length,
      bySeverity: Object.fromEntries(Object.keys(Shield.sec.SEVERITY).map((level) => [level, open.filter((c) => c.severity === level).length])),
      cases: cases.slice(0, 60).map(({ id, subject, severity, status, updated, opened, detections, resources }) => ({ id, subject, severity, status, updated, opened, titles: detections.map((d) => d.title), resources: resources.slice(0, 4) })),
      today: { events: events.length, requests: events.filter((e) => e.kind === "request").length, blocked: events.filter((e) => e.kind === "blocked").length, intelHits: events.filter((e) => e.kind === "intel.hit").length },
      intel: { hosts: intel.hosts, urls: intel.urls, feeds: intel.feeds },
      rules: Shield.sec.RULES.length,
    };
  },
  async "sec.case"(message) {
    const item = await Shield.sec.getCase(String(message.id || ""));
    if (!item) return { error: "no such case" };
    const ids = item.detections.flatMap((d) => d.evidence);
    const events = await Shield.sec.query({ ids });
    const ledger = (await Shield.sec.ledger()).map((entry, index) => Object.assign({ index }, entry)).filter((entry) => entry.case === item.id);
    return { item, events, ledger };
  },
  async "sec.contain"(message) {
    return Shield.sec.contain(String(message.id || ""), Number(message.index), { confirmed: Boolean(message.confirmed) });
  },
  async "sec.undo"(message) { return Shield.sec.undo(Number(message.index)); },
  async "sec.status"(message) { return Shield.sec.setCaseStatus(String(message.id || ""), String(message.status || "")); },
  async "sec.report"(message) {
    const item = await Shield.sec.getCase(String(message.id || ""));
    if (!item) return { error: "no such case" };
    const events = await Shield.sec.query({ ids: item.detections.flatMap((d) => d.evidence) });
    return message.format === "stix" ? { text: JSON.stringify(Shield.sec.reportStix(item, events), null, 2), name: "noah-shield-case.stix.json" } : { text: Shield.sec.reportText(item, events), name: "noah-shield-case.txt" };
  },
  async "sec.network"(message) {
    const since = Date.now() - Math.min(7 * 24, Math.max(1, Number(message.hours) || 1)) * 3600 * 1000;
    const events = await Shield.sec.query({ since, kind: ["request", "blocked", "nav.commit", "nav.redirect", "intel.hit", "download.start", "form.submit"] });
    const hosts = {};
    for (const event of events) {
      if (!event.host) continue;
      const row = hosts[event.host] = hosts[event.host] || { host: event.host, site: event.site, ips: [], requests: 0, blocked: 0, intel: 0, types: [], pages: [], first: event.t, last: event.t, owner: null, thirdParty: false };
      row.last = Math.max(row.last, event.t);
      if (event.ip && !row.ips.includes(event.ip) && row.ips.length < 6) row.ips.push(event.ip);
      if (event.kind === "request") { row.requests++; row.thirdParty = row.thirdParty || Boolean(event.data.thirdParty); if (event.data.owner) row.owner = event.data.owner; if (event.data.type && !row.types.includes(event.data.type)) row.types.push(event.data.type); if (event.data.pageSite && !row.pages.includes(event.data.pageSite) && row.pages.length < 12) row.pages.push(event.data.pageSite); }
      if (event.kind === "blocked") { row.blocked++; if (event.data.pageSite && !row.pages.includes(event.data.pageSite) && row.pages.length < 12) row.pages.push(event.data.pageSite); }
      if (event.kind === "intel.hit") row.intel++;
    }
    const timeline = events.slice(-300).reverse().map((e) => ({ t: e.t, kind: e.kind, host: e.host, ip: e.ip, text: Shield.sec.describe(e) }));
    return { since, hosts: Object.values(hosts).sort((a, b) => (b.intel - a.intel) || (b.blocked + b.requests - a.blocked - a.requests)).slice(0, 400), timeline, totals: { events: events.length, hosts: Object.keys(hosts).length, ips: new Set(events.map((e) => e.ip).filter(Boolean)).size } };
  },
  async "sec.graph"(message) {
    const g = await Shield.sec.graphSnapshot();
    const components = Shield.sec.components(g);
    const shared = Shield.sec.sharedInfrastructure(g).slice(0, 40);
    const recurring = Shield.sec.recurringDestinations(g).slice(0, 40);
    let start = String(message.node || "");
    if (!start || !g.nodes[start]) {
      const alerted = components.find((c) => c.alert);
      start = alerted ? alerted.members.find((id) => g.nodes[id].alert) : (Object.values(g.nodes).sort((a, b) => b.count - a.count)[0] || {}).id;
    }
    return { start, view: start ? Shield.sec.neighbourhood(g, start, 2, 70) : { nodes: [], edges: [] }, stats: { nodes: Object.keys(g.nodes).length, edges: Object.keys(g.edges).length, components: components.length, alertComponents: components.filter((c) => c.alert).length }, shared, recurring };
  },
  async "sec.extensions"() { return { list: await Shield.sec.extensionSnapshot(true) }; },
  async "sec.disableExtension"(message) {
    const id = String(message.id || "");
    if (id === api.runtime.id) return { error: "that is the shield itself" };
    await api.management.setEnabled(id, Boolean(message.enabled));
    await Shield.log({ kind: "security", text: (message.enabled ? "enabled" : "disabled") + " extension " + id });
    return { ok: true };
  },
  async "sec.intel"() { return Shield.sec.intelSummary(); },
  async "sec.intelAdd"(message) {
    const type = ["host", "ip", "hash", "url"].includes(message.kind) ? message.kind : "host";
    const value = String(message.value || "").trim().toLowerCase().slice(0, 300);
    if (!value) return { error: "nothing to add" };
    const added = await Shield.sec.addIndicator(type, value, { category: String(message.category || "suspicious").slice(0, 40), source: "you", confirmed: true });
    const settings = await Shield.loadSettings();
    if (type === "host") await Shield.sec.applyFeedBlocks(await Shield.sec.confirmedHosts(), Boolean(settings.secCenter.feedBlock && settings.secCenter.enabled));
    return { ok: true, added };
  },
  async "sec.intelRemove"(message) {
    await Shield.sec.removeIndicator(String(message.kind || "host"), String(message.value || ""));
    const settings = await Shield.loadSettings();
    await Shield.sec.applyFeedBlocks(await Shield.sec.confirmedHosts(), Boolean(settings.secCenter.feedBlock && settings.secCenter.enabled));
    return { ok: true };
  },
  async "sec.refreshFeeds"() { return Shield.sec.refreshFeeds(await Shield.loadSettings()); },
  // ---- local ai, wireguard, opensnitch, noah box (lib/local.js) ----
  async "ai.cognition"(message) {
    const settings = await Shield.loadSettings();
    if (!settings.localAi.enabled || !settings.localAi.cognition) return { skipped: true };
    return Shield.local.cognition(String(message.text || "").slice(0, 20000), settings);
  },
  async "local.status"() { return Shield.local.status(await Shield.loadSettings()); },
  async "local.testAi"() { return Shield.local.testAi(await Shield.loadSettings()); },
  async "local.wireguard"(message) { return Shield.local.wireguard(String(message.action || "status"), message.name); },
  async "local.opensnitch"(message) {
    if (message.action === "sync") return Shield.local.opensnitch("sync", await Shield.sec.confirmedHosts());
    return Shield.local.opensnitch("status");
  },
  async "sec.yaraCheck"() {
    const r = await Shield.sec.yaraRules();
    return { bundled: r.bundled, yours: r.yours, skipped: r.skipped, errors: r.errors };
  },
  async "sec.domainAge"(message) {
    const settings = await Shield.loadSettings();
    if (settings.localOnly) return { error: "send nothing anywhere is on" };
    return Shield.sec.domainAge(String(message.host || ""));
  },
  async "sec.scanUrl"(message) {
    const url = String(message.url || "");
    if (!/^https?:\/\//i.test(url)) return { error: "give a web address of the file" };
    const result = await Shield.sec.fetchAndScan(url, Shield.hostOf(url) && decodeURIComponent(new URL(url).pathname.split("/").pop() || "file"));
    const local = await Shield.sec.lookupHash(result.sha256);
    const settings = await Shield.loadSettings();
    const bazaar = !local && settings.secCenter.abuseKey && !settings.localOnly ? await Shield.sec.malwareBazaar(result.sha256, settings.secCenter.abuseKey).catch((error) => ({ error: String(error) })) : null;
    const knownMalware = Boolean(local || (bazaar && bazaar.known));
    await Shield.sec.record("file.scan", { url, data: { name: result.name, sha256: result.sha256, type: result.type, size: result.size, findings: result.findings, disguised: result.disguised, activeContent: result.activeContent, yara: result.yara, yaraMatch: result.yaraMatch, knownMalware, entries: result.entries.slice(0, 30).map((e) => e.name) } });
    return Object.assign(result, { knownMalware, bazaar, local });
  },
  async "sec.files"() {
    return { list: (await Shield.sec.query({ kind: "file.scan" })).slice(-60).reverse() };
  },
  async "sec.identity"(message) {
    const settings = await Shield.loadSettings();
    if (message.watch) {
      const watch = String(message.watch).split(/[\s,;]+/).map((x) => x.trim().toLowerCase()).filter((x) => /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/.test(x)).slice(0, 10);
      await Shield.updateSettings({ secCenter: { watch } });
      return { watch };
    }
    if (message.check) return { results: await Shield.sec.checkIdentities(await Shield.loadSettings()) };
    const stored = await api.storage.local.get("secIdentity");
    return { watch: settings.secCenter.watch, state: stored.secIdentity || {}, hasKey: Boolean(settings.security.hibpKey) };
  },
  async "sec.removals"(message) { return { list: await Shield.sec.removals(message.change || null) }; },
  async "sec.sync"() { return Shield.sec.syncIndicators(); },
  async "sec.devices"() {
    const status = await Shield.sec.deviceStatus();
    const remote = api.storage.sync ? await api.storage.sync.get("secReceipts").catch(() => ({})) : {};
    const self = await Shield.installId();
    return Object.assign(status, { devices: Object.entries(remote.secReceipts || {}).map(([id, r]) => Object.assign({ id, self: id === self }, r)) });
  },
  async "sec.audit"(message) {
    let tabId = message.tabId;
    let url = message.url;
    if (!url || tabId === undefined) {
      const [tab] = await api.tabs.query({ active: true, currentWindow: true });
      if (tab) { tabId = tab.id; url = tab.url; }
    }
    if (!url || !/^https?:/.test(url)) return { error: "nothing to audit on this page" };
    const https = url.startsWith("https:");
    const host = Shield.hostOf(url);

    // headers: prefer what the tab's main document already returned; else read them once
    let headers = null;
    const cached = secHeaderCache.get(tabId);
    if (cached && cached.url === url) headers = cached.headers;
    if (!headers) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        const response = await fetch(url, { credentials: "omit", redirect: "follow", cache: "no-store", signal: controller.signal, headers: { accept: "text/html,*/*;q=0.5" } });
        clearTimeout(timer);
        headers = {};
        response.headers.forEach((value, name) => { headers[name.toLowerCase()] = value; });
      } catch (error) { headers = {}; }
    }

    // cookies: real flags from the browser's store
    let cookies = [], cookieValues = [];
    try { const all = await api.cookies.getAll({ url }); cookies = all.map((c) => ({ name: c.name, secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite, domain: c.domain })); cookieValues = all.map((c) => ({ name: c.name, value: c.value })); } catch {}
    const hasSession = cookies.some((c) => /sess|sid|auth|token|login|jwt|phpsessid|jsessionid/i.test(c.name));

    // page facts from the content collector (best-effort)
    let facts = { https, host };
    try { const f = await api.tabs.sendMessage(tabId, { type: "audit.facts" }); if (f && !f.error) facts = f; } catch {}

    // grade the domains / subdomains the page pulled from, flagging any on a threat list
    let hostFacts = Array.isArray(facts.hosts) ? facts.hosts : [];
    for (const h of hostFacts) {
      try { const hits = await Shield.sec.lookup("https://" + h.host + "/", h.host); if (hits && hits.length) h.bad = hits[0].category || hits[0].source || "threat list"; } catch {}
    }
    const hostAudit = Shield.sec.auditHosts(hostFacts);

    // untrusted-deserialization exposure (cwe-502) from cookies, url and page storage
    const deser = Shield.sec.auditDeserialization({ cookies: cookieValues, url, serialStorage: facts.serialStorage, viewstate: facts.viewstate });
    // attack-vector surface checks (open redirect, session-in-url, cookie scope, CORS null, CSRF token, service worker, clickfix)
    const vectors = Shield.sec.auditVectors({ url, host, headers, cookies, links: facts.links, forms: facts.forms, serviceWorkers: facts.serviceWorkers, hasSession, textSignals: facts.textSignals });

    const headerAudit = Shield.sec.auditHeaders(headers, { https, url, host, cookies });
    const pageAudit = Shield.sec.auditPage(facts);
    pageAudit.findings = pageAudit.findings.concat(hostAudit.findings, deser.findings, vectors.findings);
    const report = Shield.sec.auditMerge(headerAudit, pageAudit);
    report.domains = hostAudit.list;
    report.thirdParties = hostAudit.thirdParties;
    report.coverage = Shield.sec.vectorCoverage();
    report.host = host;
    report.url = url;
    report.at = Date.now();

    // keep a short per-host history so grades can be compared over time
    try {
      const store = (await api.storage.local.get("secAuditHistory")).secAuditHistory || {};
      const list = store[host] || [];
      if (!list.length || list[list.length - 1].grade !== report.grade || list[list.length - 1].score !== report.score) list.push({ grade: report.grade, score: report.score, failed: report.failed, at: report.at });
      store[host] = list.slice(-20);
      await api.storage.local.set({ secAuditHistory: store });
    } catch {}

    return report;
  },
  async "sec.auditHistory"(message) {
    const store = (await api.storage.local.get("secAuditHistory")).secAuditHistory || {};
    if (message && message.host) return { host: message.host, list: store[message.host] || [] };
    const hosts = Object.entries(store).map(([host, list]) => ({ host, last: list[list.length - 1] })).sort((a, b) => (b.last.at || 0) - (a.last.at || 0));
    return { hosts };
  },
  async "media.clean"(message) {
    const url = message.url;
    if (!url || !/^https?:/.test(url)) return { error: "no file to clean on this page" };
    let buf;
    try {
      const resp = await fetch(url, { credentials: "include", cache: "no-store" });
      if (!resp.ok) return { error: "the site answered " + resp.status };
      const declared = Number(resp.headers.get("content-length") || 0);
      if (declared > 60 * 1024 * 1024) return { error: "over 60 MB; not processed" };
      buf = new Uint8Array(await resp.arrayBuffer());
    } catch (error) { return { error: String(error.message || error) }; }
    if (buf.length > 60 * 1024 * 1024) return { error: "over 60 MB; not processed" };
    const r = await Shield.media.clean(buf, { dropColor: !!message.dropColor, recompress: message.recompress !== false });
    if (!r.ok) return { error: r.note, format: r.format };
    const ext = r.format === "jpeg" ? "jpg" : r.format;
    const mime = { jpeg: "image/jpeg", png: "image/png", gif: "image/gif", webp: "image/webp" }[r.format] || "application/octet-stream";
    const base = String(message.name || "file").replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9 ._-]/g, "_").slice(0, 80) || "file";
    const filename = base + "-clean." + ext;
    // base64 the cleaned bytes for a data: download (service worker has no object URLs)
    let binary = "";
    for (let i = 0; i < r.bytes.length; i += 8192) binary += String.fromCharCode.apply(null, r.bytes.subarray(i, i + 8192));
    const dataUrl = "data:" + mime + ";base64," + btoa(binary);
    let downloadId = null;
    try { downloadId = await api.downloads.download({ url: dataUrl, filename, saveAs: true, conflictAction: "uniquify" }); } catch (error) { return { error: "cleaned, but could not start the download: " + String(error.message || error) }; }
    await Shield.sec.record("file.clean", { url, data: { name: filename, format: r.format, before: r.before, after: r.after, saved: r.saved, savedPct: r.savedPct, removed: r.removed } }).catch(() => {});
    return { ok: true, format: r.format, before: r.before, after: r.after, saved: r.saved, savedPct: r.savedPct, removed: r.removed, note: r.note, name: filename, downloadId };
  },
  async "sec.clear"() {
    await Shield.sec.clearEvents(); await Shield.sec.clearGraph(); await Shield.sec.clearCases();
    return { ok: true };
  },
  async "worker.build"() {
    return { build: Shield.BUILD, version: api.runtime.getManifest().version };
  },
  async "network.status"() {
    return Shield.networkStatus(await Shield.loadSettings());
  },
  async "network.allowHttp"(message) {
    const url = String(message.url || "");
    if (!/^http:\/\//i.test(url)) return { error: "not a plain http address" };
    await Shield.allowHttp(Shield.hostOf(url));
    await Shield.count("httpFallback", 1);
    await Shield.log({ kind: "network", site: Shield.siteOf(Shield.hostOf(url)), text: "you opened " + Shield.hostOf(url) + " over plain http", detail: "anyone on this network can read this page" });
    return { ok: true };
  },
  async "network.secureDns"() {
    const page = Shield.secureDnsPage();
    if (!page) return { error: "firefox: settings → privacy & security → dns over https" };
    await api.tabs.create({ url: page });
    return { ok: true };
  },
  async "download.info"(message) {
    const session = await api.storage.session.get("downloads");
    const entry = (session.downloads || {})[String(message.id)];
    return entry || { error: "unknown download" };
  },
  async "download.decide"(message) {
    const id = Number(message.id);
    try {
      if (message.keep) {
        await api.downloads.resume(id).catch(() => {});
      } else {
        // A small file may have finished before the hold; the file itself goes too.
        await api.downloads.cancel(id).catch(() => {});
        await api.downloads.removeFile(id).catch(() => {});
        await api.downloads.erase({ id });
      }
    } catch (error) {
      return { error: String(error.message || error) };
    }
    if (!message.keep) await Shield.count("downloads", 1);
    // Several risky downloads share one tab: hand back the next one still held.
    const session = await api.storage.session.get("downloads");
    const pending = session.downloads || {};
    delete pending[String(id)];
    await api.storage.session.set({ downloads: pending });
    const next = Object.keys(pending)[0];
    return { ok: true, next: next ? Number(next) : null };
  },
  async "shop.compare"(message, sender) {
    if (!allowRate("shop", sender, 6)) return { error: "too many lookups", limited: true };
    const product = message.product || {};
    if (typeof product.title !== "string" || product.title.length < 4) return { error: "no product" };
    const settings = await Shield.loadSettings();
    const clean = { ...product, title: product.title.slice(0, 300) };
    const home = (settings.shopping.homeCurrency || clean.currency || "USD").toUpperCase();
    const [base, market] = await Promise.all([
      Shield.compareProduct(clean),
      settings.localOnly || !settings.shopping.webSearch
        ? Promise.resolve(null)
        : Shield.marketOffers(clean, { homeCurrency: home, foreign: settings.shopping.foreign }).catch(() => null),
    ]);
    // The big stores answer in the page's currency; shown in the home currency when that differs.
    if (home !== base.currency) {
      const table = await Shield.rates();
      for (const offer of base.offers) {
        const converted = Shield.convert(offer.total, base.currency, home, table);
        if (converted !== null) { offer.nativeTotal = offer.total; offer.nativeCurrency = base.currency; offer.total = converted; offer.converted = true; }
      }
      base.cheaper = base.offers.filter((offer) => base.price && offer.total < Shield.convert(base.price, base.currency, home, table));
    }
    for (const offer of base.offers) { offer.independent = false; offer.foreign = false; }
    const homePrice = home === base.currency ? base.price : (Shield.convert(base.price, base.currency, home, await Shield.rates()) || base.price);
    const web = market ? market.offers : [];
    return {
      ...base,
      home,
      homePrice,
      web,
      webCheaper: web.filter((offer) => homePrice && offer.total < homePrice),
      independent: web.filter((offer) => offer.independent && !offer.foreign),
      foreign: web.filter((offer) => offer.foreign),
      rates: market ? market.rates : null,
      regions: market ? market.regions : [],
    };
  },
  async "shop.codes"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    const codes = await Shield.codesFor(site, settings);
    if (settings.shopping.webCoupons && !settings.localOnly && allowRate("coupons", sender, 3)) {
      const known = new Set(codes.map((entry) => entry.code));
      try {
        for (const code of await Shield.findCoupons(site)) {
          if (!known.has(code)) { known.add(code); codes.push({ code, source: "found on the web", description: "" }); }
        }
      } catch { /* the checkout still has the rest */ }
    }
    return { site, codes: codes.slice(0, 18) };
  },
  // content/cookie_consent.js and content/dark_patterns.js ask whether to run here.
  async "cookie.config"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    return { config: { cookieDeception: settings.annoyances.cookieDeception && settings.annoyances.banners !== false && !settings.privacy.trustedSites.includes(site) } };
  },
  async "dark.config"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    return { config: { darkPatterns: settings.annoyances.darkPatterns && !settings.privacy.trustedSites.includes(site) } };
  },
  // Medicines, vitamins and remedies: who is behind the brand, and herbal alternatives.
  async "shop.pharma"(message, sender) {
    const settings = await Shield.loadSettings();
    if (!settings.shopping.pharmaWarn) return { medicine: false };
    const hints = message.hints || {};
    const clean = {};
    for (const key of ["title", "brand", "manufacturer", "seller", "breadcrumb", "facts", "url"]) clean[key] = String(hints[key] || "").slice(0, key === "facts" ? 4000 : 400);
    const result = Shield.pharmaCheck(clean);
    if (result.medicine && result.category && !settings.localOnly && allowRate("shop", sender, 6)) {
      const home = (settings.shopping.homeCurrency || hints.currency || "USD").toUpperCase();
      result.webOffers = await Shield.herbalOffers(result.category.id, home).catch(() => []);
      result.home = home;
    }
    return result;
  },
  async "shop.seen"(message, sender) {
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    for (const code of (Array.isArray(message.codes) ? message.codes : []).slice(0, 10)) {
      await Shield.rememberCode(site, String(code).toUpperCase(), false);
    }
    return { ok: true };
  },
  async "shop.worked"(message, sender) {
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    await Shield.rememberCode(site, String(message.code || "").toUpperCase(), true);
    return { ok: true };
  },
  async "shop.saved"(message) {
    await Shield.count("saved", Math.round(Number(message.amount) || 0));
    return { ok: true };
  },
  async "shop.compared"() {
    await Shield.count("compared", 1);
    return { ok: true };
  },
  async "shop.price"(message) {
    const product = message.product || {};
    if (typeof product.url !== "string") return {};
    const summary = await Shield.recordPrice(product);
    return summary || {};
  },
  async "shop.watch"(message) {
    const product = message.product || {};
    if (typeof product.url !== "string") return { error: "no product" };
    return Shield.watchProduct(product);
  },
  async "shop.unwatch"(message) {
    return Shield.unwatchProduct(String(message.url || ""));
  },
  async "shop.watchlist"() {
    const stored = await api.storage.local.get(["watchlist", "receipts", "reminders"]);
    return { watchlist: stored.watchlist || [], receipts: stored.receipts || [], reminders: stored.reminders || [], spending: Shield.spendingByStore(stored.receipts || []) };
  },
  async "shop.checkWatchlist"() {
    await Shield.checkWatchlist(announceDrop);
    return { ok: true };
  },
  async "shop.storeCheck"(message, sender) {
    const settings = await Shield.loadSettings();
    if (settings.localOnly || !allowRate("shop", sender, 6)) return { verdict: "unknown", warnings: [], days: null };
    return Shield.storeCheck(Shield.hostOf(sender.url || ""), { tooGood: Boolean(message.tooGood), http: Boolean(message.http) });
  },
  async "shop.reddit"(message, sender) {
    const settings = await Shield.loadSettings();
    if (settings.localOnly || !allowRate("shop", sender, 6)) return { threads: [], searchUrl: null };
    return Shield.redditThreads(String(message.query || "").slice(0, 120));
  },
  async "shop.remind"(message) {
    const days = Math.min(365, Math.max(1, Number(message.days) || 1));
    const entry = await Shield.addReminder({ at: Date.now() + days * 86400000, label: message.label, url: message.url, kind: message.kind });
    return { reminder: entry };
  },
  async "shop.receipt"(message) {
    return Shield.saveReceipt(message.receipt || {});
  },
  async "shop.warranty"(message) {
    const stored = await api.storage.local.get("receipts");
    const receipts = stored.receipts || [];
    const receipt = receipts.find((entry) => entry.url === message.url);
    if (!receipt) return { error: "no such receipt" };
    const months = Math.min(120, Math.max(1, Number(message.months) || 12));
    receipt.warrantyMonths = months;
    await api.storage.local.set({ receipts });
    const ends = Date.parse(receipt.at) + months * 30 * 86400000;
    await Shield.addReminder({ at: ends - 14 * 86400000, label: "Warranty ends in two weeks: " + (receipt.title || receipt.site), url: receipt.url, kind: "warranty" });
    return { ok: true };
  },
  async "shop.quiet"(message, sender) {
    const settings = await Shield.loadSettings();
    const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
    if (!site) return { error: "no site" };
    await Shield.updateSettings({ shopping: { quietSites: toggleInList(settings.shopping.quietSites, site, true) } });
    return { ok: true };
  },
  async "spaces.config"() {
    const settings = await Shield.loadSettings();
    return { spaces: settings.spaces };
  },
  async "spaces.set"(message) {
    const change = { spaces: message.change || {} };
    const settings = await Shield.updateSettings(change);
    // Broadcast to every Twitter/X tab so panels appear or vanish without a reload.
    try {
      const tabs = await api.tabs.query({ url: ["https://twitter.com/*", "https://*.twitter.com/*", "https://x.com/*", "https://*.x.com/*"] });
      for (const tab of tabs) {
        try { await api.tabs.sendMessage(tab.id, { type: "spaces.set", spaces: settings.spaces }); } catch {}
      }
    } catch {}
    return { spaces: settings.spaces };
  },
  async "persona.config"() {
    const settings = await Shield.loadSettings();
    const prompt = await Shield.loadShepherdPrompt();
    return { persona: settings.persona, prompt };
  },
  async "persona.set"(message) {
    const change = { persona: message.change || {} };
    const settings = await Shield.updateSettings(change);
    const prompt = await Shield.loadShepherdPrompt();
    try {
      const tabs = await api.tabs.query({});
      for (const tab of tabs) {
        try { await api.tabs.sendMessage(tab.id, { type: "persona.set", persona: settings.persona, prompt }); } catch {}
      }
    } catch {}
    return { persona: settings.persona };
  },
  async "persona.consentCheck"() {
    const settings = await Shield.loadSettings();
    return { granted: Boolean(settings.persona.consent) };
  },
  async "persona.reseed"() {
    try {
      const tabs = await api.tabs.query({ active: true, currentWindow: true });
      if (tabs && tabs[0]) await api.tabs.sendMessage(tabs[0].id, { type: "persona.reseed" });
    } catch {}
    return { ok: true };
  },
  async "profile.config"() {
    const settings = await Shield.loadSettings();
    return { profile: settings.profileIntel };
  },
  async "profile.set"(message) {
    const change = { profileIntel: message.change || {} };
    const settings = await Shield.updateSettings(change);
    try {
      const tabs = await api.tabs.query({ url: ["https://twitter.com/*", "https://*.twitter.com/*", "https://x.com/*", "https://*.x.com/*"] });
      for (const tab of tabs) {
        try { await api.tabs.sendMessage(tab.id, { type: "profile.set", profile: settings.profileIntel }); } catch {}
      }
    } catch {}
    return { profile: settings.profileIntel };
  },
  async "yt.adPatterns"() {
    const settings = await Shield.loadSettings();
    const extra = (settings.social && settings.social.youtube && settings.social.youtube.adKeys) || [];
    const feed = (Shield.ytAdPatterns && Shield.ytAdPatterns()) || {};
    return { adKeys: [...new Set([...(feed.adKeys || []), ...extra])], enforce: feed.enforce || "" };
  },
  async "yt.novelAdKey"(message) {
    // A pattern the page script had not seen. Keep the recent ones so an
    // update to the shield's rules feed can fold them into the default set.
    const key = String(message.key || "").toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 60);
    if (!key) return { ok: false };
    const store = await api.storage.local.get("ytNovelAdKeys");
    const list = Array.isArray(store.ytNovelAdKeys) ? store.ytNovelAdKeys : [];
    if (!list.includes(key)) { list.push(key); await api.storage.local.set({ ytNovelAdKeys: list.slice(-200) }); }
    return { ok: true };
  },
  async "social.config"(message) {
    const settings = await Shield.loadSettings();
    const platform = String(message.platform || "");
    const valid = ["instagram", "tiktok", "reddit", "youtube", "linkedin", "twitter"];
    if (!valid.includes(platform)) return { config: {} };
    return { config: (settings.social && settings.social[platform]) || {} };
  },
  async "social.set"(message) {
    const platform = String(message.platform || "");
    const valid = ["instagram", "tiktok", "reddit", "youtube", "linkedin", "twitter"];
    if (!valid.includes(platform)) return { ok: false };
    const settings = await Shield.loadSettings();
    const current = (settings.social && settings.social[platform]) || {};
    const updated = { ...current, ...(message.change || message.config || {}) };
    const socialSettings = { ...((settings.social) || {}), [platform]: updated };
    await Shield.updateSettings({ social: socialSettings });
    // Broadcast to relevant tabs
    const urlMap = {
      instagram: ["https://www.instagram.com/*", "https://instagram.com/*"],
      tiktok: ["https://www.tiktok.com/*", "https://tiktok.com/*"],
      reddit: ["https://www.reddit.com/*", "https://old.reddit.com/*", "https://reddit.com/*"],
      youtube: ["https://www.youtube.com/*", "https://youtube.com/*", "https://m.youtube.com/*"],
      twitter: ["https://twitter.com/*", "https://*.twitter.com/*", "https://x.com/*", "https://*.x.com/*"],
      linkedin: ["https://www.linkedin.com/*", "https://linkedin.com/*"],
    };
    try {
      const tabs = await api.tabs.query({ url: urlMap[platform] });
      for (const tab of tabs) {
        try { await api.tabs.sendMessage(tab.id, { type: "social.set", platform, config: updated }); } catch {}
      }
    } catch {}
    return { ok: true, config: updated };
  },
  async "inspect.enabled"(message, sender) {
    const tabId = sender.tab ? sender.tab.id : (message && message.tabId);
    if (tabId == null) return { enabled: false };
    const stored = await api.storage.session.get("inspectTabs");
    const map = stored.inspectTabs || {};
    return { enabled: Boolean(map[String(tabId)]) };
  },
  async "inspect.arm.self"(message, sender) {
    const tabId = sender.tab ? sender.tab.id : null;
    if (tabId == null) return { error: "no tab" };
    const stored = await api.storage.session.get("inspectTabs");
    const map = stored.inspectTabs || {};
    map[String(tabId)] = { at: Date.now() };
    await api.storage.session.set({ inspectTabs: map });
    return { enabled: true };
  },
  async "inspect.arm"(message) {
    const tabId = Number(message && message.tabId);
    if (!Number.isFinite(tabId)) return { error: "no tabId" };
    const stored = await api.storage.session.get("inspectTabs");
    const map = stored.inspectTabs || {};
    const on = Boolean(message.on);
    if (on) map[String(tabId)] = { at: Date.now() };
    else delete map[String(tabId)];
    await api.storage.session.set({ inspectTabs: map });
    try {
      await api.tabs.sendMessage(tabId, { type: "inspect.set", enabled: on });
    } catch {}
    return { enabled: on };
  },
  async "inspect.status"(message) {
    const tabId = Number(message && message.tabId);
    const stored = await api.storage.session.get("inspectTabs");
    const map = stored.inspectTabs || {};
    return { enabled: Boolean(map[String(tabId)]) };
  },

  // ── Downloader: return network-intercepted assets for a tab ──────────────
  async "downloader.assets"(message) {
    const tabId = Number(message && message.tabId);
    if (!Number.isFinite(tabId)) return { assets: [] };
    const store = (await api.storage.session.get('dlAssets')).dlAssets || {};
    const tabData = store[tabId] || {};
    return { assets: Object.values(tabData) };
  },

  // ── Downloader: content script reports DOM-found items ───────────────────
  async "downloader.found"(message, sender) {
    const tabId = sender && sender.tab && sender.tab.id;
    if (!tabId) return { ok: false };
    const store = (await api.storage.session.get('dlAssets')).dlAssets || {};
    if (!store[tabId]) store[tabId] = {};
    for (const item of (message.items || [])) store[tabId][item.url] = item;
    await api.storage.session.set({ dlAssets: store });
    return { ok: true };
  },
};

// ── Downloader: per-tab media asset store (storage.session — survives SW restart) ──
// Every media response used to read and write storage.session on its own,
// one round trip per picture on every tab. Responses are now gathered in
// memory and written every three seconds, at most 300 per tab.
const mediaBuffer = new Map(); // tabId -> Map(url -> item)
let mediaFlushTimer = null;
async function flushMediaBuffer() {
  mediaFlushTimer = null;
  if (!mediaBuffer.size) return;
  const batch = new Map(mediaBuffer);
  mediaBuffer.clear();
  try {
    const store = (await api.storage.session.get('dlAssets')).dlAssets || {};
    for (const [tabId, items] of batch) {
      const bucket = store[tabId] || {};
      for (const [url, item] of items) bucket[url] = item;
      const keys = Object.keys(bucket);
      if (keys.length > 300) for (const key of keys.slice(0, keys.length - 300)) delete bucket[key];
      store[tabId] = bucket;
    }
    await api.storage.session.set({ dlAssets: store });
  } catch { /* the panel rescans the page when opened */ }
}
// ---- security center sensors ------------------------------------------------------------------
// What the browser itself observes, turned into events (lib/sec/events.js).
// Each third-party host is recorded once per page, with the address it was
// served from: enough for the dashboard, the graph and the intel checks,
// without a row per pixel.
const secPerTab = new Map();      // tabId -> Set of keys already recorded on this page
const secPageSite = new Map();    // tabId -> site of the page
const secChains = new Map();      // tabId -> redirect chain of the last navigation
const secSiteFirst = new Map();   // site -> first time a page of it opened (this session)
function secSeen(tabId, key, write) {
  let seen = secPerTab.get(tabId);
  if (!seen) { seen = new Set(); secPerTab.set(tabId, seen); }
  if (seen.has(key) || seen.size > 400) return;
  seen.add(key);
  Promise.resolve().then(write).catch(() => {});
}
async function secNavCommitted(details) {
  if (!/^https?:/.test(details.url || "")) return;
  secPerTab.set(details.tabId, new Set());
  const host = Shield.hostOf(details.url);
  const site = Shield.siteOf(host);
  secPageSite.set(details.tabId, site);
  if (!secSiteFirst.has(site)) secSiteFirst.set(site, Date.now());
  const chain = secChains.get(details.tabId);
  secChains.delete(details.tabId);
  if (chain && chain.length > 1 && Date.now() - chain.at < 20000) {
    const sites = chain.map((u) => Shield.siteOf(Shield.hostOf(u)));
    let crossSiteHops = 0;
    for (let i = 1; i < sites.length; i++) if (sites[i] !== sites[i - 1]) crossSiteHops++;
    await Shield.sec.record("nav.redirect", { tab: details.tabId, url: details.url, data: { from: chain[0], to: chain[chain.length - 1], hops: chain.length - 1, crossSiteHops, chain: chain.slice(0, 12).map((u) => Shield.hostOf(u)) } });
  }
}
if (api.webRequest && api.webRequest.onCompleted) {
  api.webRequest.onCompleted.addListener((details) => {
    if (details.tabId < 0 || !/^https?:/.test(details.url)) return;
    const host = Shield.hostOf(details.url);
    if (details.type === "main_frame") {
      Shield.sec.record("nav.commit", { tab: details.tabId, url: details.url, ip: details.ip || "", data: { status: details.statusCode, fromCache: Boolean(details.fromCache) } }).catch(() => {});
      return;
    }
    const pageSite = secPageSite.get(details.tabId) || "";
    const thirdParty = Boolean(pageSite) && Shield.siteOf(host) !== pageSite;
    secSeen(details.tabId, "r|" + host, () => {
      const owner = Shield.ownerOf ? Shield.ownerOf(host) : null;
      return Shield.sec.record("request", { tab: details.tabId, url: details.url.split("?")[0], ip: details.ip || "", data: { type: details.type, thirdParty, pageSite, status: details.statusCode, owner: owner ? owner.owner : undefined } });
    });
  }, { urls: ["<all_urls>"] });
}
// Latest main-document response headers per tab, for the passive site audit.
// Only the top document, only standard response headers — nothing is probed.
const secHeaderCache = new Map();
if (api.webRequest && api.webRequest.onHeadersReceived) {
  const extra = [];
  try { if (api.webRequest.OnHeadersReceivedOptions && api.webRequest.OnHeadersReceivedOptions.EXTRA_HEADERS) extra.push("extraHeaders"); } catch {}
  api.webRequest.onHeadersReceived.addListener((details) => {
    if (details.type !== "main_frame" || details.tabId < 0 || !/^https?:/.test(details.url)) return;
    const map = {};
    for (const h of details.responseHeaders || []) {
      const name = h.name.toLowerCase();
      if (name === "set-cookie") continue; // cookies come from the cookie store, with real flags
      map[name] = map[name] ? map[name] + ", " + (h.value || "") : (h.value || "");
    }
    secHeaderCache.set(details.tabId, { url: details.url, https: details.url.startsWith("https:"), headers: map, at: Date.now() });
  }, { urls: ["<all_urls>"], types: ["main_frame"] }, ["responseHeaders"].concat(extra));
  api.tabs.onRemoved.addListener((tabId) => secHeaderCache.delete(tabId));
}

Shield.sec.start();
Shield.sec.extensionSnapshot(true).catch(() => {});
if (api.management && api.management.onInstalled) {
  for (const name of ["onInstalled", "onUninstalled", "onEnabled"]) api.management[name].addListener(() => { setTimeout(() => Shield.sec.extensionSnapshot(true).catch(() => {}), 500); });
}
async function secScanDownload(item, concern, settings) {
  if (!settings.secCenter.enabled || !settings.secCenter.scanFiles || settings.localOnly === "strict") return null;
  let result;
  try {
    result = await Shield.sec.fetchAndScan(item.finalUrl || item.url, concern.name);
  } catch (error) {
    return { error: String(error.message || error) };
  }
  const local = await Shield.sec.lookupHash(result.sha256);
  let bazaar = null;
  if (!local && settings.secCenter.abuseKey && !settings.localOnly) bazaar = await Shield.sec.malwareBazaar(result.sha256, settings.secCenter.abuseKey).catch((error) => ({ error: String(error) }));
  const knownMalware = Boolean(local || (bazaar && bazaar.known));
  if (knownMalware) result.findings.unshift("matches known malware" + (bazaar && bazaar.signature ? " (" + bazaar.signature + ")" : local ? " (" + local.source + ")" : ""));
  await Shield.sec.record("file.scan", { url: item.url, data: { downloadId: item.id, name: concern.name, sha256: result.sha256, type: result.type, size: result.size, findings: result.findings, disguised: result.disguised, activeContent: result.activeContent, yara: result.yara, yaraMatch: result.yaraMatch, knownMalware, bazaar, entries: result.entries.slice(0, 30).map((e) => e.name) } });
  return Object.assign(result, { knownMalware, bazaar });
}

if (api.webRequest && api.webRequest.onCompleted) {
  api.webRequest.onCompleted.addListener(
    (details) => {
      if (!details.tabId || details.tabId < 0) return;
      const url = details.url;
      if (!url || !/^https?:/.test(url)) return;
      const mime = (details.responseHeaders || []).find(h => h.name.toLowerCase() === 'content-type');
      const mimeType = mime ? mime.value.split(';')[0].trim() : '';
      let type = null;
      if (/^video\//i.test(mimeType) || /\.(mp4|webm|mkv|mov|avi|m3u8|mpd|ts)(\?|$)/i.test(url)) type = 'video';
      else if (/^audio\//i.test(mimeType) || /\.(mp3|wav|ogg|flac|aac|m4a)(\?|$)/i.test(url)) type = 'audio';
      else if (/^image\//i.test(mimeType) || /\.(jpg|jpeg|png|gif|webp|svg|avif)(\?|$)/i.test(url)) type = 'image';
      else if (/\.(pdf|docx?|xlsx?|pptx?|zip)(\?|$)/i.test(url)) type = 'document';
      if (!type) return;
      // Tiny pictures (icons, pixels, sprites) are not downloads.
      const length = (details.responseHeaders || []).find(h => h.name.toLowerCase() === 'content-length');
      if (type === 'image' && length && Number(length.value) < 20000) return;
      const filename = (() => { try { const p = new URL(url).pathname; return decodeURIComponent(p.split('/').filter(Boolean).pop() || 'download').slice(0, 120); } catch { return 'download'; } })();
      let bucket = mediaBuffer.get(details.tabId);
      if (!bucket) { bucket = new Map(); mediaBuffer.set(details.tabId, bucket); }
      if (bucket.size < 300) bucket.set(url, { url, type, mimeType, filename });
      if (!mediaFlushTimer) mediaFlushTimer = setTimeout(flushMediaBuffer, 3000);
    },
    { urls: ['<all_urls>'] },
    ['responseHeaders']
  );
}

// Clean up stored assets when a tab closes
if (api.tabs && api.tabs.onRemoved) {
  api.tabs.onRemoved.addListener(async (tabId) => {
    const store = (await api.storage.session.get('dlAssets')).dlAssets || {};
    if (store[tabId]) {
      delete store[tabId];
      await api.storage.session.set({ dlAssets: store });
    }
  });
}

async function applyModes(settings) {
  await Shield.applyFocusHours(settings).catch((error) => console.warn("shield: focus hours", error));
  await Shield.applyLowData(settings).catch((error) => console.warn("shield: low data", error));
  await Shield.applySearchSwitch(settings).catch((error) => console.warn("shield: search", error));
  await Shield.applyParental(settings).catch((error) => console.warn("shield: parental", error));
}

// Banking mode pauses the other extensions while a banking site is in front.
api.tabs.onActivated.addListener((info) => {
  (async () => {
    const settings = await Shield.loadSettings();
    if (!settings.modes.pauseExtensionsForBanking) return;
    const tab = await api.tabs.get(info.tabId).catch(() => null);
    const site = tab ? Shield.siteOf(Shield.hostOf(tab.url || "")) : "";
    const banking = site && settings.modes.siteModes[site] === "banking";
    await Shield.pauseOtherExtensions(Boolean(banking));
  })().catch((error) => console.warn("shield: banking pause", error));
});

// Redirect hops of each tab's last navigation, for the chain viewer.
if (api.webRequest && api.webRequest.onBeforeRedirect) {
  api.webRequest.onBeforeRedirect.addListener((details) => {
    if (details.type !== "main_frame" || details.tabId < 0) return;
    if (Shield.noteUpgrade(details.tabId, details.url, details.redirectUrl || "")) Shield.count("upgrades", 1).catch(() => {});
    const chain = secChains.get(details.tabId) || [];
    if (!chain.length || Date.now() - chain.at > 20000) { chain.length = 0; chain.push(details.url); }
    chain.push(details.redirectUrl || "");
    chain.at = Date.now();
    secChains.set(details.tabId, chain);
    Shield.recordHop(details.tabId, details.url, details.redirectUrl).catch(() => {});
  }, { urls: ["<all_urls>"] });
}
if (api.webNavigation) {
  api.webNavigation.onBeforeNavigate.addListener((details) => {
    if (details.frameId === 0 && details.parentFrameId === -1) Shield.resetHops(details.tabId, details.url).catch(() => {});
  });
}

// A page that was moved to https and then failed: the site has no secure
// version. It opens over plain http for that site alone (or asks first on
// public wifi), so the upgrade never costs you the site.
if (api.webNavigation && api.webNavigation.onErrorOccurred) {
  api.webNavigation.onErrorOccurred.addListener((details) => {
    if (details.frameId !== 0 || !/^https:/.test(details.url)) return;
    Shield.loadSettings().then((settings) => Shield.upgradeFailed(details.tabId, details.url, details.error, settings)).catch((error) => console.warn("shield: http fallback", error));
  });
}

// Downloads that expire, and the alarm that removes them.
if (api.downloads && api.downloads.onChanged) {
  api.downloads.onChanged.addListener((delta) => {
    if (!delta.state || delta.state.current !== "complete") return;
    (async () => {
      const [item] = await api.downloads.search({ id: delta.id });
      if (!item) return;
      const settings = await Shield.loadSettings();
      await Shield.scheduleDownloadExpiry(item, settings);
    })().catch(() => {});
  });
}

async function locationFor(settings, trusted) {
  const city = trusted ? null : await Shield.effectiveLocation(settings);
  if (!city) return null;
  return { lat: city.lat, lon: city.lon, tz: city.tz, locale: city.locale, city: city.name, country: city.country };
}

// Stealth: the shield's own elements carry a name a page cannot look for.
async function elementTag(settings) {
  if (!settings.privacy.stealth) return "noah-shield";
  const session = await api.storage.session.get("elementTag");
  if (session.elementTag) return session.elementTag;
  const tag = "ns-" + Shield.hex(crypto.getRandomValues(new Uint8Array(4)));
  await api.storage.session.set({ elementTag: tag });
  return tag;
}

// Runs inside the page: fills the visible sign-up fields with the decoy.
function fillDecoy(identity) {
  const map = [
    [/first.?name|given/i, identity.firstName], [/last.?name|family|surname/i, identity.lastName], [/full.?name|^name$|your name/i, identity.fullName],
    [/e-?mail/i, identity.email], [/user.?name|login|handle/i, identity.username], [/pass/i, identity.password], [/phone|tel|mobile/i, identity.phone],
    [/street|address(?!.*email)/i, identity.street], [/city|town/i, identity.city], [/zip|postal/i, identity.postal], [/birth|dob/i, identity.birthday],
  ];
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  let filled = 0;
  for (const input of document.querySelectorAll("input")) {
    if (!/^(text|email|tel|password|search|url|date|)$/.test(input.type || "") || input.disabled || input.readOnly) continue;
    const box = input.getBoundingClientRect();
    if (box.width < 10 || box.height < 10) continue;
    const words = [input.name, input.id, input.placeholder, input.getAttribute("aria-label"), input.getAttribute("autocomplete"), input.labels && input.labels[0] && input.labels[0].textContent].filter(Boolean).join(" ");
    const match = map.find(([pattern]) => pattern.test(words));
    if (!match) continue;
    setter.call(input, input.type === "date" ? identity.birthday : match[1]);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    filled++;
  }
  return filled;
}

// Panic: every tab closed, history cleared, tunnel down.
Shield.panic = panic;
async function panic() {
  const settings = await Shield.loadSettings();
  if (settings.tunnel.enabled) await Shield.disconnectTunnel();
  const tabs = await api.tabs.query({});
  await api.tabs.create({ url: "about:blank" });
  await api.tabs.remove(tabs.map((tab) => tab.id));
  if (api.browsingData) {
    await api.browsingData.remove({ since: 0 }, { history: true, downloads: true, formData: true }).catch(() => {});
  }
  await api.storage.session.clear();
  await Shield.count("panics", 1);
}

// Every request a tab makes to somebody else is noted, blocked or not.
if (api.webRequest && api.webRequest.onBeforeRequest) {
  api.webRequest.onBeforeRequest.addListener((details) => {
    if (details.tabId < 0 || details.type === "main_frame") return;
    const host = Shield.hostOf(details.url);
    const tabSite = Shield.siteOf(Shield.hostOf(details.initiator || details.documentUrl || ""));
    if (!tabSite || Shield.siteOf(host) === tabSite) return;
    Shield.noteThirdParty(details.tabId, tabSite, host, false).catch(() => {});
  }, { urls: ["<all_urls>"] });
}

api.tabs.onUpdated.addListener((tabId, change, tab) => {
  if (change.url) Shield.rememberTabUrl(tabId, change.url).catch(() => {});
  if (change.status === "complete" && tab && tab.url) updateMeter(tabId, tab.url).catch(() => {});
});

async function updateMeter(tabId, url) {
  const settings = await Shield.loadSettings();
  if (settings.privacy.meter !== "grade" || !/^https?:/.test(url)) return;
  const score = await Shield.privacyScore(tabId, url);
  const action = api.action || api.browserAction;
  await action.setBadgeText({ tabId, text: score.grade });
  await action.setBadgeBackgroundColor({ tabId, color: score.grade === "A" ? "#2f5f2a" : score.grade === "B" ? "#4a5a2a" : score.grade === "C" ? "#6b5a1e" : "#6b2a2a" });
}

if (api.history && api.history.onVisited) {
  api.history.onVisited.addListener((item) => {
    Shield.loadSettings().then((settings) => Shield.forgetVisit(item.url, settings)).catch(() => {});
  });
}

if (api.idle && api.idle.onStateChanged) {
  api.idle.setDetectionInterval(15 * 60);
  api.idle.onStateChanged.addListener((state) => {
    if (state === "active") return;
    Shield.loadSettings().then((settings) => (settings.privacy.logoutSites.length ? Shield.idleLogout(settings) : 0)).catch(() => {});
  });
}

if (api.commands && api.commands.onCommand) {
  api.commands.onCommand.addListener((command) => {
    if (command === "panic") panic().catch((error) => console.error("shield: panic", error));
    if (command === "rotate-fingerprint") Shield.rotateFingerprint().catch(() => {});
  });
}

if (api.contextMenus) {
  api.runtime.onInstalled.addListener(() => {
    api.contextMenus.create({ id: "copy-clean-link", title: "Copy clean link (noah shield)", contexts: ["link"] });
    api.contextMenus.create({ id: "fill-decoy", title: "Fill this form with decoy details (noah shield)", contexts: ["editable"] });
    api.contextMenus.create({ id: "throwaway", title: "Open in a throwaway window (noah shield)", contexts: ["link"] });
    api.contextMenus.create({ id: "unshorten", title: "Where does this link go? (noah shield)", contexts: ["link"] });
    if (api.contextualIdentities) api.contextMenus.create({ id: "container", title: "Open in this site's own container (noah shield)", contexts: ["link", "page"] });
  });
  api.contextMenus.onClicked.addListener((info, tab) => {
    (async () => {
      if (info.menuItemId === "copy-clean-link" && tab) {
        const answer = await api.tabs.sendMessage(tab.id, { type: "links.cleanSelection", url: info.linkUrl }).catch(() => null);
        const cleaned = (answer && answer.cleaned) || info.linkUrl;
        await api.scripting.executeScript({ target: { tabId: tab.id }, func: (text) => navigator.clipboard.writeText(text), args: [cleaned] });
      }
      if (info.menuItemId === "fill-decoy" && tab) {
        await handlers["decoy.fill"]({ tabId: tab.id, site: Shield.siteOf(Shield.hostOf(tab.url || "")) });
      }
      if (info.menuItemId === "throwaway") await handlers["tools.throwaway"]({ url: info.linkUrl });
      if (info.menuItemId === "unshorten") await api.tabs.create({ url: api.runtime.getURL("tools.html") + "?unshorten=" + encodeURIComponent(info.linkUrl) });
      if (info.menuItemId === "container") await handlers["container.open"]({ url: info.linkUrl || info.pageUrl });
    })().catch((error) => console.warn("shield: menu", error));
  });
}

if (api.storage.sync && api.storage.onChanged) {
  api.storage.onChanged.addListener(async (changes, area) => {
    if (area !== "sync" || !changes.meta || !changes.meta.newValue) return;
    if (changes.meta.newValue.from === await Shield.installId()) return;
    handlers["sync.pull"]().catch(() => {});
  });
}

// A page whose host imitates a brand is replaced by the warning before it
// renders; the content script covers the moment in between.
if (api.webNavigation) {
  api.webNavigation.onBeforeNavigate.addListener((details) => {
    if (details.frameId !== 0 || !/^https?:/.test(details.url)) return;
    (async () => {
      const found = Shield.lookalike(Shield.hostOf(details.url));
      if (!found) return;
      const settings = await Shield.loadSettings();
      const site = Shield.siteOf(Shield.hostOf(details.url));
      if (!settings.security.lookalike || settings.security.allowedLookalikes.includes(site) || (await onceAllowed(site, "lookalike"))) return;
      const page = api.runtime.getURL("warn.html") + "?" + new URLSearchParams({ kind: "lookalike", url: details.url, brand: found.brand, real: found.real, reason: found.reason });
      await api.tabs.update(details.tabId, { url: page });
      await Shield.count("phishing", 1, details.tabId);
      await Shield.log({ kind: "phishing", site, tabId: details.tabId, text: `stopped before ${site}: it looks like ${found.brand} but is not`, detail: `${found.reason}; the real site is ${found.real}` });
    })().catch((error) => console.warn("shield: navigation guard", error));
  });
}

// Risky downloads pause until you have seen why they are risky.
//
// Chromium replays the whole download history through onCreated when the
// browser starts (seen in Chrome 142+): every old zip or installer in the list
// used to open its own "keep this download?" tab, twenty at a time. Only a
// download that is actually running, started in the last minute and never seen
// before gets a warning, and every warning shares one tab.
const DOWNLOAD_FRESH_MS = 60 * 1000;
async function freshDownload(item) {
  const stored = await api.storage.local.get("downloadsSeen");
  const seen = Array.isArray(stored.downloadsSeen) ? stored.downloadsSeen : [];
  if (!Shield.isFreshDownload(item, seen, Date.now(), DOWNLOAD_FRESH_MS)) return false;
  seen.push(item.id);
  await api.storage.local.set({ downloadsSeen: seen.slice(-500) });
  return true;
}
// One at a time: three downloads starting together used to race past the
// "is a warning tab open?" check and open three tabs.
let warningQueue = Promise.resolve();
function showDownloadWarning(id) {
  warningQueue = warningQueue.then(() => openDownloadWarning(id)).catch(() => {});
  return warningQueue;
}
async function openDownloadWarning(id) {
  const url = api.runtime.getURL("warn.html") + "?kind=download&id=" + id;
  // The tab is remembered by id: a tab still loading has no url yet, so a
  // url search misses it and a second download would open a second tab.
  const session = await api.storage.session.get("downloadWarnTab");
  const known = session.downloadWarnTab ? await api.tabs.get(session.downloadWarnTab).catch(() => null) : null;
  if (known) {
    // The tab is showing an earlier download; that one is decided first and
    // the page moves on to this one by itself.
    await api.tabs.update(known.id, { active: true }).catch(() => {});
    if (known.windowId !== undefined) await api.windows.update(known.windowId, { focused: true }).catch(() => {});
    return;
  }
  const tab = await api.tabs.create({ url });
  await api.storage.session.set({ downloadWarnTab: tab.id });
}
Shield._freshDownload = freshDownload;
if (api.downloads && api.downloads.onCreated) {
  api.downloads.onCreated.addListener((item) => {
    (async () => {
      const settings = await Shield.loadSettings();
      if (!settings.security.downloadWarn) return;
      const concern = Shield.downloadConcern(item, settings);
      if (!concern) return;
      if (!(await freshDownload(item))) return;
      // Examined whether or not it can still be held: small files finish first.
      const firstSeen = secSiteFirst.get(Shield.siteOf(Shield.hostOf(item.referrer || item.url)));
      Shield.sec.record("download.start", { url: item.url, data: { downloadId: item.id, name: concern.name, mime: item.mime || "", risky: true, reasons: concern.reasons, referrer: item.referrer || "", siteAgeMs: firstSeen ? Date.now() - firstSeen : 0 } }).catch(() => {});
      secScanDownload(item, concern, settings).then(async (scan) => {
        if (!scan) return;
        const again = await api.storage.session.get("downloads");
        const latest = again.downloads || {};
        if (latest[String(item.id)]) { latest[String(item.id)].scan = { type: scan.type, sha256: scan.sha256, findings: scan.findings || [], error: scan.error || null, knownMalware: Boolean(scan.knownMalware) }; await api.storage.session.set({ downloads: latest }); }
      }).catch(() => {});
      try {
        await api.downloads.pause(item.id);
      } catch {
        // Already finished: nothing to hold, so no tab; the log keeps the note.
        await Shield.log({ kind: "download", text: "risky download finished before it could be held: " + concern.name, detail: concern.reasons.join("; ") });
        return;
      }
      const entry = { id: item.id, name: concern.name, url: item.url, source: concern.source, reasons: concern.reasons, virusTotal: null, scan: null };

      const session = await api.storage.session.get("downloads");
      const downloads = session.downloads || {};
      downloads[String(item.id)] = entry;
      await api.storage.session.set({ downloads });
      await Shield.log({ kind: "download", text: "held a risky download: " + concern.name, detail: concern.reasons.join("; ") });
      await showDownloadWarning(item.id);
      if (settings.security.virusTotalKey && !settings.localOnly) {
        try {
          entry.virusTotal = await Shield.virusTotalUrl(item.url, settings.security.virusTotalKey);
        } catch (error) {
          entry.virusTotal = { error: String(error.message || error) };
        }
        const again = await api.storage.session.get("downloads");
        const latest = again.downloads || {};
        latest[String(item.id)] = entry;
        await api.storage.session.set({ downloads: latest });
      }
    })().catch((error) => console.warn("shield: download guard", error));
  });
}

// Warning tabs left over from the last session (the browser restores them,
// often lazily, after the worker has started) close as soon as they show up:
// session storage starts empty, so a download tab with no held download
// behind it can only be a leftover.
async function closeIfStaleWarning(tab) {
  const address = (tab && (tab.url || tab.pendingUrl)) || "";
  if (!address.startsWith(api.runtime.getURL("warn.html"))) return;
  const match = /[?&]kind=download&id=(\d+)/.exec(address);
  if (!match) return;
  const session = await api.storage.session.get("downloads");
  if ((session.downloads || {})[match[1]]) return;
  await api.tabs.remove(tab.id).catch(() => {});
}
async function closeStaleWarnings() {
  const open = await api.tabs.query({}).catch(() => []);
  for (const tab of open) await closeIfStaleWarning(tab);
}
api.runtime.onStartup.addListener(() => { closeStaleWarnings().catch(() => {}); });
api.tabs.onCreated.addListener((tab) => { closeIfStaleWarning(tab).catch(() => {}); });
api.tabs.onUpdated.addListener((tabId, change, tab) => { if (change.url || change.status === "loading") closeIfStaleWarning(tab).catch(() => {}); });
api.tabs.onRemoved.addListener((tabId) => {
  api.storage.session.get("downloadWarnTab").then((session) => {
    if (session.downloadWarnTab === tabId) return api.storage.session.remove("downloadWarnTab");
  }).catch(() => {});
});

// The handlers by name, for the shield's own pages and tests running inside the worker.
globalThis.handlersProxy = (type, message = {}) => handlers[type]({ ...message, type }, { url: api.runtime.getURL("background.js") });

function sameSiteAsSender(url, sender) {
  const senderSite = Shield.siteOf(Shield.hostOf(sender.url || ""));
  return Boolean(senderSite) && Shield.siteOf(Shield.hostOf(String(url || ""))) === senderSite;
}

// What a page's content script may say, and about what: its own tab, its own
// site, its own addresses. Nothing it sends can reach into another tab.
function boundToSender(message, sender) {
  const site = Shield.siteOf(Shield.hostOf(sender.url || ""));
  switch (message.type) {
    case "site.score":
      return sender.tab ? { ...message, tabId: sender.tab.id, url: sender.tab.url } : null;
    case "lookalike.allow":
      return message.site === site ? message : null;
    case "shop.price":
    case "shop.watch":
      return message.product && sameSiteAsSender(message.product.url, sender) ? message : null;
    case "shop.unwatch":
    case "shop.remind":
      return sameSiteAsSender(message.url, sender) ? message : null;
    case "shop.receipt":
      return message.receipt && sameSiteAsSender(message.receipt.url, sender) ? { ...message, receipt: { ...message.receipt, site } } : null;
    default:
      return message;
  }
}

// Capture questions this worker put to a tab, awaiting the person's answer.
const pendingCaptureAsks = new Map();
function captureAskKey(sender, kind) {
  return (sender.tab ? sender.tab.id : "none") + "|" + (sender.frameId ?? 0) + "|" + kind;
}

api.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Only this extension's own scripts speak here; nothing is exposed to
  // other extensions, so a message from one is refused before it is read.
  if (!sender || sender.id !== api.runtime.id) {
    sendResponse({ error: "not from here" });
    return false;
  }
  const handler = message && handlers[message.type];
  if (!handler) {
    sendResponse({ error: "unknown message" });
    return false;
  }
  // Content scripts of a page speak only for that page; the popup and options
  // pages carry the extension's own origin.
  const fromPage = !(sender.url && sender.url.startsWith(api.runtime.getURL("")));
  const pageAllowed = new Set(["guard.config", "site.score", "media.state", "lock.check", "shop.price", "shop.watch", "shop.unwatch", "shop.storeCheck", "shop.reddit", "shop.remind", "shop.receipt", "capture.ask", "capture.decide", "capture.shot", "capture.save", "light.state", "search.state", "search.hidden", "search.peek", "search.prices", "log.open", "safety.event", "lookalike.check", "lookalike.allow", "password.salt", "password.seen", "password.breach", "scam.close", "shop.compare", "shop.codes", "shop.pharma", "shop.seen", "shop.worked", "shop.saved", "shop.compared", "shop.quiet", "inspect.enabled", "inspect.arm.self", "spaces.config", "profile.config", "persona.config", "persona.consentCheck", "cookie.config", "dark.config", "downloader.found", "social.config", "sec.sense", "sec.brands", "yt.adPatterns", "yt.novelAdKey", "ai.cognition"]);
  if (fromPage && !pageAllowed.has(message.type)) {
    sendResponse({ error: "not from here" });
    return false;
  }
  if (fromPage) {
    message = boundToSender(message, sender);
    if (!message) {
      sendResponse({ error: "not about this page" });
      return false;
    }
  }
  handler(message, sender)
    .then((result) => sendResponse(result === undefined ? { ok: true } : result))
    .catch((error) => sendResponse({ error: String(error && error.message ? error.message : error) }));
  return true;
});

applyAll("wake").catch((error) => console.error("shield: wake", error));
