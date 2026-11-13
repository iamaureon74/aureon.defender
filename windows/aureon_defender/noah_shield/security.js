// The security center page: nine views onto one engine (lib/sec).
// Everything shown is read from the worker; nothing here decides anything.
"use strict";
(() => {
const send = (message) => Shield.send(message);
const $ = (id) => document.getElementById(id);
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value; // the page's policy forbids style attributes; the cssom is allowed
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : String(child));
  return node;
}
const when = (t) => { const d = new Date(t); return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }); };
const ago = (t) => { const s = Math.round((Date.now() - t) / 1000); return s < 60 ? s + " s ago" : s < 3600 ? Math.round(s / 60) + " min ago" : s < 86400 ? Math.round(s / 3600) + " h ago" : Math.round(s / 86400) + " days ago"; };
const sev = (level) => el("span", { class: "sev " + level }, level);
const card = (title, ...body) => el("section", { class: "glass card" }, title ? el("h2", {}, title) : null, ...body);
const empty = (text) => el("p", { class: "empty" }, text);
function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: name.endsWith(".json") ? "application/json" : "text/plain" }));
  const a = el("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
let settings = null;
async function loadSettings() { settings = await Shield.loadSettings(); return settings; }
async function change(part) { const answer = await send({ type: "settings.update", change: part }); settings = answer.settings || settings; }

// ---- tabs -----------------------------------------------------------------------------------
const views = {};
let current = "overview";
function show(name, arg) {
  current = name;
  for (const button of document.querySelectorAll(".sec-tabs button")) button.setAttribute("aria-selected", String(button.dataset.tab === name));
  for (const pane of document.querySelectorAll(".pane")) pane.hidden = pane.id !== "pane-" + name;
  history.replaceState(null, "", "#" + name + (arg ? ":" + encodeURIComponent(arg) : ""));
  views[name]($("pane-" + name), arg).catch((error) => $("pane-" + name).replaceChildren(card("could not load", el("p", {}, String(error)))));
}
for (const button of document.querySelectorAll(".sec-tabs button")) button.addEventListener("click", () => show(button.dataset.tab));

// ---- 1. overview -------------------------------------------------------------------------------
views.overview = async (pane) => {
  const o = await send({ type: "sec.overview" });
  $("sec-status").textContent = `${o.rules} rules · ${o.intel.hosts.toLocaleString()} known-bad hosts loaded`;
  const kpi = (n, words) => el("div", { class: "kpi" }, el("b", {}, Number(n || 0).toLocaleString()), el("span", {}, words));
  const feeds = Object.entries(o.intel.feeds || {});
  pane.replaceChildren(
    card(null, el("div", { class: "kpis" },
      kpi(o.open, "open investigations"), kpi(o.bySeverity.critical, "critical"), kpi(o.bySeverity.high, "high"),
      kpi(o.today.events, "events in 24 h"), kpi(o.today.blocked, "requests blocked"), kpi(o.today.intelHits, "threat-list matches"))),
    card("latest investigations", o.cases.length ? caseTable(o.cases.slice(0, 8)) : empty("nothing suspicious has been recorded. that is the normal state.")),
    card("threat lists", feeds.length ? el("table", { class: "list" }, el("tr", {}, el("th", {}, "list"), el("th", {}, "state"), el("th", {}, "updated")),
      feeds.map(([id, f]) => el("tr", {}, el("td", {}, id), el("td", {}, f.ok ? f.count.toLocaleString() + " entries" : el("span", { class: "tag warn" }, f.error || "not loaded")), el("td", {}, ago(f.at))))) : empty("no list downloaded yet. open “threat intel” to turn one on."))
  );
};

// ---- media cleaner (strip metadata / fingerprints, shrink losslessly) ---------------------------
views.mediaclean = async (pane) => {
  pane.replaceChildren(card("media cleaner", empty("looking for images this page loaded…")));
  const r = await send({ type: "media.assets" }).catch(() => null);
  const items = (r && r.items) || [];
  const head = el("p", { class: "audit-why" }, "strips every metadata layer — exif, gps, xmp, iptc, icc thumbnails, maker-notes, timestamps — without changing a single pixel, and shrinks the file losslessly. a fingerprint baked into the pixels (an invisible watermark or sensor noise) cannot be removed without re-encoding and quality loss.");
  if (!items.length) { pane.replaceChildren(card("media cleaner", head, empty("no images detected on the current page yet. open or reload an image-heavy page in another tab, then reopen this."))); return; }
  const list = el("div", { class: "media-list" });
  for (const item of items) {
    const name = item.filename || (() => { try { return new URL(item.url).pathname.split("/").pop(); } catch { return "image"; } })();
    const status = el("span", { class: "muted small" }, "");
    const button = el("button", { class: "act", onclick: async () => {
      button.disabled = true; status.textContent = "reading + stripping…";
      const res = await send({ type: "media.clean", url: item.url, name }).catch((e) => ({ error: String(e) }));
      button.disabled = false;
      if (!res || res.error) { status.textContent = res && res.error ? res.error : "could not clean this file"; status.className = "sev medium"; return; }
      status.className = "media-done";
      status.textContent = `saved to downloads · ${res.removed.length ? "removed " + res.removed.join(", ") + " · " : "no metadata found · "}${fmtBytes(res.before)} → ${fmtBytes(res.after)} (${res.savedPct}% smaller)`;
    } }, "strip & shrink");
    list.append(el("div", { class: "media-row" },
      el("div", { class: "media-meta" }, el("b", { class: "mono" }, String(name).slice(0, 60)), el("div", { class: "muted small" }, item.mimeType || item.type || "")),
      button, status));
  }
  pane.replaceChildren(card("media cleaner", head, list));
};
function fmtBytes(n) { return n > 1048576 ? (n / 1048576).toFixed(2) + " MB" : n > 1024 ? (n / 1024).toFixed(1) + " KB" : n + " B"; }

// ---- site audit -------------------------------------------------------------------------------
async function httpTabs() {
  try {
    const tabs = await Shield.api.tabs.query({});
    return tabs.filter((t) => t.url && /^https?:/.test(t.url) && !t.url.startsWith(Shield.api.runtime.getURL("")))
      .sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0));
  } catch { return []; }
}
function gradeBadge(grade, score) {
  const g = String(grade || "F").toLowerCase().replace(/[^a-z]/g, "");
  return el("div", { class: "audit-grade g-" + g },
    el("b", {}, grade || "—"),
    el("span", { class: "audit-score" }, Number(score || 0) + " / 100"));
}
views.audit = async (pane, arg) => {
  const tabs = await httpTabs();
  if (!tabs.length) { pane.replaceChildren(card("site audit", empty("open a normal web page in another tab, then come back here to grade its security."))); return; }
  let target = tabs.find((t) => String(t.id) === String(arg)) || tabs[0];

  const picker = el("select", { class: "audit-pick", onchange: () => show("audit", picker.value) },
    tabs.map((t) => el("option", { value: String(t.id), selected: t.id === target.id ? true : undefined }, (new URL(t.url).host + new URL(t.url).pathname).slice(0, 60))));
  const body = el("div", {}, empty("reading the headers, cookies and page this site already sent…"));
  pane.replaceChildren(card("site audit", el("div", { class: "actions-row" }, picker,
    el("button", { class: "act primary", onclick: () => show("audit", String(target.id)) }, "re-run")), body));

  const r = await send({ type: "sec.audit", tabId: target.id, url: target.url }).catch((e) => ({ error: String(e) }));
  if (!r || r.error) { body.replaceChildren(empty(r && r.error ? r.error : "could not audit this page.")); return; }

  const hist = await send({ type: "sec.auditHistory", host: r.host }).catch(() => null);
  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of r.findings) counts[f.severity] = (counts[f.severity] || 0) + 1;

  body.replaceChildren(
    el("div", { class: "audit-head" }, gradeBadge(r.grade, r.score),
      el("div", { class: "audit-meta" },
        el("div", { class: "mono" }, r.host),
        el("div", {}, r.https ? "served over https" : el("span", { class: "sev high" }, "served over plain http")),
        el("div", {}, `${r.failed} issue${r.failed === 1 ? "" : "s"} · ${r.passed} protection${r.passed === 1 ? "" : "s"} in place · ${r.cookies} cookie${r.cookies === 1 ? "" : "s"} checked`),
        el("div", { class: "audit-tally" },
          counts.critical ? el("span", { class: "sev critical" }, counts.critical + " critical") : null,
          counts.high ? el("span", { class: "sev high" }, counts.high + " high") : null,
          counts.medium ? el("span", { class: "sev medium" }, counts.medium + " medium") : null,
          counts.low ? el("span", { class: "sev low" }, counts.low + " low") : null))),
    r.findings.length
      ? el("table", { class: "list audit-findings" },
          el("tr", {}, el("th", {}, "severity"), el("th", {}, "weakness"), el("th", {}, "standard"), el("th", {}, "how to fix")),
          r.findings.map((f) => el("tr", {},
            el("td", {}, sev(f.severity)),
            el("td", {}, el("b", {}, f.title), f.vector ? el("span", { class: "audit-vector" }, f.vector) : null, f.why ? el("div", { class: "audit-why" }, f.why) : null, Array.isArray(f.detail) && f.detail.length ? el("div", { class: "mono audit-detail" }, f.detail.join(" · ")) : null),
            el("td", { class: "mono" }, [f.owasp, f.cwe].filter(Boolean).join(" · ") || "—"),
            el("td", {}, f.fix || "—"))))
      : el("p", { class: "empty" }, "no configuration weaknesses found in what this page sent. that is a strong result."),
    Array.isArray(r.domains) && r.domains.length ? el("div", { class: "audit-domains" },
      el("h3", {}, `domains & subdomains this page used (${r.domains.length}${r.thirdParties ? ", " + r.thirdParties + " third-party" : ""})`),
      el("table", { class: "list" },
        el("tr", {}, el("th", {}, "domain / subdomain"), el("th", {}, "transport"), el("th", {}, "party"), el("th", {}, "security")),
        r.domains.map((d) => el("tr", {},
          el("td", { class: "mono" }, d.host),
          el("td", {}, d.https ? "https" : el("span", { class: "sev medium" }, "http")),
          el("td", {}, d.thirdParty ? "third-party" : "same-site"),
          el("td", {}, d.bad ? el("span", { class: "sev critical" }, d.bad) : d.https ? el("span", { class: "tag ok" }, "ok") : el("span", { class: "sev medium" }, "unencrypted")))))) : null,
    hist && hist.list && hist.list.length > 1 ? el("p", { class: "audit-hist" }, "past grades: " + hist.list.map((h) => h.grade).join(" → ")) : null,
    r.coverage ? el("details", { class: "audit-coverage" },
      el("summary", {}, "what this grade covers — and what it can't"),
      el("p", { class: "audit-why" }, "graded passively (from what the browser already received):"),
      el("ul", {}, (r.coverage.gradedPassively || []).map((t) => el("li", {}, t))),
      el("p", { class: "audit-why" }, "not gradable without active testing noah does not do (so a clean grade is not a clean bill for these):"),
      el("ul", {}, (r.coverage.needsActiveTesting || []).map((t) => el("li", {}, t)))) : null,
    el("p", { class: "audit-note" }, "this audit reads only what this site already sent your browser — its response headers, its cookies, the page, its storage and its sub/domains — and scores it against the owasp secure-headers project, mitre cwe and the mozilla observatory model. nothing is probed or attacked. every issue is one the site's owner can fix.")
  );
};

