// The relationship graph: sites, hosts, addresses, files and indicators, and
// how they connect, built only from events and intelligence.
//
// Shaped after stix 2.1: nodes are observables (domain-name, ipv4-addr, url,
// file) or intelligence (indicator); edges are relationships with a type,
// a source and a "verified" flag. Verified edges were observed by the
// browser or stated by a named feed; unverified ones are associations the
// page sensor or a host-of-a-listed-url rule suggested. The page draws the
// two differently and never merges them.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const MAX_NODES = 3000;
let graph = null;
let saveTimer = null;

async function load() {
  if (graph) return graph;
  graph = { nodes: {}, edges: {} };
  try {
    const stored = Shield.api && Shield.api.storage ? await Shield.api.storage.local.get("secGraph") : {};
    if (stored.secGraph && stored.secGraph.nodes) graph = stored.secGraph;
  } catch {}
  return graph;
}
sec.loadGraph = load;

function save() {
  if (saveTimer || !Shield.api || !Shield.api.storage) return;
  saveTimer = setTimeout(() => { saveTimer = null; Shield.api.storage.local.set({ secGraph: graph }).catch(() => {}); }, 3000);
}

function node(type, value, t, extra) {
  const id = type + ":" + value;
  const existing = graph.nodes[id];
  if (existing) { existing.last = t; existing.count++; if (extra) Object.assign(existing, extra); return id; }
  graph.nodes[id] = Object.assign({ id, type, label: value, first: t, last: t, count: 1 }, extra || {});
  return id;
}

function edge(from, to, type, t, source, verified) {
  if (from === to) return;
  const key = from + ">" + type + ">" + to;
  const existing = graph.edges[key];
  if (existing) { existing.last = t; existing.count++; if (verified) existing.verified = true; return; }
  graph.edges[key] = { from, to, type, first: t, last: t, count: 1, source, verified: Boolean(verified) };
}

function trim() {
  const ids = Object.keys(graph.nodes);
  if (ids.length <= MAX_NODES) return;
  const drop = new Set(ids.sort((a, b) => graph.nodes[a].last - graph.nodes[b].last).slice(0, ids.length - MAX_NODES).filter((id) => !graph.nodes[id].alert));
  for (const id of drop) delete graph.nodes[id];
  for (const [key, value] of Object.entries(graph.edges)) if (drop.has(value.from) || drop.has(value.to)) delete graph.edges[key];
}

// One event in, the nodes and edges it proves out.
sec.graphAdd = async function graphAdd(event) {
  await load();
  const t = event.t;
  const site = event.site ? node("site", event.site, t) : null;
  switch (event.kind) {
    case "request": {
      if (!event.host || !event.data || !event.data.thirdParty || !event.data.pageSite) break;
      const page = node("site", event.data.pageSite, t);
      const host = node("host", event.host, t, { owner: event.data.owner || undefined });
      edge(page, host, "loads-from", t, "browser", true);
      if (event.ip) edge(host, node("ip", event.ip, t), "resolves-to", t, "browser", true);
      break;
    }
    case "nav.commit":
      if (event.host && event.ip) edge(node("host", event.host, t), node("ip", event.ip, t), "resolves-to", t, "browser", true);
      if (site && event.host) edge(site, node("host", event.host, t), "served-by", t, "browser", true);
      break;
    case "nav.redirect":
      if (event.data && event.data.from && event.data.to) edge(node("host", Shield.hostOf(event.data.from), t), node("host", Shield.hostOf(event.data.to), t), "redirects-to", t, "browser", true);
      break;
    case "form.submit":
      if (site && event.data && event.data.actionHost) edge(site, node("host", event.data.actionHost, t), event.data.hasPassword ? "sends-password-to" : "submits-to", t, "page sensor", true);
      break;
    case "download.start":
      if (event.data && event.data.name) edge(node("host", event.host, t), node("file", event.data.sha256 || event.data.name, t, { name: event.data.name }), "delivers", t, "browser", true);
      break;
    case "file.scan":
      if (event.data && event.data.sha256 && event.data.name) node("file", event.data.sha256, t, { name: event.data.name, alert: event.data.knownMalware || event.data.disguised || undefined });
      break;
    case "intel.hit": {
      const target = event.data.matched === "url" ? node("url", event.url, t) : node("host", event.host, t);
      const indicator = node("indicator", event.data.source + ":" + event.data.category, t, { alert: true });
      graph.nodes[target].alert = true;
      edge(target, indicator, "indicated-by", t, event.data.source, event.data.confirmed);
      if (event.data.matched === "url") edge(node("host", event.host, t), target, "hosts", t, "browser", true);
      break;
    }
    case "page.scan":
      if (site && event.data && event.data.brand && !event.data.brandDomain) edge(site, node("brand", event.data.brand, t), "impersonates", t, "page sensor", false);
      break;
    default:
      break;
  }
  trim();
  save();
};

