// The security center: sensors → rules → cases, graph and containment.
//
// This file connects the pieces and owns the parts that live over time:
// the extension inventory and its history (capability 3), the identity
// watch list (4), the removal tracker (5), shared indicators between your
// devices (11), and the notices.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

let engine = null;
let wired = false;
const noticeSent = new Map();

sec.start = function start() {
  if (wired) return;
  wired = true;
  engine = sec.createEngine();
  sec.onEvent(async (event) => {
    const settings = await Shield.loadSettings();
    if (!settings.secCenter || !settings.secCenter.enabled) return;
    await sec.graphAdd(event).catch(() => {});
    // Intelligence check for what the browser contacted.
    if ((event.kind === "request" || event.kind === "nav.commit") && event.host) {
      const hits = await sec.lookup(event.kind === "nav.commit" ? event.url : event.url, event.host);
      for (const hit of hits) {
        await sec.record("intel.hit", { tab: event.tab, url: event.url, host: event.host, ip: event.ip, source: hit.source, data: { category: hit.category, source: hit.source, confirmed: hit.confirmed, matched: hit.type, ref: hit.ref || "", from: event.id } });
      }
      if (event.ip) {
        const ipHit = await sec.lookupIp(event.ip);
        if (ipHit) await sec.record("intel.hit", { tab: event.tab, host: event.host, ip: event.ip, source: ipHit.source, data: { category: ipHit.category, source: ipHit.source, confirmed: ipHit.confirmed, matched: "ip", from: event.id } });
      }
    }
    for (const detection of engine.process(event)) {
      const item = await sec.addDetection(detection);
      const rule = detection.rule;
      // Automatic containment: only rules marked auto, only confirmed evidence.
      if (rule.auto && settings.secCenter.autoContain) {
        for (let index = 0; index < item.actions.length; index++) {
          const action = item.actions[index];
          if (action.state === "suggested" && action.auto && action.action !== "disable-extension") await sec.contain(item.id, index, { auto: true });
        }
      }
      if (!detection.merged && sec.SEVERITY[rule.severity] >= sec.SEVERITY[settings.secCenter.notifyLevel || "high"]) {
        const key = item.id + rule.id;
        if (!noticeSent.has(key) || Date.now() - noticeSent.get(key) > 10 * 60000) {
          noticeSent.set(key, Date.now());
          if (Shield.notifyUser) Shield.notifyUser("sec-" + item.id, `${rule.severity}: ${rule.title}`, `${item.subject.replace(/^\w+:/, "")} · open the security center for the evidence`).catch(() => {});
        }
      }
      await Shield.log({ kind: "security", site: event.site, tabId: event.tab, text: `${rule.severity}: ${rule.title}`, detail: `${rule.id} · att&ck ${rule.attack} · ${sec.describe(detection.evidence[detection.evidence.length - 1])}` }).catch(() => {});
    }
  });
};

// ---- feeds ---------------------------------------------------------------------------------

sec.refreshFeeds = async function refreshFeeds(settings) {
  const cfg = settings.secCenter || {};
  const results = {};
  if (settings.localOnly) return { skipped: "send nothing anywhere is on" };
  for (const id of Object.keys(sec.FEEDS)) {
    if (cfg.feeds && cfg.feeds[id]) results[id] = await sec.refreshFeed(id, { abuseKey: cfg.abuseKey, blocklistUrl: cfg.blocklistUrl, blocklistUser: cfg.blocklistUser, blocklistPass: cfg.blocklistPass });
  }
  const hosts = await sec.confirmedHosts();
  results.blockRules = await sec.applyFeedBlocks(hosts, Boolean(cfg.feedBlock && cfg.enabled)).catch((error) => ({ error: String(error) }));
  return results;
};

// ---- capability 3: extensions, their permissions and how they change -----------------------

const POWERFUL = new Set(["<all_urls>", "*://*/*", "http://*/*", "https://*/*", "cookies", "debugger", "webRequest", "webRequestBlocking", "declarativeNetRequest", "nativeMessaging", "proxy", "management", "history", "desktopCapture", "tabCapture", "clipboardRead", "scripting"]);

