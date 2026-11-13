// The rule engine: deterministic detection, written as data.
//
// Modelled on sigma (detections as plain, shareable records) and on siem
// correlation (a then b within n seconds). No scoring model, no learning: a
// rule fires when its written conditions hold, and the detection lists the
// exact events that made them hold.
//
// A rule has one of three shapes:
//   match:     one event that meets every condition
//   sequence:  events meeting step 1, then step 2 … within `within` ms,
//              grouped by tab, site or the whole browser
//   threshold: `count` events meeting the conditions within `within` ms
// Conditions are [path, operator, value]. Paths read the event
// ("kind", "host", "data.hasPassword"). A value written "@0.site" means
// "the same field of the event that matched step 0", which is how a rule
// says "a different site than the page you were on".
// Operators: eq ne in nin gt gte lt lte re exists true false.
//
// To add a future pattern: write one rule here and one test for it.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

sec.SEVERITY = { info: 0, low: 1, medium: 2, high: 3, critical: 4 };

sec.RULES = [
  // ---- phishing (att&ck t1566, credential capture t1056) --------------------------------
  { id: "NS-PH-001", title: "password sent to a different site than the page", severity: "high", attack: "T1566.002", tactic: "credential access",
    why: "the login form on this page sends what you type to another site; real logins post to their own site or their sign-in provider",
    falsePositives: "single sign-on providers not yet on the list; payment pages that post to their processor",
    match: [["kind", "eq", "form.submit"], ["data.hasPassword", "true"], ["data.crossSite", "true"], ["data.knownSso", "false"]],
    contain: ["block-host:data.actionHost"] },
  { id: "NS-PH-002", title: "page claims a brand it does not belong to and asks for a password", severity: "high", attack: "T1566", tactic: "initial access",
    why: "the page names a brand in its title or headings and shows a password field, but its address is not one of that brand's domains",
    falsePositives: "review sites and help articles that mention a brand and have their own login",
    match: [["kind", "eq", "page.scan"], ["data.brand", "exists"], ["data.brandDomain", "false"], ["data.hasPassword", "true"]],
    contain: ["close-tab"] },
  { id: "NS-PH-003", title: "address listed as phishing by a threat feed", severity: "critical", attack: "T1566.002", tactic: "initial access",
    why: "the exact address is on a phishing list downloaded to this device",
    match: [["kind", "eq", "intel.hit"], ["data.category", "eq", "phishing"], ["data.confirmed", "true"]],
    contain: ["block-host:host", "close-tab"], auto: true },
  { id: "NS-PH-004", title: "lookalike of a known brand's domain", severity: "high", attack: "T1583.001", tactic: "resource development",
    why: "the domain is a near-copy of a brand's real domain (swapped letters, extra words, a different ending)",
    match: [["kind", "eq", "safety"], ["data.kind", "eq", "phishing"]] },
  { id: "NS-PH-005", title: "fake sign-in window drawn inside the page", severity: "high", attack: "T1056.003", tactic: "credential access",
    why: "the page draws something that looks like a browser window with its own address bar around a password field (browser-in-the-browser)",
    match: [["kind", "eq", "page.scan"], ["data.fakeWindow", "true"], ["data.hasPassword", "true"]],
    contain: ["close-tab"] },
  { id: "NS-PH-006", title: "a page you left turned itself into a login page", severity: "medium", attack: "T1566", tactic: "initial access",
    why: "while the tab was in the background it changed its title or address and now shows a password field (tab-nabbing)",
    match: [["kind", "eq", "page.tabnab"]] },

  // ---- malware delivery (t1204 user execution, t1189 drive-by) ---------------------------
  { id: "NS-MW-001", title: "contact with a host listed for spreading malware", severity: "critical", attack: "T1189", tactic: "initial access",
    why: "this host is on a malware-distribution list downloaded to this device",
    match: [["kind", "eq", "intel.hit"], ["data.category", "eq", "malware"], ["data.confirmed", "true"]],
    contain: ["block-host:host"], auto: true },
  { id: "NS-BH-001", title: "page put a command on your clipboard and asks you to run it", severity: "critical", attack: "T1204.004", tactic: "execution",
    why: "a page copied a system command for you, then told you to open the run box or a terminal and paste it (fake captcha / clickfix)",
    falsePositives: "developer documentation with copy buttons for terminal commands",
    sequence: { by: "tab", within: 180000, steps: [
      [["kind", "eq", "clipboard.write"], ["data.commandLike", "true"]],
      [["kind", "eq", "page.scan"], ["data.runInstruction", "true"]] ] },
    orMatch: [["kind", "eq", "clipboard.write"], ["data.commandLike", "true"], ["data.runInstruction", "true"]],
    contain: ["close-tab"] },
  { id: "NS-BH-002", title: "redirect chain across sites ending in a risky download", severity: "high", attack: "T1189", tactic: "initial access",
    why: "you were bounced through several sites and a program or archive started downloading seconds later (malvertising pattern)",
    sequence: { by: "global", within: 30000, steps: [
      [["kind", "eq", "nav.redirect"], ["data.crossSiteHops", "gte", 2]],
      [["kind", "eq", "download.start"], ["data.risky", "true"]] ] },
    contain: ["hold-download:@1.data.downloadId"] },
  { id: "NS-BH-003", title: "risky download from a site you opened moments ago", severity: "medium", attack: "T1204.002", tactic: "execution",
    why: "a program, script or archive began downloading within a minute of first opening this site",
    match: [["kind", "eq", "download.start"], ["data.risky", "true"], ["data.siteAgeMs", "lt", 60000]] },

  // ---- browser extensions (t1176) --------------------------------------------------------
  { id: "NS-EX-001", title: "an extension gained new permissions", severity: "high", attack: "T1176", tactic: "persistence",
    why: "an installed extension now asks for more than it did before; takeovers of popular extensions look exactly like this",
    match: [["kind", "eq", "ext.change"], ["data.addedCount", "gt", 0]],
    contain: ["disable-extension:data.extensionId"] },
  { id: "NS-EX-002", title: "extension installed from outside a store", severity: "medium", attack: "T1176", tactic: "persistence",
    why: "this extension was sideloaded or loaded in developer mode; store copies at least pass a review",
    match: [["kind", "eq", "ext.install"], ["data.installType", "in", ["sideload", "development"]], ["data.self", "false"]] },
  { id: "NS-EX-003", title: "extension can now read every site", severity: "critical", attack: "T1176", tactic: "collection",
    why: "an update added access to every website, or to cookies, debugging or all requests",
    match: [["kind", "eq", "ext.change"], ["data.addedPowerful", "true"]],
    contain: ["disable-extension:data.extensionId"] },

  // ---- network (t1040 sniffing, t1046 discovery) ----------------------------------------
  { id: "NS-NT-001", title: "password sent without encryption", severity: "high", attack: "T1040", tactic: "credential access",
    why: "the form posts over plain http: anyone on this network can read the password",
    match: [["kind", "eq", "form.submit"], ["data.hasPassword", "true"], ["data.actionScheme", "eq", "http"]] },
  { id: "NS-NT-002", title: "page scanning your local network", severity: "medium", attack: "T1046", tactic: "discovery",
    why: "a website tried to reach five or more addresses inside your home network within seconds",
    threshold: { by: "tab", within: 15000, count: 5, where: [["kind", "eq", "blocked"], ["data.lan", "true"]] } },
  { id: "NS-NT-003", title: "page contacted many new third parties at once", severity: "low", attack: "T1071.001", tactic: "command and control",
    why: "more than 40 different outside hosts in ten seconds from one page; heavy ad pages do this, so does injected code",
    threshold: { by: "tab", within: 10000, count: 40, distinct: "host", where: [["kind", "eq", "request"], ["data.thirdParty", "true"]] } },

  // ---- files ------------------------------------------------------------------------------
  { id: "NS-FS-001", title: "downloaded file matches known malware", severity: "critical", attack: "T1204.002", tactic: "execution",
    why: "the file's sha-256 is a catalogued malware sample",
    match: [["kind", "eq", "file.scan"], ["data.knownMalware", "true"]],
    contain: ["delete-download:data.downloadId"], auto: true },
  { id: "NS-FS-002", title: "file built to hide what it is", severity: "high", attack: "T1036.008", tactic: "defense evasion",
    why: "the file's real type does not match its name (double extension, a program dressed as a document)",
    match: [["kind", "eq", "file.scan"], ["data.disguised", "true"]],
    contain: ["delete-download:data.downloadId"] },
  { id: "NS-FS-003", title: "document carries active content", severity: "medium", attack: "T1204.002", tactic: "execution",
    why: "macros, embedded javascript or auto-run actions inside an office file or pdf",
    match: [["kind", "eq", "file.scan"], ["data.activeContent", "true"]] },
  { id: "NS-FS-004", title: "file matches a yara malware rule", severity: "high", attack: "T1204.002", tactic: "execution",
    why: "a yara rule rated high or critical (bundled or your own) matched the file's bytes: a download cradle, credential stealer, implant, miner or ransom note",
    match: [["kind", "eq", "file.scan"], ["data.yaraMatch", "true"]],
    contain: ["delete-download:data.downloadId"] },

  // ---- scams, identity ---------------------------------------------------------------------
  { id: "NS-SC-001", title: "store shows several scam signs together", severity: "high", attack: "T1583.001", tactic: "resource development",
    why: "two or more of: domain registered recently, payment only by crypto, gift cards or wire, prices far below other stores, no contact or returns page",
    match: [["kind", "eq", "shop.scan"], ["data.signalCount", "gte", 2]] },
  { id: "NS-ID-001", title: "a watched identity appeared in a breach", severity: "medium", attack: "T1589", tactic: "reconnaissance",
    why: "an email you asked the shield to watch is listed in a known breach",
    match: [["kind", "eq", "identity.exposed"]] },
];

