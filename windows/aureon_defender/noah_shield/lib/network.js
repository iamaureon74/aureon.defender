// Network shield: what the wifi (or any network) you join can collect.
//
// The story of a connection: the moment you join a network, its owner sits
// between you and every site. What they can read is what goes out in the
// clear: plain-http pages (every word and form), names you look up before you
// click (dns prefetch), your local address and the devices around you (webrtc,
// pages probing 192.168.x.x), and ids the browser attaches to requests. The
// encrypted part (https pages) they can only see the name of, not the content;
// hiding the name too needs secure dns and a vpn, which this file points to
// but cannot switch on by itself.
//
// So this file:
//   1. keeps pages on https, and when a site truly has no https version it
//      opens the plain one only for that site (or asks first on public wifi),
//      so access is never lost;
//   2. stops public sites from reaching into your local network (router,
//      printers, cameras), the trick used to fingerprint which wifi you are on;
//   3. hides your local address from webrtc without breaking calls;
//   4. turns off dns prefetch, so hovering a link tells the network nothing;
//   5. strips browser-attached ids from requests (best effort);
//   6. counts each of these so the popup can show what was stopped.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});

// Dynamic rule ids 7000..7019 belong here (7001 ids, 7002.. lan guard); session rules 7100..7899 are the
// per-site plain-http allowances, which end with the browser session.
const NET_RULE_BASE = 7000;
const HTTP_ALLOW_BASE = 7100;
const HTTP_ALLOW_MAX = 800;

// One short pattern per private range: a single combined pattern compiles past
// Chromium's 2 KB regex limit and is silently skipped (seen in Chrome 153).
const OCTET = "[0-9]{1,3}";
const PORT_END = "(:[0-9]{1,5})?(/|$)";
const PRIVATE_PATTERNS = [
  "localhost",
  `127\\.${OCTET}\\.${OCTET}\\.${OCTET}`,
  `10\\.${OCTET}\\.${OCTET}\\.${OCTET}`,
  `192\\.168\\.${OCTET}\\.${OCTET}`,
  `172\\.(1[6-9]|2[0-9]|3[01])\\.${OCTET}\\.${OCTET}`,
  `169\\.254\\.${OCTET}\\.${OCTET}`,
  "0\\.0\\.0\\.0",
  "\\[::1\\]",
  "\\[f[cd][0-9a-f]{2}:[0-9a-f:]*\\]",
].map((host) => `^[a-z]+://${host}${PORT_END}`);
const PRIVATE_HOST = `^[a-z]+://(localhost|127\\.${OCTET}\\.${OCTET}\\.${OCTET}|10\\.${OCTET}\\.${OCTET}\\.${OCTET}|192\\.168\\.${OCTET}\\.${OCTET}|172\\.(1[6-9]|2[0-9]|3[01])\\.${OCTET}\\.${OCTET}|169\\.254\\.${OCTET}\\.${OCTET}|0\\.0\\.0\\.0|\\[(::1|f[cd][0-9a-f]{2}:[0-9a-f:]{0,36})\\])${PORT_END}`;
Shield.PRIVATE_HOST_RE = new RegExp(PRIVATE_HOST, "i");
const SUB_TYPES = ["sub_frame", "script", "image", "stylesheet", "object", "xmlhttprequest", "ping", "websocket", "media", "font", "other"];

Shield.networkRules = function networkRules(settings) {
  const net = settings.network || {};
  if (!net.enabled) return [];
  const rules = [];
  if (net.lanGuard) {
    const trusted = (settings.privacy.trustedSites || []).filter(Boolean);
    PRIVATE_PATTERNS.forEach((regexFilter, index) => {
      const condition = { regexFilter, domainType: "thirdParty", resourceTypes: SUB_TYPES };
      if (trusted.length) condition.excludedInitiatorDomains = trusted;
      rules.push({ id: NET_RULE_BASE + 2 + index, priority: 5, action: { type: "block" }, condition });
    });
  }
  if (net.stripClientIds) {
    rules.push({
      id: NET_RULE_BASE + 1,
      priority: 5,
      action: { type: "modifyHeaders", requestHeaders: [{ header: "X-Client-Data", operation: "remove" }] },
      condition: { urlFilter: "*", resourceTypes: ["main_frame", ...SUB_TYPES] },
    });
  }
  return rules;
};