function caseTable(cases) {
  return el("table", { class: "list" },
    el("tr", {}, el("th", {}, "severity"), el("th", {}, "subject"), el("th", {}, "findings"), el("th", {}, "status"), el("th", {}, "updated")),
    cases.map((c) => el("tr", { class: "click", onclick: () => show("cases", c.id) },
      el("td", {}, sev(c.severity)), el("td", { class: "mono" }, c.subject.replace(/^\w+:/, "")),
      el("td", {}, c.titles.slice(0, 3).join(" · ")), el("td", {}, c.status), el("td", {}, ago(c.updated)))));
}

// ---- 2. investigations + 12. containment -----------------------------------------------------------
views.cases = async (pane, id) => {
  if (!id) {
    const o = await send({ type: "sec.overview" });
    pane.replaceChildren(card("investigations", o.cases.length ? caseTable(o.cases) : empty("no investigations.")),
      card(null, el("div", { class: "actions-row" }, el("button", { class: "act danger", onclick: async () => { if (confirm("forget every event, investigation and graph entry on this device?")) { await send({ type: "sec.clear" }); show("cases"); } } }, "clear all security history"))));
    return;
  }
  const { item, events, ledger, error } = await send({ type: "sec.case", id });
  if (error) { pane.replaceChildren(card("not found", empty(error))); return; }
  const actionButton = (action, index) => {
    const label = { "block-host": "block " + action.target, "close-tab": "close the tab", "hold-download": "hold the download", "delete-download": "delete the download", "disable-extension": "turn off the extension" }[action.action] || action.action;
    if (action.state !== "suggested") return el("span", { class: "tag" + (action.state === "failed" ? " bad" : "") }, `${label}: ${action.state}${action.error ? " (" + action.error + ")" : ""}`);
    return el("button", { class: "act" + (action.action === "disable-extension" ? " danger" : " primary"), onclick: async () => {
      const confirmed = action.action === "disable-extension" ? confirm("turn this extension off? you can turn it back on here or in chrome://extensions.") : true;
      if (!confirmed) return;
      const answer = await send({ type: "sec.contain", id: item.id, index, confirmed });
      if (answer.error) alert(answer.error);
      show("cases", item.id);
    } }, label);
  };
  pane.replaceChildren(
    card(null,
      el("div", { class: "row" }, sev(item.severity), el("h2", { style: "margin:0" }, item.subject.replace(/^\w+:/, "")), el("span", { class: "tag" }, item.status)),
      el("p", { class: "muted" }, `opened ${when(item.opened)} · last activity ${ago(item.updated)} · ${events.length} recorded events`),
      el("div", { class: "actions-row" },
        el("button", { class: "act", onclick: () => show("cases") }, "← all investigations"),
        item.status !== "dismissed" ? el("button", { class: "act", onclick: async () => { await send({ type: "sec.status", id: item.id, status: "dismissed" }); show("cases", item.id); } }, "not a threat (dismiss)") : el("button", { class: "act", onclick: async () => { await send({ type: "sec.status", id: item.id, status: "open" }); show("cases", item.id); } }, "reopen"),
        el("button", { class: "act", onclick: async () => { await send({ type: "sec.status", id: item.id, status: "resolved" }); show("cases", item.id); } }, "mark resolved"),
        el("button", { class: "act", onclick: async () => { const r = await send({ type: "sec.report", id: item.id }); download(r.name, r.text); } }, "report (text)"),
        el("button", { class: "act", onclick: async () => { const r = await send({ type: "sec.report", id: item.id, format: "stix" }); download(r.name, r.text); } }, "report (stix 2.1)"))),
    card("findings", item.detections.map((d) => el("div", { class: "finding" },
      el("h3", {}, sev(d.severity), " ", d.title),
      el("p", {}, d.why),
      d.falsePositives ? el("p", { class: "meta" }, "can be wrong when: " + d.falsePositives) : null,
      el("p", { class: "meta" }, `${d.rule} · mitre att&ck ${d.attack} (${d.tactic}) · seen ${d.times}× · ${ago(d.last)}`)))),
    card("contain", item.actions.length ? el("div", { class: "actions-row" }, item.actions.map(actionButton)) : empty("no containment action fits this finding."),
      ledger.length ? el("table", { class: "list", style: "margin-top:12px" }, el("tr", {}, el("th", {}, "when"), el("th", {}, "action"), el("th", {}, "by"), el("th", {}, "")),
        ledger.map((entry) => el("tr", {}, el("td", {}, when(entry.at)), el("td", {}, `${entry.action} ${entry.target || ""} ${entry.ok ? "" : "(failed: " + (entry.error || "?") + ")"}`), el("td", {}, entry.by),
          el("td", {}, entry.undo && !entry.undone ? el("button", { class: "act", onclick: async () => { const r = await send({ type: "sec.undo", index: entry.index }); if (r.error) alert(r.error); show("cases", item.id); } }, "undo") : entry.undone ? "undone" : "")))) : null),
    el("div", { class: "grid2" },
      card("timeline", el("ol", { class: "timeline" }, item.timeline.map((t) => el("li", {}, el("time", {}, when(t.t) + " · " + t.kind + " · event " + t.event), t.text))))),
      card("affected", item.resources.length ? el("ul", {}, item.resources.map((r) => el("li", { class: "mono" }, r))) : empty("—"),
        el("h2", { style: "margin-top:14px" }, "evidence"), el("table", { class: "list" }, events.slice(-20).map((e) => el("tr", {}, el("td", { class: "mono" }, "#" + e.id), el("td", {}, e.kind), el("td", {}, e.source), el("td", { class: "mono" }, e.host || "")))))
  );
};

