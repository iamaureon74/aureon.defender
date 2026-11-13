// Investigations and containment.
//
// A case gathers every detection about one site (or one extension, or one
// file) into a story: what was seen, in order; how bad; what it touched;
// what was done and how to undo it. Response follows nist 800-61: contain,
// then recover. Only confirmed, critical findings with a rule marked `auto`
// are contained without asking; everything else waits for a press.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const CONTAIN_BASE = 8500;   // dynamic rules 8500..8999: one block per contained host
const FEED_BASE = 8000;      // dynamic rules 8000..8499: feed hosts, 1000 per rule
let cases = null;
let ledger = null;
let saveTimer = null;

async function load() {
  if (cases) return;
  cases = {}; ledger = [];
  try {
    const stored = Shield.api && Shield.api.storage ? await Shield.api.storage.local.get(["secCases", "secLedger"]) : {};
    cases = stored.secCases || {};
    ledger = stored.secLedger || [];
  } catch {}
}
function save() {
  if (saveTimer || !Shield.api || !Shield.api.storage) return;
  saveTimer = setTimeout(() => { saveTimer = null; Shield.api.storage.local.set({ secCases: cases, secLedger: ledger.slice(-500) }).catch(() => {}); }, 1000);
}

function subjectOf(detection) {
  const last = detection.evidence[detection.evidence.length - 1];
  if (last.kind.startsWith("ext.")) return "extension:" + (last.data.extensionId || "?");
  if (last.kind === "file.scan") return "file:" + (last.data.sha256 || last.data.name);
  if (last.kind === "identity.exposed") return "identity:" + (last.data.label || "?");
  return "site:" + (last.site || last.host || "browser");
}

function readPath(event, path) {
  let value = event;
  for (const part of path.split(".")) { if (value == null) return undefined; value = value[part]; }
  return value;
}

// "block-host:data.actionHost" → { action: "block-host", target: <value from the evidence> }
sec.resolveAction = function resolveAction(spec, evidence) {
  const [action, path] = spec.split(":");
  if (!path) return { action, target: null };
  let source = evidence[evidence.length - 1];
  let field = path;
  const step = /^@(\d+)\.(.*)$/.exec(path);
  if (step) { source = evidence[Number(step[1])]; field = step[2]; }
  return { action, target: source ? readPath(source, field) : undefined };
};

sec.addDetection = async function addDetection(detection) {
  await load();
  const subject = subjectOf(detection);
  const now = detection.t;
  const rule = detection.rule;
  let item = cases[subject];
  if (!item) {
    item = cases[subject] = { id: subject, subject, opened: now, updated: now, status: "open", severity: rule.severity, detections: [], timeline: [], resources: [], actions: [], tabs: [] };
  }
  item.updated = now;
  if (sec.SEVERITY[rule.severity] > sec.SEVERITY[item.severity]) item.severity = rule.severity;
  if (item.status === "dismissed") item.status = "open";
  let existing = item.detections.find((d) => d.rule === rule.id);
  if (!existing) {
    existing = { rule: rule.id, title: rule.title, severity: rule.severity, attack: rule.attack, tactic: rule.tactic, why: rule.why, falsePositives: rule.falsePositives || "", first: now, last: now, times: 0, evidence: [] };
    item.detections.push(existing);
  }
  existing.last = now;
  existing.times++;
  for (const event of detection.evidence) {
    if (!existing.evidence.includes(event.id)) existing.evidence.push(event.id);
    if (!item.timeline.some((entry) => entry.event === event.id)) item.timeline.push({ t: event.t, event: event.id, kind: event.kind, text: describe(event), rule: rule.id });
    for (const resource of [event.url, event.host, event.data && event.data.actionHost, event.data && event.data.name].filter(Boolean)) if (!item.resources.includes(resource) && item.resources.length < 40) item.resources.push(resource);
    if (event.tab >= 0 && !item.tabs.includes(event.tab)) item.tabs.push(event.tab);
  }
  existing.evidence = existing.evidence.slice(-30);
  item.timeline.sort((a, b) => a.t - b.t);
  item.timeline = item.timeline.slice(-80);
  // suggested actions, deduplicated
  for (const spec of rule.contain || []) {
    const { action, target } = sec.resolveAction(spec, detection.evidence);
    const suggestion = { action, target: target === undefined ? null : target, tab: detection.evidence[detection.evidence.length - 1].tab };
    if (action !== "close-tab" && (suggestion.target === null || suggestion.target === "")) continue;
    if (!item.actions.some((a) => a.action === action && a.target === suggestion.target)) item.actions.push(Object.assign(suggestion, { state: "suggested", auto: Boolean(rule.auto) }));
  }
  save();
  return item;
};