Shield.applyNetwork = async function applyNetwork(settings) {
  const net = settings.network || {};
  const dnr = Shield.api.declarativeNetRequest;
  if (dnr && dnr.updateDynamicRules) {
    try {
      const existing = (await dnr.getDynamicRules()).filter((rule) => rule.id >= NET_RULE_BASE && rule.id < NET_RULE_BASE + 20).map((rule) => rule.id);
      await dnr.updateDynamicRules({ removeRuleIds: existing, addRules: Shield.networkRules(settings) });
    } catch (error) {
      console.warn("shield: network rules", error);
    }
  }
  const privacy = Shield.api.privacy;
  // DNS prefetch tells the network's resolver about links you only hovered.
  if (net.enabled && privacy && privacy.network && privacy.network.networkPredictionEnabled) {
    await privacy.network.networkPredictionEnabled.set({ value: false }).catch(() => {});
  }
  // WebRTC: the vpn's own, stricter policy wins while it is guarding.
  const webrtc = privacy && privacy.network && privacy.network.webRTCIPHandlingPolicy;
  if (webrtc) {
    try {
      const current = await webrtc.get({});
      const tunnelGuarding = settings.tunnel.enabled && settings.tunnel.webRtcGuard;
      if (!tunnelGuarding) {
        if (net.enabled && net.publicWifi) await webrtc.set({ value: "disable_non_proxied_udp" });
        else if (net.enabled && net.hideLocalAddress) await webrtc.set({ value: "default_public_interface_only" });
        else if (current && current.levelOfControl === "controlled_by_this_extension") await webrtc.clear({});
      }
    } catch (error) {
      console.warn("shield: network webrtc", error);
    }
  }
};

// ---- https first, plain http only where a site has nothing else ------------------

const upgradedTabs = new Map(); // tabId -> { httpUrl, host, at }