// ---- matching -----------------------------------------------------------------------------

function read(event, path) {
  let value = event;
  for (const part of String(path).split(".")) {
    if (value == null) return undefined;
    value = value[part];
  }
  return value;
}

function resolve(value, steps) {
  if (typeof value === "string" && /^@\d+\./.test(value)) {
    const index = Number(value.slice(1, value.indexOf(".")));
    return steps && steps[index] ? read(steps[index], value.slice(value.indexOf(".") + 1)) : undefined;
  }
  return value;
}

function test(event, condition, steps) {
  const [path, operator] = condition;
  const actual = read(event, path);
  const expected = resolve(condition[2], steps);
  switch (operator) {
    case "eq": return actual === expected;
    case "ne": return actual !== expected;
    case "in": return Array.isArray(expected) && expected.includes(actual);
    case "nin": return Array.isArray(expected) && !expected.includes(actual);
    case "gt": return typeof actual === "number" && actual > expected;
    case "gte": return typeof actual === "number" && actual >= expected;
    case "lt": return typeof actual === "number" && actual < expected;
    case "lte": return typeof actual === "number" && actual <= expected;
    case "re": try { return new RegExp(expected, "i").test(String(actual || "")); } catch { return false; }
    case "exists": return actual !== undefined && actual !== null && actual !== "";
    case "true": return actual === true;
    case "false": return actual !== true;
    default: return false;
  }
}

