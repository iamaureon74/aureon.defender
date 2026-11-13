// Threat intelligence: lists of known-bad hosts, addresses and files.
//
// Every indicator says where it came from and whether it is confirmed:
//   confirmed   - the exact address or host is listed by a named source
//   unverified  - only related (the host of a listed phishing address,
//                 which is often a hacked site or a shared host)
// Feeds are downloaded whole and matched on this device: no address you
// visit is sent to anyone to be checked.
//
// Sources (all optional; "send nothing anywhere" turns every one off):
//   urlhaus  (abuse.ch)   hosts spreading malware; free abuse.ch key may be
//                          required for downloads, sent as Auth-Key
//   openphish community   phishing addresses; free for non-commercial use,
//                          so it is off until you turn it on
//   your own list         hosts you add by hand
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

sec.FEEDS = {
  urlhaus: { name: "urlhaus (abuse.ch)", url: "https://urlhaus.abuse.ch/downloads/hostfile/", category: "malware", kind: "hostfile", confirmed: true, license: "cc0, abuse.ch fair use" },
  openphish: { name: "openphish community", url: "https://openphish.com/feed.txt", category: "phishing", kind: "urls", confirmed: true, license: "non-commercial use only" },
  // Mercenary spyware and stalkerware infrastructure (Pegasus, Predator,
  // Candiru, Cellebrite, stalkerware apps …) as published for the Mobile
  // Verification Toolkit by Amnesty International, Citizen Lab and others.
  // The index lists STIX 2 bundles; each is downloaded whole.
  mvt: { name: "mvt spyware indicators", url: "https://raw.githubusercontent.com/mvt-project/mvt-indicators/main/indicators.yaml", category: "spyware", kind: "stix-index", confirmed: true, license: "per source, see github.com/mvt-project/mvt-indicators" },
  // Your own list of bad addresses at a URL you choose: one ip, host or
  // address per line. A CrowdSec blocklist integration ("raw ip list" format)
  // works as is, with its username and password.
  blocklist: { name: "your blocklist (e.g. CrowdSec)", url: "", category: "malicious", kind: "list", confirmed: true, license: "yours" },
};

// Big shared platforms appear in feeds because one file or page on them was
// bad. They are never blocked as a whole host; only the exact address is.
sec.SHARED_HOSTS = new Set([
  "github.com", "raw.githubusercontent.com", "gist.githubusercontent.com", "objects.githubusercontent.com", "gitlab.com", "bitbucket.org",
  "drive.google.com", "docs.google.com", "sites.google.com", "storage.googleapis.com", "firebasestorage.googleapis.com", "forms.gle",
  "dropbox.com", "dl.dropboxusercontent.com", "onedrive.live.com", "1drv.ms", "sharepoint.com", "cdn.discordapp.com", "discord.com",
  "pastebin.com", "mega.nz", "mediafire.com", "web.app", "firebaseapp.com", "pages.dev", "workers.dev", "netlify.app", "vercel.app",
  "glitch.me", "weebly.com", "wixsite.com", "blogspot.com", "wordpress.com", "s3.amazonaws.com", "amazonaws.com", "cloudfront.net",
  "azurewebsites.net", "blob.core.windows.net", "ipfs.io", "telegra.ph", "t.me", "bit.ly", "tinyurl.com",
]);

let store = null; // { hosts: {host: ind}, urls: {url: ind}, ips: {ip: ind}, hashes: {sha256: ind}, feeds: {id: status} }
let saveTimer = null;

function empty() { return { hosts: {}, urls: {}, ips: {}, hashes: {}, feeds: {} }; }

async function load() {
  if (store) return store;
  store = empty();
  try {
    const stored = Shield.api && Shield.api.storage ? await Shield.api.storage.local.get("secIntel") : {};
    if (stored.secIntel && typeof stored.secIntel === "object") store = Object.assign(empty(), stored.secIntel);
  } catch {}
  return store;
}
sec.loadIntel = load;

function save() {
  if (saveTimer || !Shield.api || !Shield.api.storage) return;
  saveTimer = setTimeout(() => { saveTimer = null; Shield.api.storage.local.set({ secIntel: store }).catch(() => {}); }, 1500);
}

function shared(host) {
  if (sec.SHARED_HOSTS.has(host)) return true;
  for (const item of sec.SHARED_HOSTS) if (host.endsWith("." + item)) return true;
  return false;
}

sec.addIndicator = async function addIndicator(type, value, info) {
  await load();
  value = String(value || "").trim().toLowerCase();
  if (!value) return null;
  const table = { host: "hosts", url: "urls", ip: "ips", hash: "hashes" }[type];
  if (!table) return null;
  const indicator = { value, type, category: info.category || "suspicious", source: info.source || "you", confirmed: info.confirmed !== false, added: info.added || Date.now(), ref: info.ref || "" };
  store[table][value] = indicator;
  save();
  return indicator;
};

sec.removeIndicator = async function removeIndicator(type, value) {
  await load();
  const table = { host: "hosts", url: "urls", ip: "ips", hash: "hashes" }[type];
  if (table) delete store[table][String(value).toLowerCase()];
  save();
};