Shield.noteUpgrade = function noteUpgrade(tabId, fromUrl, toUrl) {
  if (!/^http:\/\//i.test(fromUrl) || !/^https:\/\//i.test(toUrl)) return false;
  if (fromUrl.slice(7) !== toUrl.slice(8)) return false;
  upgradedTabs.set(tabId, { httpUrl: fromUrl, host: Shield.hostOf(fromUrl), at: Date.now() });
  return true;
};

const NO_HTTPS = /ERR_(SSL_|CERT_|CONNECTION_REFUSED|CONNECTION_RESET|CONNECTION_CLOSED|CONNECTION_TIMED_OUT|TIMED_OUT|EMPTY_RESPONSE|ADDRESS_UNREACHABLE|BAD_SSL_CLIENT_AUTH_CERT|HTTP2_PROTOCOL_ERROR)/;

// Called on a failed top-level load. Returns what was done, for the tests.
Shield.upgradeFailed = async function upgradeFailed(tabId, httpsUrl, error, settings) {
  const seen = upgradedTabs.get(tabId);
  if (!seen || Date.now() - seen.at > 30000 || Shield.hostOf(httpsUrl) !== seen.host) return null;
  if (!NO_HTTPS.test(String(error || ""))) return null;
  upgradedTabs.delete(tabId);
  const net = settings.network || {};
  if (net.publicWifi || !net.httpFallback) {
    const page = Shield.api.runtime.getURL("warn.html") + "?" + new URLSearchParams({ kind: "http", url: seen.httpUrl });
    await Shield.api.tabs.update(tabId, { url: page });
    return "asked";
  }
  await Shield.allowHttp(seen.host);
  await Shield.api.tabs.update(tabId, { url: seen.httpUrl });
  await Shield.count("httpFallback", 1);
  await Shield.log({ kind: "network", site: Shield.siteOf(seen.host), tabId, text: `${seen.host} has no secure version, so it opened over plain http`, detail: "anyone on this network can read this page; do not type passwords or card numbers here" });
  return "opened";
};

Shield.allowHttp = async function allowHttp(host) {
  const dnr = Shield.api.declarativeNetRequest;
  if (!dnr || !dnr.updateSessionRules || !host) return;
  const rules = await dnr.getSessionRules();
  const mine = rules.filter((rule) => rule.id >= HTTP_ALLOW_BASE && rule.id < HTTP_ALLOW_BASE + HTTP_ALLOW_MAX);
  if (mine.some((rule) => (rule.condition.requestDomains || []).includes(host))) return;
  const used = new Set(mine.map((rule) => rule.id));
  let id = HTTP_ALLOW_BASE;
  while (used.has(id) && id < HTTP_ALLOW_BASE + HTTP_ALLOW_MAX) id++;
  const removeRuleIds = [];
  if (id >= HTTP_ALLOW_BASE + HTTP_ALLOW_MAX) { id = mine[0].id; removeRuleIds.push(id); }
  await dnr.updateSessionRules({
    removeRuleIds,
    addRules: [{ id, priority: 10, action: { type: "allow" }, condition: { requestDomains: [host], resourceTypes: ["main_frame", ...SUB_TYPES] } }],
  });
};

// ---- what the popup shows ---------------------------------------------------------------

Shield.networkStatus = async function networkStatus(settings) {
  const net = settings.network || {};
  const summary = Shield.statsSummary ? await Shield.statsSummary() : { today: {}, month: {} };
  const today = summary.today || {};
  const vpn = Shield.tunnelStatus ? await Shield.tunnelStatus() : { state: "off" };
  const on = Boolean(net.enabled);
  const items = [
    { id: "https", on: on && settings.security.httpsUpgrade !== false, title: "pages kept on https", plain: "the network sees only the site's name, not what you read or type", count: today.upgrades || 0 },
    { id: "lan", on: on && net.lanGuard, title: "local network hidden from sites", plain: "sites cannot scan your router, printer or cameras to tell which wifi you are on", count: today.lan || 0 },
    { id: "webrtc", on: on && (net.hideLocalAddress || net.publicWifi), title: "local address hidden", plain: net.publicWifi ? "calls go through the vpn or not at all" : "calls still work; your device's address on this wifi stays private" },
    { id: "prefetch", on, title: "no lookups for links you only hover", plain: "the network's dns does not learn about pages you never opened" },
    { id: "ids", on: on && net.stripClientIds, title: "browser ids removed from requests", plain: "best effort: some browsers add them after extensions can reach them" },
    { id: "trackers", on: settings.privacy.trackers, title: "trackers and data grabs blocked", plain: "ads, analytics and fingerprinting scripts never load", count: today.trackers || 0 },
    { id: "vpn", on: vpn.state === "up", title: "vpn (hides which sites you visit)", plain: vpn.state === "up" ? "the wifi sees only encrypted traffic to the vpn" : "off: the wifi can still see the names of sites you visit" },
  ];
  return { enabled: on, publicWifi: Boolean(net.publicWifi), items, httpFallbacks: today.httpFallback || 0 };
};

// Where the browser's own secure dns switch lives: an extension cannot flip it.
Shield.secureDnsPage = function secureDnsPage() {
  const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
  if (/Firefox\//.test(ua)) return null;
  if (/Edg\//.test(ua)) return "edge://settings/privacy";
  if (/OPR\//.test(ua)) return "opera://settings/security";
  if (/Brave/.test(ua)) return "brave://settings/security";
  return "chrome://settings/security";
};
})();