// ---- 6. network ----------------------------------------------------------------------------------
views.network = async (pane, arg) => {
  const hours = Number(arg) || 1;
  const n = await send({ type: "sec.network", hours });
  const picker = el("div", { class: "row" }, [1, 24, 168].map((h) => el("button", { class: "act" + (h === hours ? " primary" : ""), onclick: () => show("network", String(h)) }, h === 1 ? "last hour" : h === 24 ? "24 hours" : "7 days")));
  pane.replaceChildren(
    card("network activity", picker, el("p", { class: "muted" }, `${n.totals.hosts} hosts · ${n.totals.ips} addresses · ${n.totals.events} events. what the browser itself saw; traffic of other apps needs the native companion.`)),
    card("hosts contacted", n.hosts.length ? el("table", { class: "list" },
      el("tr", {}, el("th", {}, "host"), el("th", {}, "owner"), el("th", {}, "addresses"), el("th", {}, "types"), el("th", {}, "on pages"), el("th", { class: "num" }, "loaded"), el("th", { class: "num" }, "blocked"), el("th", { class: "num" }, "threat")),
      n.hosts.slice(0, 200).map((h) => el("tr", {},
        el("td", { class: "mono" }, h.host, h.thirdParty ? el("span", { class: "tag" }, "3rd party") : null),
        el("td", {}, h.owner || ""), el("td", { class: "mono" }, h.ips.join(" ")), el("td", {}, h.types.join(", ")), el("td", {}, h.pages.slice(0, 3).join(", ")),
        el("td", { class: "num" }, h.requests), el("td", { class: "num" }, h.blocked), el("td", { class: "num" }, h.intel ? el("span", { class: "tag bad" }, h.intel) : "0")))) : empty("nothing recorded in this window yet.")),
    card("timeline", el("ol", { class: "timeline" }, n.timeline.slice(0, 120).map((t) => el("li", {}, el("time", {}, when(t.t) + " · " + t.kind), t.text))))
  );
};