// Parse a feed body into indicators. Kept separate so the tests can feed it text.
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
const HOST = /^[a-z0-9.-]+\.[a-z0-9-]{2,}$/;

sec.parseFeed = function parseFeed(id, text) {
  const feed = sec.FEEDS[id];
  const out = { hosts: {}, urls: {}, ips: {}, hashes: {} };
  const now = Date.now();
  if (feed.kind === "stix") return sec.parseStix(id, text, "");
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (feed.kind === "list") {
      const value = line.split(/[\s,;]+/)[0].toLowerCase().replace(/\/32$/, "");
      if (IPV4.test(value) || (value.includes(":") && /^[0-9a-f:]+$/.test(value))) out.ips[value] = { value, type: "ip", category: feed.category, source: id, confirmed: true, added: now };
      else if (/^https?:\/\//.test(value)) { try { const url = new URL(value); out.urls[url.href] = { value: url.href, type: "url", category: feed.category, source: id, confirmed: true, added: now }; } catch {} }
      else if (HOST.test(value)) out.hosts[value] = { value, type: "host", category: feed.category, source: id, confirmed: !shared(value), added: now };
      continue;
    }
    if (feed.kind === "hostfile") {
      const parts = line.split(/\s+/);
      const host = (parts.length > 1 ? parts[1] : parts[0]).toLowerCase();
      if (!/^[a-z0-9.-]+\.[a-z0-9-]{2,}$/.test(host) && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) continue;
      if (host === "localhost") continue;
      out.hosts[host] = { value: host, type: "host", category: feed.category, source: id, confirmed: !shared(host), added: now };
    } else {
      let url;
      try { url = new URL(line); } catch { continue; }
      const value = url.href.toLowerCase();
      out.urls[value] = { value, type: "url", category: feed.category, source: id, confirmed: true, added: now };
      const host = url.hostname.toLowerCase();
      if (!out.hosts[host]) out.hosts[host] = { value: host, type: "host", category: feed.category, source: id, confirmed: false, added: now, ref: "host of a listed address" };
    }
  }
  return out;
};