function permissionsOf(extension) {
  return [...(extension.permissions || []), ...(extension.hostPermissions || [])].sort();
}

sec.extensionSnapshot = async function extensionSnapshot(recordChanges = true) {
  const api = Shield.api;
  if (!api.management || !api.management.getAll) return { error: "this browser does not list extensions" };
  const list = await api.management.getAll();
  const stored = await api.storage.local.get("secExtensions");
  const previous = stored.secExtensions || {};
  const now = Date.now();
  const next = {};
  const self = api.runtime.id;
  for (const extension of list) {
    if (extension.type !== "extension") continue;
    const perms = permissionsOf(extension);
    const before = previous[extension.id];
    const history = before ? before.history.slice(-20) : [];
    if (!before) {
      history.push({ t: now, version: extension.version, change: "first seen", added: perms });
      if (recordChanges && Object.keys(previous).length) await sec.record("ext.install", { data: { extensionId: extension.id, name: extension.name, version: extension.version, installType: extension.installType, self: extension.id === self, permissions: perms } });
    } else {
      const added = perms.filter((p) => !before.perms.includes(p));
      const removed = before.perms.filter((p) => !perms.includes(p));
      if (added.length || removed.length || before.version !== extension.version) {
        history.push({ t: now, version: extension.version, change: before.version !== extension.version ? `updated ${before.version} → ${extension.version}` : "permissions changed", added, removed });
        if (recordChanges && added.length) await sec.record("ext.change", { data: { extensionId: extension.id, name: extension.name, version: extension.version, added, removed, addedCount: added.length, addedPowerful: added.some((p) => POWERFUL.has(p) || /^\*:\/\/\*|^https?:\/\/\*\//.test(p)), self: extension.id === self } });
      }
    }
    next[extension.id] = { id: extension.id, name: extension.name, version: extension.version, enabled: extension.enabled, installType: extension.installType, homepage: extension.homepageUrl || "", updateUrl: extension.updateUrl || "", perms, history, self: extension.id === self, mayDisable: extension.mayDisable };
  }
  for (const [id, before] of Object.entries(previous)) {
    if (!next[id] && recordChanges) await sec.record("ext.remove", { data: { extensionId: id, name: before.name } });
  }
  await api.storage.local.set({ secExtensions: next });
  const audit = Shield.auditExtensions ? await Shield.auditExtensions().catch(() => []) : [];
  const risk = Object.fromEntries(((audit && audit.extensions) || []).map((item) => [item.id, { level: item.level, score: item.score, reasons: item.reasons }]));
  return Object.values(next).map((item) => Object.assign(item, { risk: risk[item.id] || null, store: /clients2\.google\.com|edge\.microsoft\.com|addons\.mozilla/.test(item.updateUrl) ? "store" : item.installType }));
};

// ---- capability 4: identity watch -----------------------------------------------------------

sec.checkIdentities = async function checkIdentities(settings) {
  const cfg = settings.secCenter || {};
  const key = settings.security && settings.security.hibpKey;
  if (!key || settings.localOnly) return { skipped: key ? "send nothing anywhere is on" : "needs a have i been pwned key in settings → security" };
  const stored = await Shield.api.storage.local.get("secIdentity");
  const state = stored.secIdentity || {};
  const results = [];
  for (const email of (cfg.watch || []).slice(0, 10)) {
    try {
      const breaches = await Shield.breachedEmail(email, key);
      const before = state[email] ? state[email].breaches : [];
      const fresh = breaches.filter((name) => !before.includes(name));
      state[email] = { breaches, checked: Date.now() };
      if (fresh.length) await sec.record("identity.exposed", { data: { label: email, breaches: breaches.length, fresh, source: "have i been pwned" } });
      results.push({ email, breaches, fresh });
      await new Promise((resolve) => setTimeout(resolve, 6500)); // hibp rate limit
    } catch (error) {
      results.push({ email, error: String(error.message || error) });
    }
  }
  await Shield.api.storage.local.set({ secIdentity: state });
  return results;
};

// ---- capability 5: removal requests, tracked to the end -------------------------------------

sec.removals = async function removals(change) {
  const stored = await Shield.api.storage.local.get("secRemovals");
  let list = Array.isArray(stored.secRemovals) ? stored.secRemovals : [];
  if (change && change.add) list.push({ id: Date.now().toString(36), broker: String(change.add.broker || "").slice(0, 120), url: String(change.add.url || "").slice(0, 300), categories: String(change.add.categories || "").slice(0, 200), sent: null, status: "found", history: [{ t: Date.now(), status: "found" }] });
  if (change && change.update) {
    const item = list.find((entry) => entry.id === change.update.id);
    const allowed = ["found", "requested", "answered", "removed", "refused", "relisted"];
    if (item && allowed.includes(change.update.status)) {
      item.status = change.update.status;
      if (item.status === "requested") item.sent = Date.now();
      item.history.push({ t: Date.now(), status: item.status });
    }
  }
  if (change && change.remove) list = list.filter((entry) => entry.id !== change.remove);
  // a request with no answer after 45 days is overdue: most privacy laws give 30–45
  for (const entry of list) entry.overdue = entry.status === "requested" && entry.sent && Date.now() - entry.sent > 45 * 86400000;
  await Shield.api.storage.local.set({ secRemovals: list });
  return list;
};

// ---- capability 11: your own indicators and receipts, shared between devices ----------------
// End-to-end encrypted with your sync passphrase (aes-gcm, pbkdf2 250k) and
// carried by the browser's own sync. Each device writes a receipt saying
// which indicator set it applied, so the devices page shows real state.

async function key(passphrase, salt) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations: 250000, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}
const b64 = (bytes) => btoa(String.fromCharCode(...bytes));
const unb64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

sec.syncIndicators = async function syncIndicators() {
  const api = Shield.api;
  const stored = await api.storage.local.get(["syncPassphrase"]);
  if (!stored.syncPassphrase || !api.storage.sync) return { skipped: "turn on encrypted sync in settings first" };
  const device = await Shield.installId();
  const summary = await sec.intelSummary();
  const mine = summary.mine.map(({ type, value, category, added }) => ({ type, value, category, added }));
  // pull what others shared
  const remote = await api.storage.sync.get(["secShare", "secReceipts"]);
  let merged = mine;
  if (remote.secShare) {
    try {
      const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(remote.secShare.iv) }, await key(stored.syncPassphrase, unb64(remote.secShare.salt)), unb64(remote.secShare.data));
      const theirs = JSON.parse(new TextDecoder().decode(plain));
      for (const item of theirs.indicators || []) if (!mine.some((m) => m.type === item.type && m.value === item.value)) { await sec.addIndicator(item.type, item.value, { category: item.category, source: "you", added: item.added }); merged.push(item); }
    } catch {
      return { error: "another device used a different sync passphrase" };
    }
  }
  const salt = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12));
  const data = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await key(stored.syncPassphrase, salt), new TextEncoder().encode(JSON.stringify({ indicators: merged.slice(0, 300) }))));
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(merged.map((m) => m.type + m.value).sort())))), (b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
  const receipts = remote.secReceipts || {};
  const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
  receipts[device] = { at: Date.now(), applied: digest, count: merged.length, browser: /Firefox\//.test(ua) ? "firefox" : /Edg\//.test(ua) ? "edge" : "chromium", mobile: /Android|Mobile/.test(ua) };
  await api.storage.sync.set({ secShare: { salt: b64(salt), iv: b64(iv), data: b64(data) }, secReceipts: receipts });
  return { ok: true, count: merged.length, applied: digest, devices: Object.entries(receipts).map(([id, r]) => Object.assign({ id, self: id === device, inStep: r.applied === digest }, r)) };
};

// ---- capability 7: what exists outside the browser -------------------------------------------
sec.deviceStatus = async function deviceStatus() {
  const info = Shield.hostInfo ? await Shield.hostInfo().catch((error) => ({ error: String(error) })) : { error: "no helper support" };
  return {
    helper: info && info.present ? { installed: true, version: info.version || null, platform: info.platform || "", features: [info.brightness && "screen brightness", info.tor && "tor"].filter(Boolean) } : { installed: false, reason: info && info.error },
    deviceWide: { available: false, reason: "device-wide firewall and dns need the native companion, which is not built yet" },
  };
};
})();