// ---- 13. graph --------------------------------------------------------------------------------------
const COLORS = { site: "#c9d27a", host: "#9fb3a0", ip: "#8aa0c8", file: "#d9c08a", indicator: "#e8a08a", url: "#c6c7aa", brand: "#e6c27e" };
views.graph = async (pane, node) => {
  const g = await send({ type: "sec.graph", node });
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "graph");
  svg.setAttribute("viewBox", "0 0 1000 520");
  layout(svg, g.view, g.start);
  pane.replaceChildren(
    card("relationship graph", el("p", { class: "muted" }, `${g.stats.nodes} nodes · ${g.stats.edges} links · ${g.stats.components} groups, ${g.stats.alertComponents} touching a threat. solid lines were observed; dashed lines are unconfirmed associations. click a node to centre on it.`),
      el("div", { class: "legend" }, Object.entries(COLORS).map(([type, color]) => el("span", {}, el("i", { style: "background:" + color }), type)), el("span", {}, el("i", { style: "background:transparent;border:2px solid #e8a08a" }), "linked to a threat")),
      g.view.nodes.length ? svg : empty("the graph fills as you browse.")),
    el("div", { class: "grid2" },
      card("shared infrastructure", g.shared.length ? el("table", { class: "list" }, el("tr", {}, el("th", {}, "address"), el("th", {}, "hosts on it")), g.shared.slice(0, 20).map((s) => el("tr", { class: "click", onclick: () => show("graph", "ip:" + s.ip) }, el("td", { class: "mono" }, s.ip, s.alert ? el("span", { class: "tag bad" }, "threat") : null), el("td", { class: "mono" }, s.hosts.slice(0, 6).join(" "))))) : empty("no address serves more than one site yet.")),
      card("followed you across sites", g.recurring.length ? el("table", { class: "list" }, el("tr", {}, el("th", {}, "host"), el("th", {}, "owner"), el("th", { class: "num" }, "sites")), g.recurring.slice(0, 20).map((r) => el("tr", { class: "click", onclick: () => show("graph", "host:" + r.host) }, el("td", { class: "mono" }, r.host), el("td", {}, r.owner || ""), el("td", { class: "num" }, r.sites)))) : empty("nothing has followed you across three or more sites yet.")))
  );
};

// A small force layout: repulsion, spring edges, the centre node pinned.
function layout(svg, view, start) {
  const W = 1000, H = 520;
  const nodes = view.nodes.map((n, i) => ({ ...n, x: W / 2 + Math.cos(i) * (80 + i * 4), y: H / 2 + Math.sin(i) * (80 + i * 3), vx: 0, vy: 0 }));
  const index = Object.fromEntries(nodes.map((n, i) => [n.id, i]));
  const links = view.edges.filter((e) => index[e.from] !== undefined && index[e.to] !== undefined);
  const centre = nodes[index[start]];
  if (centre) { centre.x = W / 2; centre.y = H / 2; }
  for (let step = 0; step < 260; step++) {
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y; const d2 = Math.max(dx * dx + dy * dy, 30);
      const force = 1600 / d2; dx *= force / Math.sqrt(d2); dy *= force / Math.sqrt(d2);
      a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
    }
    for (const l of links) {
      const a = nodes[index[l.from]], b = nodes[index[l.to]];
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, pull = (d - 90) * 0.02;
      a.vx += dx / d * pull; a.vy += dy / d * pull; b.vx -= dx / d * pull; b.vy -= dy / d * pull;
    }
    for (const n of nodes) {
      if (n === centre) { n.vx = n.vy = 0; continue; }
      n.vx += (W / 2 - n.x) * 0.002; n.vy += (H / 2 - n.y) * 0.002;
      n.x = Math.max(20, Math.min(W - 20, n.x + n.vx * 0.5)); n.y = Math.max(20, Math.min(H - 20, n.y + n.vy * 0.5));
      n.vx *= 0.82; n.vy *= 0.82;
    }
  }
  const NS = "http://www.w3.org/2000/svg";
  for (const l of links) {
    const a = nodes[index[l.from]], b = nodes[index[l.to]];
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", a.x); line.setAttribute("y1", a.y); line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
    line.setAttribute("class", l.verified ? "verified" : "unverified");
    const title = document.createElementNS(NS, "title"); title.textContent = `${l.type} · ${l.source} · ${l.count}× · ${l.verified ? "observed" : "unconfirmed"}`; line.append(title);
    svg.append(line);
  }
  for (const n of nodes) {
    const circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", n.x); circle.setAttribute("cy", n.y); circle.setAttribute("r", n.id === start ? 9 : Math.min(8, 4 + Math.log2(1 + n.count)));
    circle.setAttribute("fill", COLORS[n.type] || "#9a9f80");
    if (n.alert) circle.setAttribute("class", "alert");
    const title = document.createElementNS(NS, "title"); title.textContent = `${n.type}: ${n.label}${n.owner ? " (" + n.owner + ")" : ""} · seen ${n.count}×`; circle.append(title);
    circle.addEventListener("click", () => show("graph", n.id));
    svg.append(circle);
    const text = document.createElementNS(NS, "text");
    text.setAttribute("x", n.x + 10); text.setAttribute("y", n.y + 3);
    text.textContent = String(n.name || n.label).slice(0, 34);
    svg.append(text);
  }
}