sec.matches = function matches(event, conditions, steps) {
  return (conditions || []).every((condition) => test(event, condition, steps));
};

function groupKey(by, event) {
  if (by === "global") return "*";
  if (by === "site") return event.site || "?";
  return String(event.tab);
}

// The engine keeps only what open sequences and thresholds need.
sec.createEngine = function createEngine(rules = sec.RULES) {
  const partial = new Map();   // rule|key -> [{ steps:[events], started }]
  const windows = new Map();   // rule|key -> [events]
  const recent = new Map();    // rule|key -> last detection time, to merge repeats

  function detection(rule, evidence, key) {
    const stamp = rule.id + "|" + key;
    const last = recent.get(stamp);
    const now = evidence[evidence.length - 1].t;
    const merged = last && now - last < 60000;
    recent.set(stamp, now);
    return { rule, evidence, key, merged, t: now };
  }

  return {
    process(event) {
      const found = [];
      for (const rule of rules) {
        if (rule.match && sec.matches(event, rule.match)) found.push(detection(rule, [event], groupKey("tab", event)));
        if (rule.orMatch && sec.matches(event, rule.orMatch)) found.push(detection(rule, [event], groupKey("tab", event)));
        if (rule.sequence) {
          const { by, within, steps } = rule.sequence;
          const key = rule.id + "|" + groupKey(by, event);
          const open = (partial.get(key) || []).filter((item) => event.t - item.started <= within);
          const next = [];
          for (const item of open) {
            const want = steps[item.steps.length];
            if (want && sec.matches(event, want, item.steps)) {
              const steps2 = item.steps.concat(event);
              if (steps2.length === steps.length) found.push(detection(rule, steps2, groupKey(by, event)));
              else next.push({ steps: steps2, started: item.started });
            } else next.push(item);
          }
          if (sec.matches(event, steps[0])) {
            if (steps.length === 1) found.push(detection(rule, [event], groupKey(by, event)));
            else next.push({ steps: [event], started: event.t });
          }
          partial.set(key, next.slice(-5));
        }
        if (rule.threshold) {
          const { by, within, count, where, distinct } = rule.threshold;
          if (!sec.matches(event, where)) continue;
          const key = rule.id + "|" + groupKey(by, event);
          const list = (windows.get(key) || []).filter((item) => event.t - item.t <= within);
          list.push(event);
          windows.set(key, list);
          const size = distinct ? new Set(list.map((item) => read(item, distinct))).size : list.length;
          if (size >= count) {
            found.push(detection(rule, list.slice(-count), groupKey(by, event)));
            windows.set(key, []);
          }
        }
      }
      return found;
    },
  };
};
})();