sec.markAlert = async function markAlert(type, value) {
  await load();
  const id = type + ":" + value;
  if (graph.nodes[id]) { graph.nodes[id].alert = true; save(); }
};

// ---- algorithms ------------------------------------------------------------------------------

// Connected components with union-find; each component lists whether it
// touches an alert, so "everything linked to this bad host" is one lookup.
sec.components = function components(g) {
  const parent = {};
  const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  for (const id of Object.keys(g.nodes)) parent[id] = id;
  for (const e of Object.values(g.edges)) if (parent[e.from] !== undefined && parent[e.to] !== undefined) { const a = find(e.from), b = find(e.to); if (a !== b) parent[a] = b; }
  const groups = {};
  for (const id of Object.keys(g.nodes)) (groups[find(id)] = groups[find(id)] || []).push(id);
  return Object.values(groups).map((members) => ({ members, size: members.length, alert: members.some((id) => g.nodes[id].alert) })).sort((a, b) => (b.alert - a.alert) || (b.size - a.size));
};

// Addresses that serve several different sites' hosts: shared infrastructure.
sec.sharedInfrastructure = function sharedInfrastructure(g) {
  const byIp = {};
  for (const e of Object.values(g.edges)) if (e.type === "resolves-to") (byIp[e.to] = byIp[e.to] || new Set()).add(e.from);
  return Object.entries(byIp).map(([ip, hosts]) => ({ ip: ip.slice(3), hosts: [...hosts].map((h) => h.slice(5)), sites: new Set([...hosts].map((h) => Shield.siteOf(h.slice(5)))).size, alert: [...hosts].some((h) => g.nodes[h] && g.nodes[h].alert) }))
    .filter((item) => item.sites >= 2).sort((a, b) => (b.alert - a.alert) || (b.sites - a.sites));
};

// Third-party hosts that follow you across many sites.
sec.recurringDestinations = function recurringDestinations(g, minSites = 3) {
  const bySite = {};
  for (const e of Object.values(g.edges)) if (e.type === "loads-from") (bySite[e.to] = bySite[e.to] || new Set()).add(e.from);
  return Object.entries(bySite).map(([host, sites]) => ({ host: host.slice(5), sites: sites.size, owner: g.nodes[host] && g.nodes[host].owner })).filter((item) => item.sites >= minSites).sort((a, b) => b.sites - a.sites);
};

// The neighbourhood of one node, for the drawing: up to `limit` nodes, alerts first.
sec.neighbourhood = function neighbourhood(g, start, depth = 2, limit = 80) {
  const seen = new Set([start]);
  let frontier = [start];
  for (let level = 0; level < depth; level++) {
    const next = [];
    for (const e of Object.values(g.edges)) {
      for (const [a, b] of [[e.from, e.to], [e.to, e.from]]) if (frontier.includes(a) && !seen.has(b) && seen.size < limit) { seen.add(b); next.push(b); }
    }
    frontier = next;
  }
  const nodes = [...seen].map((id) => g.nodes[id]).filter(Boolean);
  const edges = Object.values(g.edges).filter((e) => seen.has(e.from) && seen.has(e.to));
  return { nodes, edges };
};

sec.graphSnapshot = async function graphSnapshot() { await load(); return graph; };
sec.clearGraph = async function clearGraph() { graph = { nodes: {}, edges: {} }; if (Shield.api && Shield.api.storage) await Shield.api.storage.local.remove("secGraph"); };
sec._resetGraphForTests = function resetGraphForTests() { graph = { nodes: {}, edges: {} }; };
})();