// STIX 2.1 bundle → indicators. Only plain equality patterns are read:
// [domain-name:value = 'x'], [url:value = …], [ipv4-addr:value = …],
// [file:hashes.sha256 = …] (any of them joined by OR). Everything else in a
// pattern (app ids, process names, configuration profiles) does not apply to
// a browser and is left out.
sec.parseStix = function parseStix(id, text, collection) {
  const feed = sec.FEEDS[id];
  const out = { hosts: {}, urls: {}, ips: {}, hashes: {} };
  const now = Date.now();
  let bundle;
  try { bundle = JSON.parse(text); } catch { return out; }
  const objects = Array.isArray(bundle.objects) ? bundle.objects : [];
  const malware = objects.find((o) => o.type === "malware");
  const ref = collection || (malware && malware.name) || "";
  const term = /(domain-name|url|ipv4-addr|ipv6-addr|file):(value|hashes\.'?(?:sha-?256|SHA-256)'?)\s*=\s*'((?:[^'\\]|\\.)+)'/gi;
  for (const object of objects) {
    if (object.type !== "indicator" || typeof object.pattern !== "string") continue;
    term.lastIndex = 0;
    let m;
    while ((m = term.exec(object.pattern))) {
      const kind = m[1].toLowerCase();
      const value = m[3].replace(/\\'/g, "'").trim().toLowerCase();
      const base = { category: feed.category, source: id, confirmed: true, added: now, ref };
      if (kind === "domain-name" && HOST.test(value)) out.hosts[value] = Object.assign({ value, type: "host" }, base, { confirmed: !shared(value) });
      else if (kind === "url") { try { const url = new URL(/^[a-z]+:\/\//.test(value) ? value : "http://" + value); out.urls[url.href] = Object.assign({ value: url.href, type: "url" }, base); } catch {} }
      else if (kind === "ipv4-addr" || kind === "ipv6-addr") out.ips[value.replace(/\/32$/, "")] = Object.assign({ value: value.replace(/\/32$/, ""), type: "ip" }, base);
      else if (kind === "file" && /^[a-f0-9]{64}$/.test(value)) out.hashes[value] = Object.assign({ value, type: "hash" }, base);
    }
  }
  return out;
};

// The mvt index (indicators.yaml) names github files; read owner, repo,
// branch and path of each without a yaml parser.
sec.parseStixIndex = function parseStixIndex(text) {
  const list = [];
  for (const block of String(text || "").split(/\n\s*-\s*\n/)) {
    const field = (name) => { const m = new RegExp("^\\s*" + name + ":\\s*(.+?)\\s*$", "m").exec(block); return m ? m[1].replace(/^["']|["']$/g, "") : ""; };
    const name = field("name"), owner = field("owner"), repo = field("repo"), branch = field("branch") || "main", path = field("path");
    if (owner && repo && path && /\.stix2?$/i.test(path)) list.push({ name, url: `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${path}` });
    else { const direct = /^\s*download_url:\s*(\S+)/m.exec(block); if (direct) list.push({ name, url: direct[1] }); }
  }
  return list;
};

async function fetchText(url, headers = {}) {
  const response = await fetch(url, { headers, credentials: "omit", cache: "no-store" });
  if (!response.ok) throw new Error("the feed answered " + response.status + (response.status === 401 || response.status === 403 ? " (it may need a key or a password)" : ""));
  return response.text();
}

sec.refreshFeed = async function refreshFeed(id, options = {}) {
  await load();
  const feed = sec.FEEDS[id];
  if (!feed) return { error: "unknown feed" };
  const status = { at: Date.now(), ok: false, count: 0 };
  try {
    const headers = {};
    if (id === "urlhaus" && options.abuseKey) headers["Auth-Key"] = options.abuseKey;
    let parsed;
    if (feed.kind === "stix-index") {
      const index = sec.parseStixIndex(await fetchText(feed.url));
      if (!index.length) throw new Error("the index listed no indicator files");
      parsed = { hosts: {}, urls: {}, ips: {}, hashes: {} };
      const failed = [];
      for (const entry of index.slice(0, 60)) {
        try {
          const one = sec.parseStix(id, await fetchText(entry.url), entry.name);
          for (const table of Object.keys(parsed)) Object.assign(parsed[table], one[table]);
        } catch { failed.push(entry.name); }
      }
      status.collections = index.length - failed.length;
      if (failed.length) status.failed = failed;
    } else if (feed.kind === "list") {
      const url = String(options.blocklistUrl || "").trim();
      if (!/^https:\/\//i.test(url)) throw new Error("set an https address for your blocklist first");
      if (options.blocklistUser || options.blocklistPass) headers.Authorization = "Basic " + btoa(unescape(encodeURIComponent(options.blocklistUser + ":" + options.blocklistPass)));
      parsed = sec.parseFeed(id, await fetchText(url, headers));
    } else {
      parsed = sec.parseFeed(id, await fetchText(feed.url, headers));
    }
    for (const table of ["hosts", "urls", "ips", "hashes"]) {
      for (const [key, value] of Object.entries(store[table])) if (value.source === id) delete store[table][key];
      Object.assign(store[table], parsed[table] || {});
    }
    status.ok = true;
    status.count = Object.keys(parsed.urls).length + Object.values(parsed.hosts).filter((item) => item.confirmed).length + Object.keys(parsed.ips || {}).length + Object.keys(parsed.hashes || {}).length;
  } catch (error) {
    status.error = String(error.message || error);
  }
  store.feeds[id] = status;
  save();
  return status;
};

// What an address matches, strongest first. Parent domains count: a listed
// evil.example also covers cdn.evil.example.
sec.lookup = async function lookup(url, host) {
  await load();
  host = String(host || Shield.hostOf(url) || "").toLowerCase();
  const hits = [];
  if (url) {
    const exact = store.urls[String(url).toLowerCase()];
    if (exact) hits.push(exact);
  }
  const labels = host.split(".");
  for (let index = 0; index < labels.length - 1; index++) {
    const candidate = labels.slice(index).join(".");
    if (store.hosts[candidate]) { hits.push(store.hosts[candidate]); break; }
  }
  if (store.ips[host]) hits.push(store.ips[host]);
  return hits;
};

sec.lookupIp = async function lookupIp(ip) { await load(); return store.ips[ip] || null; };
sec.lookupHash = async function lookupHash(hash) { await load(); return store.hashes[String(hash).toLowerCase()] || null; };

sec.confirmedHosts = async function confirmedHosts() {
  await load();
  return Object.values(store.hosts).filter((item) => item.confirmed).map((item) => item.value);
};

sec.intelSummary = async function intelSummary() {
  await load();
  const count = (table) => Object.keys(store[table]).length;
  const mine = Object.values(store.hosts).concat(Object.values(store.ips), Object.values(store.hashes)).filter((item) => item.source === "you");
  return { hosts: count("hosts"), urls: count("urls"), ips: count("ips"), hashes: count("hashes"), feeds: store.feeds, mine };
};

// RDAP (rfc 9224): the official, structured successor to whois. One domain is
// sent to the registry that runs its ending. Only asked when you press a button.
sec.domainAge = async function domainAge(host) {
  const site = Shield.siteOf(String(host || "").toLowerCase());
  if (!site) return { error: "no domain" };
  try {
    const response = await fetch("https://rdap.org/domain/" + encodeURIComponent(site), { credentials: "omit", headers: { accept: "application/rdap+json" } });
    if (!response.ok) return { site, error: "the registry answered " + response.status };
    const data = await response.json();
    const registered = (data.events || []).find((event) => event.eventAction === "registration");
    const date = registered ? Date.parse(registered.eventDate) : NaN;
    return { site, registered: Number.isFinite(date) ? new Date(date).toISOString().slice(0, 10) : null, ageDays: Number.isFinite(date) ? Math.floor((Date.now() - date) / 86400000) : null, registrar: ((data.entities || []).find((entity) => (entity.roles || []).includes("registrar")) || {}).handle || null, source: "rdap" };
  } catch (error) {
    return { site, error: String(error.message || error) };
  }
};

sec._resetIntelForTests = function resetIntelForTests() { store = empty(); };
})();
