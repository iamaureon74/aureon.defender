// Attack-vector surface checks for the passive site audit.
//
// Each detector below maps to a named vector from the shepherd attack-vector
// tree, but fires ONLY on something the browser already received — the url, the
// response headers, the cookie store, the loaded page, its forms, links,
// storage and service workers. Nothing is probed, fuzzed, or sent. A finding
// marks an exposure or a missing defense the site owner can fix; it never
// claims the attack succeeded, because passive observation cannot prove that.
//
// Server-side-only vectors (sql/nosql/ldap/xpath injection, ssti, xxe, command
// injection, ssrf, deserialization gadget execution, request smuggling, cache
// poisoning, brute force, cloud/k8s/docker, supply-chain) cannot be seen from
// the browser without attacking the site, so they are NOT guessed here. The
// coverage note (sec.vectorCoverage) states that plainly in the report.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const REDIRECT_PARAM = /^(next|url|redirect|redirect_uri|redirecturl|return|returnurl|return_to|returnto|goto|dest|destination|continue|target|forward|out|away|link|u|r)$/i;
const SESSION_PARAM = /^(phpsessid|jsessionid|sid|sessid|sessionid|session_id|aspsessionid|asp\.net_sessionid|cfid|cftoken|zenid)$/i;
const TOKEN_FIELD = /csrf|xsrf|_token|authenticity|antiforgery|requestverification|nonce/i;