// ---- 3. extensions -----------------------------------------------------------------------------------
views.extensions = async (pane) => {
  const { list = [], error } = await send({ type: "sec.extensions" });
  const powerful = /<all_urls>|^\*:\/\/\*|^https?:\/\/\*\/|cookies|debugger|webRequest|nativeMessaging|proxy|management|history|desktopCapture|tabCapture|clipboardRead|scripting/;
  pane.replaceChildren(card("installed extensions", error ? empty(error) : el("p", { class: "muted" }, "the shield notes every permission each extension has and raises an investigation when one gains more; takeovers of popular extensions look exactly like that."),
    el("table", { class: "list" }, el("tr", {}, el("th", {}, "extension"), el("th", {}, "source"), el("th", {}, "risk"), el("th", {}, "can"), el("th", {}, "history"), el("th", {}, "")),
      list.sort((a, b) => ((b.risk && b.risk.score) || 0) - ((a.risk && a.risk.score) || 0)).map((x) => el("tr", {},
        el("td", {}, el("b", {}, x.name), el("div", { class: "mono" }, x.id + " · v" + x.version), x.self ? el("span", { class: "tag" }, "this shield") : null),
        el("td", {}, x.store === "store" ? "store" : el("span", { class: "tag warn" }, x.store || x.installType)),
        el("td", {}, x.risk ? el("span", { class: "tag" + (x.risk.level === "watch" ? " bad" : x.risk.level === "note" ? " warn" : "") }, x.risk.level) : "", x.risk && x.risk.reasons.length ? el("div", { class: "meta" }, x.risk.reasons.slice(0, 3).join("; ")) : null),
        el("td", {}, x.perms.slice(0, 14).map((p) => el("span", { class: "tag" + (powerful.test(p) ? " warn" : "") }, p)), x.perms.length > 14 ? " +" + (x.perms.length - 14) : ""),
        el("td", {}, x.history.slice(-3).reverse().map((h) => el("div", { class: "meta" }, `${ago(h.t)}: ${h.change}${h.added && h.added.length && h.change !== "first seen" ? " (+" + h.added.join(", ") + ")" : ""}`))),
        el("td", {}, x.self || x.mayDisable === false ? "" : el("button", { class: "act" + (x.enabled ? " danger" : ""), onclick: async () => { if (x.enabled && !confirm("turn off " + x.name + "?")) return; await send({ type: "sec.disableExtension", id: x.id, enabled: !x.enabled }); show("extensions"); } }, x.enabled ? "turn off" : "turn on")))))));
};

// ---- 8. files -------------------------------------------------------------------------------------------
views.files = async (pane) => {
  const { list = [] } = await send({ type: "sec.files" });
  const input = el("input", { type: "text", placeholder: "https://… address of a file to examine" });
  const out = el("div");
  pane.replaceChildren(
    card("examine a file", el("p", { class: "muted" }, "risky downloads are examined automatically while they are held. the file is read as bytes and never opened or run: its real type, hidden endings, archive contents, macros, pdf scripts, and its sha-256 against threat lists (malwarebazaar needs your free abuse.ch key)."),
      el("div", { class: "row" }, input, el("button", { class: "act primary", onclick: async () => {
        out.replaceChildren(empty("reading the file…"));
        const r = await send({ type: "sec.scanUrl", url: input.value.trim() });
        out.replaceChildren(r.error ? empty(r.error) : scanCard({ data: r, t: Date.now(), url: input.value.trim() }));
      } }, "examine")), out),
    card("examined files", list.length ? list.map(scanCard) : empty("no file has been examined yet."))
  );
};
function scanCard(event) {
  const d = event.data;
  const bad = d.knownMalware || d.disguised || d.yaraMatch, warn = d.activeContent || (d.findings || []).length;
  return el("div", { class: "finding" },
    el("h3", {}, el("span", { class: "tag" + (bad ? " bad" : warn ? " warn" : "") }, bad ? "dangerous" : warn ? "look twice" : "nothing found"), " ", d.name || "file"),
    el("p", { class: "meta" }, `${d.type} · ${(d.size || 0).toLocaleString()} bytes · ${event.t ? ago(event.t) : ""}`),
    el("p", { class: "mono" }, "sha-256 " + d.sha256),
    (d.findings || []).length ? el("ul", {}, d.findings.map((f) => el("li", {}, f))) : null,
    d.entries && d.entries.length ? el("p", { class: "meta" }, "inside: " + d.entries.slice(0, 12).map((e) => e.name || e).join(", ")) : null);
}

