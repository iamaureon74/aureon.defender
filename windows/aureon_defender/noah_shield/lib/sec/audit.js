// Passive site security audit.
//
// Reads what the browser already receives for a site — its response headers,
// cookies, and page DOM — and grades its security posture against published
// standards: the OWASP Secure Headers Project, the MITRE CWE weakness
// catalogue, and Mozilla's HTTP Observatory scoring model. Nothing is
// attacked, probed, or harvested; every finding is a configuration weakness
// the site owner can fix, with the fix stated.
//
// Each check is data: id, title, the CWE and OWASP ids it maps to, a severity,
// an Observatory-compatible score modifier, and the remediation. New checks —
// and new branches of existing ones (per cookie, per missing header, per
// insecure form) — are generated from these, so the catalogue extends without
// new code paths.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

// Observatory maps a 0..100+ score to a letter grade.
sec.grade = function grade(score) {
  const table = [[100, "A+"], [90, "A"], [85, "A-"], [80, "B+"], [70, "B"], [65, "B-"], [60, "C+"], [50, "C"], [45, "C-"], [40, "D+"], [30, "D"], [25, "D-"], [0, "F"]];
  for (const [min, letter] of table) if (score >= min) return letter;
  return "F";
};

function headerGet(headers, name) {
  if (!headers) return null;
  const lower = name.toLowerCase();
  for (const key of Object.keys(headers)) if (key.toLowerCase() === lower) return headers[key];
  return null;
}

