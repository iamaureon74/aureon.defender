// Security events: what the sensors saw, in one shape.
//
// Every finding in the security center points back to these. An event is a
// plain observation, never a conclusion:
//   { id, t, kind, tab, site, host, url, ip, data, source }
// kinds in use:
//   request        a request finished (host, ip, type, third party or not)
//   blocked        a request the rule lists stopped
//   nav.commit     a page opened in a tab
//   nav.redirect   a top-level hop from one address to another
//   download.start a download began (name, url, mime, risky reasons)
//   form.submit    a form was sent (password field? where to? cross-site?)
//   clipboard.write a page put text on the clipboard (command-like?)
//   page.scan      what the page sensor read off a page (brand words, fake
//                  window, run-dialog instructions, login form)
//   page.tabnab    a page you had left changed itself while hidden
//   ext.install / ext.change / ext.remove   extensions coming and changing
//   file.scan      the result of a static file analysis
//   intel.hit      something seen matched a threat indicator
//   identity.exposed  a watched identifier showed up in a breach
//   shop.scan      what a store page shows (payment methods, contact, prices)
//   safety         an existing shield guard fired (lookalike, keylog, …)
// Kept on this device only: at most 4000 events and seven days.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const MAX_EVENTS = 4000;
const KEEP_MS = 7 * 24 * 3600 * 1000;
let events = null;
let nextId = 1;
let saveTimer = null;
const listeners = [];

async function load() {
  if (events) return events;
  events = [];
  try {
    const stored = Shield.api && Shield.api.storage ? await Shield.api.storage.local.get("secEvents") : {};
    const list = Array.isArray(stored.secEvents) ? stored.secEvents : [];
    const since = Date.now() - KEEP_MS;
    events = list.filter((event) => event && event.t >= since);
    nextId = events.reduce((max, event) => Math.max(max, event.id || 0), 0) + 1;
  } catch {
    events = [];
  }
  return events;
}
sec.loadEvents = load;

function save() {
  if (saveTimer || !Shield.api || !Shield.api.storage) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    Shield.api.storage.local.set({ secEvents: events.slice(-MAX_EVENTS) }).catch(() => {});
  }, 2000);
}

// Fields are copied and trimmed: an event never carries page text, form
// values or cookies, only the facts a rule needs.
function clean(value, depth = 0) {
  if (value == null) return value;
  if (typeof value === "string") return value.slice(0, 500);
  if (typeof value === "number" || typeof value === "boolean") return value;
  if (depth > 3) return undefined;
  if (Array.isArray(value)) return value.slice(0, 40).map((item) => clean(item, depth + 1));
  if (typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value).slice(0, 40)) out[key] = clean(item, depth + 1);
    return out;
  }
  return undefined;
}

sec.record = async function record(kind, fields = {}) {
  await load();
  const host = fields.host || (fields.url ? Shield.hostOf(fields.url) : "");
  const event = {
    id: nextId++,
    t: fields.t || Date.now(),
    kind: String(kind),
    tab: Number.isInteger(fields.tab) ? fields.tab : -1,
    host,
    site: fields.site || (host ? Shield.siteOf(host) : ""),
    url: fields.url ? String(fields.url).slice(0, 500) : "",
    ip: fields.ip ? String(fields.ip).slice(0, 64) : "",
    source: fields.source || "browser",
    data: clean(fields.data || {}),
  };
  events.push(event);
  if (events.length > MAX_EVENTS + 200) events.splice(0, events.length - MAX_EVENTS);
  save();
  for (const listener of listeners) {
    try { await listener(event); } catch (error) { console.warn("shield: security listener", error); }
  }
  return event;
};

sec.onEvent = function onEvent(listener) { listeners.push(listener); };

sec.query = async function query(filter = {}) {
  await load();
  const since = filter.since || 0;
  return events.filter((event) =>
    event.t >= since &&
    (!filter.kind || (Array.isArray(filter.kind) ? filter.kind.includes(event.kind) : event.kind === filter.kind)) &&
    (filter.tab === undefined || event.tab === filter.tab) &&
    (!filter.site || event.site === filter.site) &&
    (!filter.host || event.host === filter.host) &&
    (!filter.ids || filter.ids.includes(event.id)));
};

sec.clearEvents = async function clearEvents() {
  events = [];
  if (Shield.api && Shield.api.storage) await Shield.api.storage.local.remove("secEvents");
};

sec._resetForTests = function resetForTests() { events = []; nextId = 1; listeners.length = 0; };
})();