// ---- intel (sources, your indicators, the switches) ---------------------------------------------------------
views.intel = async (pane) => {
  await loadSettings();
  const cfg = settings.secCenter;
  const intel = await send({ type: "sec.intel" });
  const toggle = (label, path, value) => el("label", { class: "switch" }, el("input", { type: "checkbox", checked: Boolean(value) || undefined, onchange: (e) => change({ secCenter: path(e.target.checked) }) }), el("span", {}, label));
  const key = el("input", { type: "password", placeholder: "abuse.ch auth-key (free at auth.abuse.ch)", value: cfg.abuseKey || "" });
  const blockUrl = el("input", { type: "url", placeholder: "https://… blocklist address (one ip, host or address per line)", value: cfg.blocklistUrl || "" });
  const blockUser = el("input", { type: "text", placeholder: "username (if any)", value: cfg.blocklistUser || "", autocomplete: "off" });
  const blockPass = el("input", { type: "password", placeholder: "password (if any)", value: cfg.blocklistPass || "", autocomplete: "off" });
  const yaraText = el("textarea", { rows: "10", spellcheck: "false", class: "mono", placeholder: 'rule My_Rule\n{\n    meta:\n        description = "what it means"\n        severity = "high"\n    strings:\n        $a = "text" nocase\n        $b = { 4D 5A ?? 90 }\n    condition:\n        $a and $b\n}' });
  yaraText.value = cfg.yaraRules || "";
  const yaraStatus = el("p", { class: "muted" });
  const yaraReport = (r) => { yaraStatus.textContent = `${r.bundled} bundled + ${r.yours} of yours in use` + (r.skipped.length ? ` · skipped (not supported here): ${r.skipped.join(", ")}` : "") + (r.errors.length ? ` · errors: ${r.errors.join(" | ")}` : ""); };
  send({ type: "sec.yaraCheck" }).then((r) => { if (r && !r.error) yaraReport(r); });
  const status = el("p", { class: "muted" });
  const type = el("select", {}, ["host", "ip", "hash", "url"].map((t) => el("option", { value: t }, t)));
  const value = el("input", { type: "text", placeholder: "evil.example, 203.0.113.7, a sha-256, or an address" });
  const category = el("select", {}, ["malware", "phishing", "scam", "tracking", "suspicious"].map((t) => el("option", { value: t }, t)));
  pane.replaceChildren(
    card("threat lists", el("p", { class: "muted" }, "lists are downloaded whole and checked here: no address you visit is sent to anyone to be checked."),
      toggle("urlhaus (abuse.ch): hosts spreading malware", (v) => ({ feeds: { urlhaus: v } }), cfg.feeds.urlhaus),
      toggle("openphish community: phishing addresses (free for personal, non-commercial use)", (v) => ({ feeds: { openphish: v } }), cfg.feeds.openphish),
      toggle("mvt spyware indicators: Pegasus, Predator, Candiru, stalkerware and more (Amnesty, Citizen Lab and others, via the Mobile Verification Toolkit)", (v) => ({ feeds: { mvt: v } }), cfg.feeds.mvt),
      toggle("your own blocklist at an address below (a CrowdSec blocklist integration works as is)", (v) => ({ feeds: { blocklist: v } }), cfg.feeds.blocklist),
      el("div", { class: "row" }, key, el("button", { class: "act", onclick: async () => { await change({ secCenter: { abuseKey: key.value.trim() } }); status.textContent = "key saved."; } }, "save key")),
      el("div", { class: "row" }, blockUrl, blockUser, blockPass, el("button", { class: "act", onclick: async () => { await change({ secCenter: { blocklistUrl: blockUrl.value.trim(), blocklistUser: blockUser.value.trim(), blocklistPass: blockPass.value } }); status.textContent = "blocklist saved."; } }, "save blocklist")),
      el("div", { class: "actions-row" }, el("button", { class: "act primary", onclick: async () => { status.textContent = "downloading…"; const r = await send({ type: "sec.refreshFeeds" }); status.textContent = r.skipped || Object.entries(r).filter(([k]) => k !== "blockRules").map(([k, v]) => `${k}: ${v.ok ? v.count.toLocaleString() + " entries" : v.error}`).join(" · ") + ` · ${r.blockRules || 0} block rules`; } }, "update lists now")),
      status,
      el("p", { class: "meta" }, `loaded: ${intel.hosts.toLocaleString()} hosts · ${intel.urls.toLocaleString()} addresses · ${intel.ips} ips · ${intel.hashes} file hashes`)),
    card("what happens on a match",
      toggle("contain confirmed critical threats by themselves (block the host, close the page, delete a known-malware file)", (v) => ({ autoContain: v }), cfg.autoContain),
      toggle("turn listed hosts into block rules", (v) => ({ feedBlock: v }), cfg.feedBlock),
      toggle("examine risky downloads while they are held", (v) => ({ scanFiles: v }), cfg.scanFiles),
      toggle("ask the registry (rdap) how old a store's domain is, only when it already shows a scam sign", (v) => ({ domainAgeLookups: v }), cfg.domainAgeLookups),
      toggle("security center on", (v) => ({ enabled: v }), cfg.enabled)),
    card("yara rules", el("p", { class: "muted" }, "every examined file is also checked against yara rules: a bundled set (download cradles, credential stealers, implants, miners, ransom notes, malicious shortcuts and documents) and any you add here. rules are written in yara's own language; ones that need modules (import \"pe\"), for-loops, xor or base64 strings are skipped and named below."),
      yaraText,
      el("div", { class: "actions-row" }, el("button", { class: "act primary", onclick: async () => { await change({ secCenter: { yaraRules: yaraText.value } }); const r = await send({ type: "sec.yaraCheck" }); if (r.error) yaraStatus.textContent = r.error; else yaraReport(r); } }, "save and check rules")),
      yaraStatus),
    card("your own indicators", el("p", { class: "muted" }, "add what you know to be bad. hosts are blocked; all of them are shared to your other devices when encrypted sync is on."),
      el("div", { class: "row" }, type, value, category, el("button", { class: "act primary", onclick: async () => { const r = await send({ type: "sec.intelAdd", kind: type.value, value: value.value, category: category.value }); if (r.error) alert(r.error); show("intel"); } }, "add")),
      intel.mine.length ? el("table", { class: "list" }, intel.mine.map((m) => el("tr", {}, el("td", {}, m.type), el("td", { class: "mono" }, m.value), el("td", {}, m.category), el("td", {}, ago(m.added)), el("td", {}, el("button", { class: "act", onclick: async () => { await send({ type: "sec.intelRemove", kind: m.type, value: m.value }); show("intel"); } }, "remove"))))) : empty("none yet."))
  );
};