function describe(event) {
  const d = event.data || {};
  switch (event.kind) {
    case "form.submit": return `${d.hasPassword ? "password form" : "form"} on ${event.site} sent to ${d.actionHost}${d.actionScheme === "http" ? " over plain http" : ""}`;
    case "page.scan": return [d.brand && `page names "${d.brand}"`, d.hasPassword && "shows a password field", d.fakeWindow && "draws a fake browser window", d.runInstruction && "tells you to open the run box or a terminal"].filter(Boolean).join(", ") || "page read";
    case "clipboard.write": return `page wrote ${d.commandLike ? "a system command" : "text"} to the clipboard${d.sample ? ": " + d.sample : ""}`;
    case "nav.redirect": return `redirected ${Shield.hostOf(d.from)} → ${Shield.hostOf(d.to)} (${d.crossSiteHops || 0} cross-site hops)`;
    case "download.start": return `download started: ${d.name}${d.reasons ? " (" + d.reasons.join("; ") + ")" : ""}`;
    case "intel.hit": return `${event.url || event.host} is on ${d.source} (${d.category}${d.confirmed ? "" : ", unverified"})`;
    case "ext.change": return `extension "${d.name}" ${d.version ? "v" + d.version + " " : ""}added: ${(d.added || []).join(", ")}`;
    case "ext.install": return `extension "${d.name}" installed (${d.installType})`;
    case "file.scan": return `file ${d.name}: ${(d.findings || []).join("; ") || "no findings"}`;
    case "blocked": return `blocked request to ${event.host}`;
    case "request": return `request to ${event.host}${event.ip ? " (" + event.ip + ")" : ""}`;
    case "page.tabnab": return `background tab changed to "${d.title || "?"}" with a password field`;
    case "shop.scan": return `store signs: ${(d.signals || []).join(", ")}`;
    case "identity.exposed": return `${d.label} found in ${d.breaches} breach${d.breaches === 1 ? "" : "es"}`;
    case "safety": return `shield guard: ${d.kind}${d.detail ? " – " + d.detail : ""}`;
    default: return event.kind;
  }
}
sec.describe = describe;

// ---- containment --------------------------------------------------------------------------

sec.contain = async function contain(caseId, index, options = {}) {
  await load();
  const item = cases[caseId];
  const action = item && item.actions[index];
  if (!action) return { error: "no such action" };
  const api = Shield.api;
  const entry = { at: Date.now(), case: caseId, action: action.action, target: action.target, by: options.auto ? "rule" : "you", undo: null, ok: false };
  try {
    switch (action.action) {
      case "block-host": {
        const host = String(action.target).toLowerCase();
        const rules = await api.declarativeNetRequest.getDynamicRules();
        const used = new Set(rules.map((r) => r.id));
        let id = CONTAIN_BASE;
        while (used.has(id) && id < CONTAIN_BASE + 500) id++;
        await api.declarativeNetRequest.updateDynamicRules({ addRules: [{ id, priority: 20, action: { type: "block" }, condition: { requestDomains: [host] } }] });
        entry.undo = { type: "remove-rule", id };
        entry.ok = true;
        break;
      }
      case "close-tab":
        if (Number.isInteger(action.tab) && action.tab >= 0) await api.tabs.remove(action.tab);
        entry.ok = true;
        break;
      case "hold-download":
        await api.downloads.pause(Number(action.target));
        entry.undo = { type: "resume-download", id: Number(action.target) };
        entry.ok = true;
        break;
      case "delete-download":
        await api.downloads.cancel(Number(action.target)).catch(() => {});
        await api.downloads.removeFile(Number(action.target)).catch(() => {});
        entry.ok = true;
        break;
      case "disable-extension":
        if (!options.confirmed) return { error: "needs your confirmation" };
        await api.management.setEnabled(String(action.target), false);
        entry.undo = { type: "enable-extension", id: String(action.target) };
        entry.ok = true;
        break;
      default:
        return { error: "unknown action" };
    }
  } catch (error) {
    entry.error = String(error.message || error);
  }
  action.state = entry.ok ? "done" : "failed";
  action.at = entry.at;
  action.error = entry.error;
  if (entry.ok && item.actions.every((a) => a.state !== "suggested" || a.action === "close-tab")) item.status = "contained";
  ledger.push(entry);
  save();
  return entry;
};

sec.undo = async function undo(ledgerIndex) {
  await load();
  const entry = ledger[ledgerIndex];
  if (!entry || !entry.undo || entry.undone) return { error: "nothing to undo" };
  const api = Shield.api;
  try {
    if (entry.undo.type === "remove-rule") await api.declarativeNetRequest.updateDynamicRules({ removeRuleIds: [entry.undo.id] });
    if (entry.undo.type === "resume-download") await api.downloads.resume(entry.undo.id);
    if (entry.undo.type === "enable-extension") await api.management.setEnabled(entry.undo.id, true);
    entry.undone = Date.now();
    const item = cases[entry.case];
    if (item) {
      const action = item.actions.find((a) => a.action === entry.action && a.target === entry.target);
      if (action) action.state = "undone";
      item.status = "open";
    }
    save();
    return { ok: true };
  } catch (error) {
    return { error: String(error.message || error) };
  }
};