function looksAbsolute(v) { const s = decodeURIComponent(String(v || "")); return /^(https?:)?\/\//i.test(s) || /^https?:\/\//i.test(s); }
function offSite(v, host) { try { const u = new URL(decodeURIComponent(v), "https://" + host + "/"); return u.hostname.replace(/^www\./, "") !== host; } catch { return false; } }

// input: { url, host, headers, cookies:[{name,domain,secure,httpOnly,sameSite}],
//          links:[{params:[names]}], forms:[{method,hasPassword,hasToken,crossSite}],
//          serviceWorkers:[{scope}], hasSession:bool, textSignals:{clickfix} }
sec.auditVectors = function auditVectors(input = {}) {
  const findings = [];
  const host = (input.host || "").replace(/^www\./, "");
  const add = (f) => findings.push(f);

  // --- open redirect (CWE-601) : redirect-shaped param carrying an absolute/off-site url ---
  try {
    const u = new URL(input.url);
    for (const [k, v] of u.searchParams) {
      if (REDIRECT_PARAM.test(k) && looksAbsolute(v) && offSite(v, host)) {
        add({ id: "open-redirect", vector: "Open Redirect", title: "Redirect parameter carries an off-site URL", severity: "low", cwe: "CWE-601", owasp: "A01:2021", why: "A “" + k + "=” parameter pointing to another domain is the shape attackers use to lend a trusted link to a phishing page; confirm the app validates the destination.", fix: "Allow only relative paths or an allowlist of destinations for redirect parameters; never redirect to a raw user-supplied URL.", detail: [k + " → " + decodeURIComponent(v).slice(0, 80)] });
        break;
      }
    }
  } catch {}
  if (!findings.some((f) => f.id === "open-redirect")) {
    for (const href of input.links || []) {
      try { const u = new URL(href, input.url); for (const [k, v] of u.searchParams) { if (REDIRECT_PARAM.test(k) && looksAbsolute(v) && offSite(v, host)) { add({ id: "open-redirect", vector: "Open Redirect", title: "A link on this page redirects through an off-site URL", severity: "low", cwe: "CWE-601", owasp: "A01:2021", why: "A “" + k + "=” parameter pointing to another domain is the shape attackers use to lend a trusted link to a phishing page; confirm the app validates the destination.", fix: "Allow only relative paths or an allowlist of destinations for redirect parameters; never redirect to a raw user-supplied URL.", detail: [k + " → " + decodeURIComponent(v).slice(0, 80)] }); break; } } } catch {}
      if (findings.some((f) => f.id === "open-redirect")) break;
    }
  }

  // --- session id in URL (CWE-384 session fixation / token leak) ---
  try {
    const u = new URL(input.url);
    const hit = [...u.searchParams.keys()].find((k) => SESSION_PARAM.test(k)) || (SESSION_PARAM.test("") ? null : (/;jsessionid=/i.test(u.pathname) ? "jsessionid" : null));
    if (hit) add({ id: "session-in-url", vector: "Session Fixation", title: "Session identifier carried in the URL", severity: "medium", cwe: "CWE-384", owasp: "A07:2021", why: "A session id in the URL leaks through browser history, referer headers and server logs, and enables session-fixation if it is not regenerated at login.", fix: "Keep session ids in Secure, HttpOnly cookies only; never in the URL, and regenerate the id on authentication." });
  } catch {}

  // --- cookie tossing surface: session cookie scoped to the parent domain ---
  for (const c of input.cookies || []) {
    const dom = String(c.domain || "").replace(/^\./, "").replace(/^www\./, "");
    const isSession = /sess|sid|auth|token|login|jwt|csrf|xsrf|phpsessid|jsessionid/i.test(c.name);
    if (isSession && dom && dom !== host && host.endsWith("." + dom) && dom.split(".").length >= 2) {
      add({ id: "cookie-parent-scope", vector: "Cookie Tossing / Subdomain Injection", title: 'Session cookie "' + c.name + '" is shared with every subdomain of ' + dom, severity: "low", cwe: "CWE-732", owasp: "A05:2021", why: "A cookie scoped to the parent domain can be read or overwritten by any subdomain; one compromised subdomain can fixate or steal it.", fix: "Scope session cookies to the exact host (omit the Domain attribute), and use __Host- prefixed cookies where possible." });
      break;
    }
  }

  // --- CORS null origin (CWE-942) ---
  const acao = input.headers && Object.keys(input.headers).find((k) => k.toLowerCase() === "access-control-allow-origin");
  if (acao && String(input.headers[acao]).trim().toLowerCase() === "null") add({ id: "cors-null-origin", vector: "CORS Misconfiguration", title: "CORS allows the null origin", severity: "medium", cwe: "CWE-942", owasp: "A05:2021", why: "Access-Control-Allow-Origin: null can be reached from a sandboxed iframe, letting an attacker page read authenticated responses.", fix: "Never return the null origin; echo only specific allowed origins." });

  // --- CSRF: state-changing form with no visible anti-CSRF token ---
  for (const form of input.forms || []) {
    if ((form.method || "").toLowerCase() === "post" && !form.hasToken && !form.crossSite && (form.hasPassword || input.hasSession)) {
      add({ id: "csrf-no-token", vector: "CSRF", title: "POST form has no visible anti-CSRF token", severity: "low", cwe: "CWE-352", owasp: "A01:2021", why: "A state-changing form with no token field relies entirely on SameSite cookies; SameSite=Lax still sends cookies on top-level navigations, so confirm a token or a custom header is required.", fix: "Include a per-request anti-CSRF token (or require a custom header) on all state-changing requests, alongside SameSite cookies." });
      break;
    }
  }

  // --- service worker persistence surface (informational, no score penalty) ---
  if (Array.isArray(input.serviceWorkers) && input.serviceWorkers.length) {
    add({ id: "service-worker", vector: "Service Worker Hijacking (surface)", title: input.serviceWorkers.length + " service worker(s) control this origin", severity: "info", cwe: "CWE-16", owasp: "A05:2021", why: "A service worker intercepts every request to this origin and persists across sessions; normal for a PWA, but it is also what an XSS-planted worker abuses. Worth knowing it is here.", fix: "Ensure service workers are only registered from first-party, integrity-checked scripts and scoped as narrowly as possible.", detail: input.serviceWorkers.map((w) => w.scope).slice(0, 4) });
  }

  // --- ClickFix clipboard social-engineering (2026 dominant lure) ---
  if (input.textSignals && input.textSignals.clickfix) add({ id: "clickfix", vector: "ClickFix (clipboard RCE lure)", title: "Page shows run-dialog “verification” instructions — possible ClickFix", severity: "high", cwe: "CWE-1021", owasp: "A04:2021", why: "This page tells the visitor to open the Windows Run dialog and paste a command — the hallmark of a ClickFix lure that loads a malicious command into the clipboard. Do not paste anything into Run or PowerShell from this page.", fix: "If this is your site, remove the instruction; if you are a visitor, close the page and run nothing it asks you to paste." });

  return { findings };
};

// Honest coverage statement for the report: what the passive audit does and does not grade.
sec.vectorCoverage = function vectorCoverage() {
  return {
    gradedPassively: [
      "transport & headers (HSTS, CSP, X-Frame-Options/clickjacking, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP/COEP/CORP)",
      "cookies (Secure, HttpOnly, SameSite, parent-domain scope)",
      "mixed content, insecure & cross-site forms, subresource integrity",
      "CORS misconfiguration (wildcard+credentials, null origin)",
      "untrusted serialized data in cookies/url/storage (CWE-502)",
      "open-redirect-shaped parameters, session id in URL",
      "sub/domains the page loads from, and known-bad hosts",
      "ClickFix clipboard social-engineering on the page",
    ],
    needsActiveTesting: [
      "server-side injection (SQL, NoSQL, LDAP, XPath, SSTI, command, XXE)",
      "SSRF, LFI/RFI, request smuggling, cache poisoning",
      "deserialization gadget execution, IDOR/BOLA, business-logic flaws",
      "brute force / credential stuffing / MFA bypass, auth & OAuth/SAML logic",
      "infrastructure, cloud, container, and supply-chain exposure",
    ],
  };
};
})();