// ---- 4. identity + 5. removals --------------------------------------------------------------------------------
views.identity = async (pane) => {
  const id = await send({ type: "sec.identity" });
  const { list = [] } = await send({ type: "sec.removals" });
  const watch = el("textarea", { rows: "3", placeholder: "emails to watch, one per line" }); watch.value = (id.watch || []).join("\n");
  const out = el("div");
  const broker = el("input", { type: "text", placeholder: "site or data broker (e.g. a people-search site)" });
  const where = el("input", { type: "text", placeholder: "address of the listing" });
  const what = el("input", { type: "text", placeholder: "what it shows (name, phone, address…)" });
  const STATES = ["found", "requested", "answered", "removed", "refused", "relisted"];
  pane.replaceChildren(
    card("identity watch", el("p", { class: "muted" }, id.hasKey ? "checked every week against have i been pwned; a new breach opens an investigation." : "needs a have i been pwned key: settings → security and account safety."),
      el("div", { class: "row" }, watch), el("div", { class: "actions-row" },
        el("button", { class: "act", onclick: async () => { await send({ type: "sec.identity", watch: watch.value }); show("identity"); } }, "save list"),
        el("button", { class: "act primary", disabled: !id.hasKey || undefined, onclick: async () => { out.replaceChildren(empty("checking (a few seconds per address)…")); const r = await send({ type: "sec.identity", check: true }); out.replaceChildren(Array.isArray(r.results) ? el("ul", {}, r.results.map((x) => el("li", {}, `${x.email}: ${x.error || (x.breaches.length ? x.breaches.length + " breaches: " + x.breaches.slice(0, 8).join(", ") : "not found in any breach")}`))) : empty(r.results && r.results.skipped || "done")); } }, "check now")),
      out,
      Object.keys(id.state || {}).length ? el("table", { class: "list" }, Object.entries(id.state).map(([email, s]) => el("tr", {}, el("td", {}, email), el("td", {}, s.breaches.length ? el("span", { class: "tag warn" }, s.breaches.length + " breaches") : "clean"), el("td", {}, "checked " + ago(s.checked))))) : null),
    card("removal requests", el("p", { class: "muted" }, "keep track of every listing you asked to take down. a request with no answer after 45 days is flagged; most privacy laws give 30–45 days. “forget me” in tools writes the request letters."),
      el("div", { class: "row" }, broker, where, what, el("button", { class: "act primary", onclick: async () => { await send({ type: "sec.removals", change: { add: { broker: broker.value, url: where.value, categories: what.value } } }); show("identity"); } }, "add")),
      list.length ? el("table", { class: "list" }, el("tr", {}, el("th", {}, "where"), el("th", {}, "shows"), el("th", {}, "status"), el("th", {}, "history"), el("th", {}, "")),
        list.map((r) => el("tr", {}, el("td", {}, r.broker, r.url ? el("div", { class: "mono" }, r.url) : null), el("td", {}, r.categories),
          el("td", {}, (() => { const s = el("select", { onchange: async (e) => { await send({ type: "sec.removals", change: { update: { id: r.id, status: e.target.value } } }); show("identity"); } }, STATES.map((x) => el("option", { value: x, selected: x === r.status || undefined }, x))); return s; })(), r.overdue ? el("span", { class: "tag bad" }, "overdue") : null),
          el("td", {}, r.history.slice(-3).map((h) => el("div", { class: "meta" }, h.status + " · " + ago(h.t)))),
          el("td", {}, el("button", { class: "act", onclick: async () => { await send({ type: "sec.removals", change: { remove: r.id } }); show("identity"); } }, "remove"))))) : empty("no requests tracked."))
  );
};

// ---- 7. device-wide + 11. cross-device ---------------------------------------------------------------------------
views.devices = async (pane) => {
  const d = await send({ type: "sec.devices" });
  const out = el("p", { class: "muted" });
  pane.replaceChildren(
    card("this computer", el("table", { class: "list" },
      el("tr", {}, el("td", {}, "noah desktop helper"), el("td", {}, d.helper.installed ? `installed ${d.helper.version || ""} ${d.helper.platform || ""} · ${d.helper.features.join(", ") || "basic"}` : el("span", { class: "tag warn" }, "not installed"))),
      el("tr", {}, el("td", {}, "device-wide firewall and dns"), el("td", {}, el("span", { class: "tag warn" }, "not available"), " ", d.deviceWide.reason)),
      el("tr", {}, el("td", {}, "browser protection"), el("td", {}, "on: rules, threat lists, containment and file triage run inside the browser")))),
    card("your devices", el("p", { class: "muted" }, "your own indicators travel end-to-end encrypted with your sync passphrase. each device writes a receipt of the set it applied, so this list shows what each one really has."),
      el("div", { class: "actions-row" }, el("button", { class: "act primary", onclick: async () => { const r = await send({ type: "sec.sync" }); out.textContent = r.error || r.skipped || `synced ${r.count} indicators`; show("devices"); } }, "sync now")), out,
      d.devices.length ? el("table", { class: "list" }, el("tr", {}, el("th", {}, "device"), el("th", {}, "browser"), el("th", {}, "last sync"), el("th", {}, "indicators"), el("th", {}, "set")),
        d.devices.map((x) => el("tr", {}, el("td", { class: "mono" }, x.id.slice(0, 10) + (x.self ? " (this one)" : "")), el("td", {}, x.browser + (x.mobile ? " · phone" : "")), el("td", {}, ago(x.at)), el("td", { class: "num" }, x.count), el("td", { class: "mono" }, x.applied)))) : empty("no device has synced yet. turn on encrypted sync in settings, then press sync now."))
  );
};