// Feed hosts become block rules in chunks of 1000 domains.
sec.applyFeedBlocks = async function applyFeedBlocks(hosts, enabled) {
  const dnr = Shield.api.declarativeNetRequest;
  const existing = (await dnr.getDynamicRules()).filter((r) => r.id >= FEED_BASE && r.id < CONTAIN_BASE).map((r) => r.id);
  const addRules = [];
  if (enabled) {
    const list = hosts.filter((host) => !sec.SHARED_HOSTS.has(host)).slice(0, 400000);
    for (let index = 0; index * 1000 < list.length && index < 480; index++) {
      addRules.push({ id: FEED_BASE + index, priority: 15, action: { type: "block" }, condition: { requestDomains: list.slice(index * 1000, (index + 1) * 1000) } });
    }
  }
  await dnr.updateDynamicRules({ removeRuleIds: existing, addRules });
  return addRules.length;
};

sec.setCaseStatus = async function setCaseStatus(caseId, status) {
  await load();
  if (!cases[caseId] || !["open", "dismissed", "contained", "resolved"].includes(status)) return { error: "no such case" };
  cases[caseId].status = status;
  cases[caseId].updated = Date.now();
  save();
  return { ok: true };
};

sec.listCases = async function listCases() {
  await load();
  return Object.values(cases).sort((a, b) => (sec.SEVERITY[b.severity] - sec.SEVERITY[a.severity]) || (b.updated - a.updated));
};
sec.getCase = async function getCase(caseId) { await load(); return cases[caseId] || null; };
sec.ledger = async function readLedger() { await load(); return ledger.slice(); };
sec.clearCases = async function clearCases() { cases = {}; ledger = []; save(); };

// ---- the report: plain text, and a stix 2.1 bundle -----------------------------------------

sec.reportText = function reportText(item, events) {
  const byId = Object.fromEntries((events || []).map((e) => [e.id, e]));
  const lines = [
    `noah shield investigation: ${item.subject}`,
    `severity: ${item.severity} · status: ${item.status} · opened ${new Date(item.opened).toISOString()} · updated ${new Date(item.updated).toISOString()}`,
    "",
    "findings",
  ];
  for (const d of item.detections) {
    lines.push(`- [${d.severity}] ${d.title} (${d.rule}, att&ck ${d.attack}, ${d.times}×)`);
    lines.push(`  why: ${d.why}`);
    if (d.falsePositives) lines.push(`  can be wrong when: ${d.falsePositives}`);
  }
  lines.push("", "timeline");
  for (const entry of item.timeline) lines.push(`- ${new Date(entry.t).toISOString()}  ${entry.text}  [event ${entry.event}${byId[entry.event] ? ", source " + byId[entry.event].source : ""}]`);
  lines.push("", "affected", ...item.resources.map((r) => "- " + r));
  lines.push("", "actions", ...item.actions.map((a) => `- ${a.action}${a.target ? " " + a.target : ""}: ${a.state}${a.error ? " (" + a.error + ")" : ""}`));
  lines.push("", "every finding above comes from a recorded browser event and a written rule; no guesswork or ai is involved.");
  return lines.join("\n");
};

function uuid() {
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

sec.reportStix = function reportStix(item, events) {
  const now = new Date().toISOString();
  const identity = { type: "identity", spec_version: "2.1", id: "identity--" + uuid(), created: now, modified: now, name: "noah shield", identity_class: "system" };
  const objects = [identity];
  const observables = {};
  const observe = (type, value) => {
    const key = type + "|" + value;
    if (!observables[key]) { observables[key] = { type, spec_version: "2.1", id: type + "--" + uuid(), value }; objects.push(observables[key]); }
    return observables[key].id;
  };
  for (const event of events || []) {
    if (event.host) observe("domain-name", event.host);
    if (event.url) observe("url", event.url);
    if (event.ip) objects.push({ type: "ipv4-addr", spec_version: "2.1", id: "ipv4-addr--" + uuid(), value: event.ip });
  }
  for (const d of item.detections) {
    const indicator = { type: "indicator", spec_version: "2.1", id: "indicator--" + uuid(), created: now, modified: now, created_by_ref: identity.id, name: d.title, description: d.why, pattern_type: "noah-shield-rule", pattern: d.rule, valid_from: new Date(d.first).toISOString(), external_references: [{ source_name: "mitre-attack", external_id: d.attack }] };
    objects.push(indicator);
    const refs = (events || []).filter((e) => d.evidence.includes(e.id)).map((e) => e.url ? observables["url|" + e.url].id : e.host ? observables["domain-name|" + e.host].id : null).filter(Boolean);
    objects.push({ type: "sighting", spec_version: "2.1", id: "sighting--" + uuid(), created: now, modified: now, created_by_ref: identity.id, sighting_of_ref: indicator.id, first_seen: new Date(d.first).toISOString(), last_seen: new Date(d.last).toISOString(), count: d.times, observed_data_refs: [], where_sighted_refs: [identity.id], description: refs.length ? "observables: " + refs.join(", ") : undefined });
  }
  return { type: "bundle", id: "bundle--" + uuid(), objects };
};

sec._resetCasesForTests = function resetCasesForTests() { cases = {}; ledger = []; };
})();