// ---- header + cookie checks (run against the main response) --------------------------------
// context: { https, url, host }
sec.auditHeaders = function auditHeaders(headers, context = {}) {
  const https = context.https !== false;
  const findings = [];
  let score = 100;
  const add = (f) => { findings.push(f); score += f.scoreModifier || 0; };
  const H = (n) => headerGet(headers, n);

  // --- Content-Security-Policy (CWE-693 / A05) ---
  const csp = H("content-security-policy");
  if (!csp) {
    add({ id: "csp-missing", title: "No Content-Security-Policy", severity: "high", cwe: "CWE-693", owasp: "A05:2021", scoreModifier: -25,
      why: "Without a CSP the browser has no policy to stop injected scripts, so a single XSS flaw runs with full reach.",
      fix: "Add a Content-Security-Policy header. Start from default-src 'self' and move inline scripts to nonces." });
  } else {
    const lc = csp.toLowerCase();
    if (/'unsafe-inline'/.test(lc) && /script-src|default-src/.test(lc)) add({ id: "csp-unsafe-inline", title: "CSP allows 'unsafe-inline' scripts", severity: "medium", cwe: "CWE-79", owasp: "A03:2021", scoreModifier: -20, why: "'unsafe-inline' lets injected inline scripts run, which is most of what a CSP exists to stop.", fix: "Remove 'unsafe-inline'; use per-response nonces or hashes with 'strict-dynamic'." });
    else if (/'unsafe-eval'/.test(lc)) add({ id: "csp-unsafe-eval", title: "CSP allows 'unsafe-eval'", severity: "low", cwe: "CWE-95", owasp: "A03:2021", scoreModifier: -10, why: "'unsafe-eval' permits eval() and similar, widening the surface for script injection.", fix: "Remove 'unsafe-eval' and the code paths that need it." });
    else if (https && /(^|[^.])\bhttp:\/\//.test(lc)) add({ id: "csp-insecure-scheme", title: "CSP allows resources over http://", severity: "medium", cwe: "CWE-319", owasp: "A02:2021", scoreModifier: -20, why: "A secure page that permits http:// resources can be downgraded by a network attacker.", fix: "Use https:// sources only, or add upgrade-insecure-requests." });
    else add({ id: "csp-ok", title: "CSP implemented without unsafe directives", severity: "info", pass: true, scoreModifier: 5, fix: "" });
  }

  // --- HSTS (CWE-319 / A02) ---
  const hsts = H("strict-transport-security");
  if (!https) add({ id: "hsts-na", title: "Site served over plain HTTP", severity: "info", pass: false, scoreModifier: 0, why: "HSTS and most header protections only apply over HTTPS.", fix: "Serve the site over HTTPS." });
  else if (!hsts) add({ id: "hsts-missing", title: "No HTTP Strict-Transport-Security", severity: "high", cwe: "CWE-319", owasp: "A02:2021", scoreModifier: -20, why: "Without HSTS the first visit (or a stripped link) can be forced onto http and intercepted.", fix: "Add Strict-Transport-Security: max-age=31536000; includeSubDomains; preload." });
  else {
    const max = Number((/max-age=(\d+)/.exec(hsts) || [])[1] || 0);
    if (max < 15768000) add({ id: "hsts-short", title: "HSTS max-age under six months", severity: "low", cwe: "CWE-319", owasp: "A02:2021", scoreModifier: -10, why: "A short max-age leaves gaps where the site can be downgraded.", fix: "Raise max-age to at least 15768000 (6 months), ideally 31536000." });
    else { add({ id: "hsts-ok", title: "HSTS present", severity: "info", pass: true, scoreModifier: 0, fix: "" }); if (!/includesubdomains/i.test(hsts)) add({ id: "hsts-no-subdomains", title: "HSTS without includeSubDomains", severity: "low", cwe: "CWE-319", owasp: "A02:2021", scoreModifier: 0, why: "Subdomains are not covered, so an http subdomain can still be intercepted.", fix: "Add includeSubDomains (after confirming every subdomain supports HTTPS)." }); }
  }

  // --- X-Content-Type-Options (CWE-434/16) ---
  const xcto = H("x-content-type-options");
  if (!xcto || !/nosniff/i.test(xcto)) add({ id: "xcto-missing", title: "No X-Content-Type-Options: nosniff", severity: "low", cwe: "CWE-16", owasp: "A05:2021", scoreModifier: -5, why: "Without nosniff the browser may run a file as a script based on its contents, not its type.", fix: "Add X-Content-Type-Options: nosniff to every response." });
  else add({ id: "xcto-ok", title: "X-Content-Type-Options: nosniff", severity: "info", pass: true, scoreModifier: 0, fix: "" });

  // --- clickjacking: X-Frame-Options / CSP frame-ancestors (CWE-1021 / A05) ---
  const xfo = H("x-frame-options");
  const frameAncestors = csp && /frame-ancestors/i.test(csp);
  if (!xfo && !frameAncestors) add({ id: "clickjacking", title: "No clickjacking protection", severity: "medium", cwe: "CWE-1021", owasp: "A05:2021", scoreModifier: -20, why: "The page can be framed by any site, which enables clickjacking of its buttons and forms.", fix: "Add Content-Security-Policy: frame-ancestors 'self' (and X-Frame-Options: SAMEORIGIN for old browsers)." });
  else add({ id: "clickjacking-ok", title: "Clickjacking protection present", severity: "info", pass: true, scoreModifier: 0, fix: "" });

  // --- Referrer-Policy ---
  const ref = H("referrer-policy");
  if (!ref) add({ id: "referrer-missing", title: "No Referrer-Policy", severity: "low", cwe: "CWE-200", owasp: "A01:2021", scoreModifier: -5, why: "Full URLs (which can carry tokens) may leak to other sites in the Referer header.", fix: "Add Referrer-Policy: strict-origin-when-cross-origin." });
  else if (/unsafe-url/i.test(ref)) add({ id: "referrer-unsafe", title: "Referrer-Policy: unsafe-url", severity: "low", cwe: "CWE-200", owasp: "A01:2021", scoreModifier: -5, why: "unsafe-url sends the full URL to every destination, including over http.", fix: "Use strict-origin-when-cross-origin instead." });
  else add({ id: "referrer-ok", title: "Referrer-Policy set", severity: "info", pass: true, scoreModifier: 0, fix: "" });

  // --- Permissions-Policy ---
  if (!H("permissions-policy") && !H("feature-policy")) add({ id: "permissions-missing", title: "No Permissions-Policy", severity: "info", cwe: "CWE-16", owasp: "A05:2021", scoreModifier: 0, why: "Powerful features (camera, microphone, geolocation) are not restricted at the header level.", fix: "Add Permissions-Policy limiting features you do not use, e.g. camera=(), microphone=(), geolocation=()." });

  // --- cross-origin isolation trio (advisory) ---
  for (const [name, id, label] of [["cross-origin-opener-policy", "coop", "COOP"], ["cross-origin-resource-policy", "corp", "CORP"]]) {
    if (!H(name)) add({ id: id + "-missing", title: "No " + label, severity: "info", cwe: "CWE-16", owasp: "A05:2021", scoreModifier: 0, why: "Cross-origin isolation header " + label + " is not set; recommended for sites handling sensitive data.", fix: "Add " + name + ": same-origin where compatible." });
  }

  // --- CORS wildcard with credentials (CWE-942) ---
  const acao = H("access-control-allow-origin");
  const acac = H("access-control-allow-credentials");
  if (acao === "*" && acac && /true/i.test(acac)) add({ id: "cors-wildcard-creds", title: "CORS allows any origin with credentials", severity: "high", cwe: "CWE-942", owasp: "A05:2021", scoreModifier: -25, why: "Any website can read this site's authenticated responses — a serious cross-origin leak.", fix: "Never combine Access-Control-Allow-Origin: * with Allow-Credentials: true; echo a specific allowed origin instead." });
  else if (acao === "*") add({ id: "cors-wildcard", title: "CORS allows any origin", severity: "info", cwe: "CWE-942", owasp: "A05:2021", scoreModifier: 0, why: "Any site can read this response. Fine for public data, risky for anything user-specific.", fix: "Restrict Access-Control-Allow-Origin to the origins that need it." });

  // --- information disclosure: server / x-powered-by versions (CWE-200) ---
  for (const [name, id] of [["server", "server"], ["x-powered-by", "powered-by"], ["x-aspnet-version", "aspnet"], ["x-aspnetmvc-version", "aspnetmvc"]]) {
    const v = H(name);
    if (v && /\d/.test(v)) add({ id: "disclose-" + id, title: "Reveals software version in " + name, severity: "low", cwe: "CWE-200", owasp: "A05:2021", scoreModifier: 0, why: "A version string (" + String(v).slice(0, 40) + ") tells an attacker exactly which known flaws to try.", fix: "Remove or blank the " + name + " header." });
  }

  // --- cookies: one branch per cookie (CWE-614/1004/1275) ---
  // Prefer cookies read from the browser's cookie store (context.cookies):
  // fetch() hides Set-Cookie, and the store carries the real flags.
  const cookies = Array.isArray(context.cookies) && context.cookies.length
    ? context.cookies.map((c) => ({ name: c.name, secure: !!c.secure, httpOnly: !!c.httpOnly, sameSite: normalizeSameSite(c.sameSite) }))
    : parseSetCookies(headers);
  let cookiePenalty = 0;
  for (const c of cookies) {
    const problems = [];
    if (!c.secure && https) problems.push("no Secure flag");
    if (isSession(c.name) && !c.httpOnly) problems.push("session cookie without HttpOnly");
    if (!c.sameSite) problems.push("no SameSite");
    else if (!/^(strict|lax)$/i.test(c.sameSite)) problems.push("SameSite=" + c.sameSite + " (invalid)");
    if (problems.length) add({ id: "cookie-" + c.name.toLowerCase().replace(/[^a-z0-9]/g, ""), title: 'Cookie "' + c.name + '": ' + problems.join(", "), severity: !c.secure && https ? "medium" : "low", cwe: "CWE-614", owasp: "A05:2021", scoreModifier: 0, why: "A cookie missing Secure can leak over http; without HttpOnly it is readable by scripts; without SameSite it is sent on cross-site requests (CSRF).", fix: "Set " + c.name + " with Secure; HttpOnly (for session cookies); SameSite=Lax or Strict." });
  }
  if (cookies.length && cookies.some((c) => !c.secure && https)) cookiePenalty = -20;
  else if (cookies.length && cookies.some((c) => isSession(c.name) && !c.httpOnly)) cookiePenalty = -10;
  score += cookiePenalty;

  // bonus only applies when the base is already strong (Observatory rule)
  if (score < 90) for (const f of findings) if (f.pass && f.scoreModifier > 0) score -= f.scoreModifier;

  score = Math.max(0, Math.min(100, score));
  return { score, grade: sec.grade(score), https, findings, cookies: cookies.length };
};

function parseSetCookies(headers) {
  const out = [];
  if (!headers) return out;
  let raw = [];
  for (const key of Object.keys(headers)) if (key.toLowerCase() === "set-cookie") {
    const v = headers[key];
    raw = raw.concat(Array.isArray(v) ? v : String(v).split(/\n/));
  }
  for (const line of raw) {
    if (!line) continue;
    const parts = line.split(";").map((p) => p.trim());
    const name = (parts[0].split("=")[0] || "").trim();
    if (!name) continue;
    const flags = parts.slice(1).map((p) => p.toLowerCase());
    out.push({ name, secure: flags.includes("secure"), httpOnly: flags.includes("httponly"), sameSite: (parts.slice(1).find((p) => /^samesite=/i.test(p)) || "").split("=")[1] || "" });
  }
  return out;
}
function isSession(name) { return /sess|sid|auth|token|login|jwt|csrf|xsrf|\.asp|phpsessid|jsessionid/i.test(name); }
// Browser cookie stores report sameSite as no_restriction/lax/strict/unspecified.
function normalizeSameSite(v) {
  const s = String(v || "").toLowerCase();
  if (s === "strict" || s === "lax") return s;
  if (s === "no_restriction" || s === "none") return "None";
  if (s === "" || s === "unspecified") return "";
  return v;
}

// ---- page-level checks (from DOM facts collected in the page) -------------------------------
// facts: { https, mixedContent:[], externalScripts:[{src,integrity}], forms:[{action,https,crossSite,hasPassword}], metaCsp, inlineScripts, autocompleteOff }
sec.auditPage = function auditPage(facts = {}) {
  const findings = [];
  const add = (f) => findings.push(f);
  if (facts.https && (facts.mixedContent || []).length) add({ id: "mixed-content", title: (facts.mixedContent.length) + " resource(s) loaded over http on an https page", severity: "medium", cwe: "CWE-319", owasp: "A02:2021", why: "Mixed content can be read or altered by a network attacker, undermining the page's HTTPS.", fix: "Load every script, style, image and frame over https.", detail: facts.mixedContent.slice(0, 8) });
  for (const form of facts.forms || []) {
    if (form.hasPassword && !form.https) add({ id: "password-http", title: "Password form submits over http", severity: "critical", cwe: "CWE-319", owasp: "A02:2021", why: "Anyone on the network can read the password as it is sent.", fix: "Post the form to an https:// endpoint." });
    else if (form.hasPassword && form.crossSite) add({ id: "password-crosssite", title: "Password form posts to another site", severity: "high", cwe: "CWE-319", owasp: "A07:2021", why: "Credentials leave for a different domain than the page — the pattern of a phishing or hijacked form.", fix: "Confirm the form action is the site's own sign-in endpoint." });
  }
  const noSri = (facts.externalScripts || []).filter((s) => s.src && !s.integrity && /^https?:\/\//.test(s.src));
  if (noSri.length) add({ id: "no-sri", title: noSri.length + " third-party script(s) without Subresource Integrity", severity: "low", cwe: "CWE-353", owasp: "A08:2021", why: "If the third-party host is compromised, its script runs here unchecked.", fix: "Add an integrity=\"sha384-…\" attribute (and crossorigin) to external <script> tags.", detail: noSri.slice(0, 6).map((s) => s.src) });
  return { findings };
};

// Untrusted-deserialization exposure (CWE-502), observable from the browser.
// Derived from the deserialization roots in the archive pattern set (object-entry
// boundary, type confusion, class loading) — but only the parts a passive
// extension can actually see: serialized objects carried in cookies, url
// parameters, and page storage. Each signature is specific enough not to fire on
// ordinary text. Nothing is executed; values are classified, never stored or sent.
sec.SERIAL_SIGS = [
  { kind: "node-serialize", severity: "high", test: (s) => s.includes("_$$ND_FUNC$$_"), note: "node-serialize function marker — a known remote-code-execution sink if the server deserializes it" },
  { kind: "java", severity: "medium", test: (s) => s.startsWith("rO0AB") || s.startsWith("\xac\xed\x00\x05"), note: "Java serialized object (aced0005) — object-injection risk if deserialized server-side" },
  { kind: "php-object", severity: "medium", test: (s) => /(^|;|&|=)O:\d+:"/.test(s), note: "PHP serialized object (O:) — PHP object-injection risk if unserialized" },
  { kind: "python-pickle", severity: "medium", test: (s) => s.startsWith("gASV") || s.startsWith("gAJ") || s.startsWith("gAN"), note: "Python pickle stream — arbitrary code on load if unpickled" },
  { kind: "dotnet-viewstate", severity: "low", test: (s) => s.startsWith("/wEP") || s.startsWith("/wEW"), note: ".NET ViewState — check it is MAC-protected and encrypted (CWE-502 if not)" },
];
sec.detectSerialized = function detectSerialized(value) {
  const s = String(value || "");
  if (s.length < 5) return null;
  for (const sig of sec.SERIAL_SIGS) { try { if (sig.test(s)) return sig; } catch {} } return null;
};
// inputs: { cookies:[{name,value}], url, serialStorage:[{area,key,kind}], viewstate:{present,protected} }
sec.auditDeserialization = function auditDeserialization(input = {}) {
  const findings = [];
  const seen = new Set();
  const flag = (sig, where) => {
    const id = "deser-" + sig.kind;
    if (seen.has(id)) { const f = findings.find((x) => x.id === id); if (f && f.detail.length < 8) f.detail.push(where); return; }
    seen.add(id);
    findings.push({ id, title: "Untrusted serialized data (" + sig.kind + ")", severity: sig.severity, cwe: "CWE-502", owasp: "A08:2021", why: sig.note, fix: "Do not deserialize data that round-trips through the client; sign/encrypt it, or use a data-only format (plain JSON) with a schema check.", detail: [where] });
  };
  for (const c of input.cookies || []) { const sig = sec.detectSerialized(c.value); if (sig) flag(sig, "cookie " + c.name); }
  if (input.url) { try { const u = new URL(input.url); for (const part of [u.search.slice(1), u.hash.slice(1)]) for (const kv of part.split("&")) { const [k, v] = kv.split("="); const sig = sec.detectSerialized(decodeURIComponent(v || k || "")); if (sig) flag(sig, "url parameter" + (k ? " " + k : "")); } } catch {} }
  for (const s of input.serialStorage || []) { const sig = sec.SERIAL_SIGS.find((x) => x.kind === s.kind); if (sig) flag(sig, s.area + " key " + s.key); }
  if (input.viewstate && input.viewstate.present && input.viewstate.protected === false) findings.push({ id: "viewstate-unprotected", title: "ASP.NET ViewState without evident integrity protection", severity: "medium", cwe: "CWE-502", owasp: "A08:2021", why: "A ViewState that is not MAC-protected can be tampered with and, on vulnerable servers, drive deserialization.", fix: "Enable ViewState MAC and encryption (enableViewStateMac, ViewStateEncryptionMode=Always).", detail: [] });
  return { findings };
};

// Grade the domains and subdomains a page pulled from. hosts: [{host, https, thirdParty, bad}]
// bad is set by the caller from threat intel. Returns findings + a per-host list.
sec.auditHosts = function auditHosts(hosts = []) {
  const findings = [];
  const list = hosts.map((h) => ({ host: h.host, https: h.https !== false, thirdParty: !!h.thirdParty, bad: h.bad || null }));
  const insecure = list.filter((h) => !h.https);
  const flagged = list.filter((h) => h.bad);
  if (flagged.length) findings.push({ id: "domain-known-bad", title: flagged.length + " domain(s) on a threat list", severity: "critical", cwe: "CWE-829", owasp: "A08:2021", why: "The page loads from a host flagged as malicious or a known tracker — anything it serves runs here.", fix: "Remove the flagged host(s): " + flagged.map((h) => h.host).join(", "), detail: flagged.map((h) => h.host + (h.bad ? " (" + h.bad + ")" : "")) });
  if (insecure.length) findings.push({ id: "domain-insecure", title: insecure.length + " domain(s) reached over http", severity: "medium", cwe: "CWE-319", owasp: "A02:2021", why: "Resources from these hosts arrive unencrypted and can be read or altered in transit.", fix: "Load every sub/domain over https.", detail: insecure.map((h) => h.host) });
  const thirdParties = list.filter((h) => h.thirdParty).length;
  return { findings, list, thirdParties, total: list.length };
};

// Merge a header audit and a page audit into one graded report.
sec.auditMerge = function auditMerge(headerAudit, pageAudit) {
  const findings = headerAudit.findings.filter((f) => !f.pass).concat((pageAudit && pageAudit.findings) || []);
  // page-level criticals pull the grade down too
  let score = headerAudit.score;
  for (const f of (pageAudit && pageAudit.findings) || []) score += f.severity === "critical" ? -25 : f.severity === "high" ? -15 : f.severity === "medium" ? -10 : f.severity === "info" ? 0 : -3;
  score = Math.max(0, Math.min(100, score));
  const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
  findings.sort((a, b) => (order[a.severity] ?? 5) - (order[b.severity] ?? 5));
  return { score, grade: sec.grade(score), https: headerAudit.https, cookies: headerAudit.cookies, findings, passed: headerAudit.findings.filter((f) => f.pass).length, failed: findings.length };
};
})();