// ---- local ai, whole-computer protection, noah box (lib/local.js) -------------------------------------------------------
views.local = async (pane) => {
  await loadSettings();
  const ai = settings.localAi, box = settings.noahBox;
  pane.replaceChildren(card("checking what is here…", empty("asking noah, Ollama and your box.")));
  const s = await send({ type: "local.status" });
  const tag = (ok, text) => el("span", { class: "tag" + (ok ? "" : " warn") }, text);
  const reason = (r) => (r && r.error ? " " + r.error : "");

  // local ai
  const aiOn = el("input", { type: "checkbox", checked: ai.enabled || undefined });
  const aiCog = el("input", { type: "checkbox", checked: ai.cognition || undefined });
  const provider = el("select", {}, el("option", { value: "ollama" }, "Ollama on this computer"), el("option", { value: "noah" }, "noah's own model (through the helper)"));
  provider.value = ai.provider;
  const endpoint = el("input", { type: "text", value: ai.endpoint, placeholder: "http://127.0.0.1:11434" });
  const model = el("input", { type: "text", value: ai.model, placeholder: "llama3.2:3b" });
  const aiOut = el("p", { class: "muted" });
  const saveAi = () => change({ localAi: { enabled: aiOn.checked, cognition: aiCog.checked, provider: provider.value, endpoint: endpoint.value.trim(), model: model.value.trim() } });
  for (const input of [aiOn, aiCog, provider]) input.addEventListener("change", saveAi);

  // wireguard
  const wg = s.wireguard || {};
  const wgName = el("input", { type: "text", placeholder: "tunnel name (as noah knows it, e.g. home)" });
  const wgOut = el("p", { class: "muted" });
  const wgAct = (action) => async () => { wgOut.textContent = action === "up" ? "starting…" : "stopping…"; const r = await send({ type: "local.wireguard", action, name: wgName.value.trim() }); wgOut.textContent = r.error || (r.up ? "up" : "down") + (r.endpoint ? " · " + r.endpoint : ""); };
  const tunnels = Array.isArray(wg.tunnels) ? wg.tunnels : [];

  // opensnitch
  const sn = s.opensnitch || {};
  const snOut = el("p", { class: "muted" });

  // noah box
  const boxAddress = el("input", { type: "url", value: box.address, placeholder: "https://noah.box or https://192.168.1.50", style: "flex: 2 1 260px; min-width: 0" });
  const boxToken = el("input", { type: "password", value: box.token, placeholder: "STATUS_TOKEN from the box's .env", autocomplete: "off", style: "flex: 1 1 200px; min-width: 0" });
  const b = s.box || {};
  const services = b.ok && b.data && b.data.services ? Object.entries(b.data.services) : [];

  pane.replaceChildren(
    card("local ai", el("p", { class: "muted" }, "a language model on this computer gives a second opinion on pressure tactics (urgency, fake scarcity, confirm-shaming …) when the built-in patterns already see one. the page's text goes to that model and nowhere else. with Ollama: install it, run ", el("span", { class: "mono" }, "ollama pull " + (ai.model || "llama3.2:3b")), ", and start it with ", el("span", { class: "mono" }, "OLLAMA_ORIGINS=chrome-extension://*,moz-extension://*"), " so it accepts the shield."),
      el("label", { class: "switch" }, aiOn, el("span", {}, "use a local model")),
      el("label", { class: "switch" }, aiCog, el("span", {}, "second opinion on pressure tactics")),
      el("div", { class: "row" }, provider, endpoint, model, el("button", { class: "act", onclick: async () => { await saveAi(); aiOut.textContent = "saved."; } }, "save"),
        el("button", { class: "act primary", onclick: async () => { await saveAi(); aiOut.textContent = "asking the model…"; const r = await send({ type: "local.testAi" }); aiOut.textContent = r.ok ? `works: ${r.provider} · ${r.model} · answered in ${r.ms} ms` : "does not work yet: " + (r.error || "the model's answer was not JSON"); } }, "test")),
      aiOut),
    card("this whole computer", el("p", { class: "muted" }, "the browser tunnel protects only the browser. through the noah helper the shield can also drive WireGuard (a tunnel for every program) and OpenSnitch (an application firewall that can block the shield's bad hosts for every program). the helper must support these; older ones answer \"not available\"."),
      el("table", { class: "list" },
        el("tr", {}, el("td", {}, "noah helper"), el("td", {}, s.host && s.host.present ? tag(true, "installed " + (s.host.version || "")) : tag(false, "not installed"), reason(s.host))),
        el("tr", {}, el("td", {}, "WireGuard"), el("td", {}, wg.available ? tag(true, tunnels.length ? tunnels.map((t) => t.name + (t.up ? " (up)" : "")).join(", ") : "available, no tunnels") : tag(false, "not available"), wg.available ? "" : reason(wg))),
        el("tr", {}, el("td", {}, "OpenSnitch"), el("td", {}, sn.available ? tag(Boolean(sn.running), sn.running ? "running" + (sn.rules !== undefined ? ` · ${sn.rules} rules` : "") : "installed, not running") : tag(false, "not available"), sn.available ? "" : reason(sn)))),
      el("div", { class: "row" }, wgName, el("button", { class: "act primary", disabled: !wg.available || undefined, onclick: wgAct("up") }, "start tunnel"), el("button", { class: "act", disabled: !wg.available || undefined, onclick: wgAct("down") }, "stop tunnel")), wgOut,
      el("div", { class: "actions-row" }, el("button", { class: "act", disabled: !sn.available || undefined, onclick: async () => { snOut.textContent = "sending…"; const r = await send({ type: "local.opensnitch", action: "sync" }); snOut.textContent = r.error || `sent ${r.sent.toLocaleString()} hosts to OpenSnitch as deny rules`; } }, "block the shield's bad hosts for every program")), snOut),
    card("noah box", el("p", { class: "muted" }, "a Raspberry Pi on your network running the noah-box stack (DNS filtering with the shield's lists, your own WireGuard VPN, Tor, CrowdSec and Suricata). it protects every device in the house, phones and TVs too. point the shield at it to see its state; it must answer over https with a certificate this browser trusts."),
      el("div", { class: "row" }, boxAddress, boxToken, el("button", { class: "act primary", onclick: async () => { await change({ noahBox: { address: boxAddress.value.trim(), token: boxToken.value } }); show("local"); } }, "save and check")),
      !b.configured ? empty("no box set.") : b.error ? el("p", {}, tag(false, "unreachable"), " ", b.error) :
        el("table", { class: "list" },
          el("tr", {}, el("td", {}, "box"), el("td", {}, tag(true, "answering"), " ", b.url, b.data.version ? " · " + b.data.version : "")),
          services.map(([name, info]) => el("tr", {}, el("td", {}, name), el("td", {}, tag(Boolean(info && info.up), info && info.up ? "up" : "down"), info && info.detail ? " " + info.detail : ""))),
          b.data.alerts !== undefined ? el("tr", {}, el("td", {}, "intrusion alerts (24 h)"), el("td", { class: "num" }, String(b.data.alerts))) : null,
          b.data.blockedToday !== undefined ? el("tr", {}, el("td", {}, "dns queries blocked today"), el("td", { class: "num" }, String(b.data.blockedToday))) : null))
  );
};

// ---- start --------------------------------------------------------------------------------------------------------------
(async () => {
  try { if (Shield.applyLook && Shield.loadLook) Shield.applyLook(await Shield.loadLook()); } catch {}
  await loadSettings().catch(() => {});
  const fromHash = () => {
    const raw = location.hash.slice(1);
    const cut = raw.indexOf(":");
    const name = cut < 0 ? raw : raw.slice(0, cut);
    const arg = cut < 0 ? undefined : decodeURIComponent(raw.slice(cut + 1));
    show(views[name] ? name : "overview", arg);
  };
  window.addEventListener("hashchange", fromHash);
  fromHash();
  setInterval(() => { if (current === "overview" && !document.hidden) views.overview($("pane-overview")).catch(() => {}); }, 15000);
})();
})();
