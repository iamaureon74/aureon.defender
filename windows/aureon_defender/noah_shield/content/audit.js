// Page-fact collector for the passive site audit.
//
// Reads only the page the browser already loaded — never probes, never
// touches another origin. On request it reports the facts the header audit
// cannot see from headers alone: resources pulled over http on an https page,
// forms that send passwords off-origin or in the clear, third-party scripts
// with no Subresource Integrity, and whether a CSP was set via <meta>.
"use strict";
(() => {
  if (window.__noahAuditFacts) return;
  window.__noahAuditFacts = true;
  const api = (typeof browser !== "undefined" && browser.runtime) ? browser : chrome;

  function collect() {
    const https = location.protocol === "https:";
    const here = location.hostname.replace(/^www\./, "");
    const isHttp = (u) => { try { return new URL(u, location.href).protocol === "http:"; } catch { return false; } };
    const sameSite = (u) => { try { return new URL(u, location.href).hostname.replace(/^www\./, "").endsWith(here); } catch { return true; } };

    const mixedContent = [];
    if (https) for (const node of document.querySelectorAll("script[src],link[href],img[src],iframe[src],video[src],audio[src],source[src],embed[src],object[data]")) {
      const url = node.getAttribute("src") || node.getAttribute("href") || node.getAttribute("data") || "";
      if (url && isHttp(url)) mixedContent.push(url.slice(0, 120));
      if (mixedContent.length >= 20) break;
    }

    const tokenField = /csrf|xsrf|_token|authenticity|antiforgery|requestverification|nonce/i;
    const forms = [];
    for (const form of document.querySelectorAll("form")) {
      const action = form.getAttribute("action") || location.href;
      const hasToken = [...form.querySelectorAll("input[name]")].some((i) => tokenField.test(i.getAttribute("name") || ""));
      forms.push({ action: String(action).slice(0, 120), method: (form.getAttribute("method") || "get").toLowerCase(), https: !isHttp(action), crossSite: !sameSite(action), hasPassword: !!form.querySelector('input[type="password"]'), hasToken });
      if (forms.length >= 30) break;
    }

    // links carrying a redirect-shaped parameter (open-redirect surface)
    const redirectParam = /^(next|url|redirect|redirect_uri|redirecturl|return|returnurl|return_to|returnto|goto|dest|destination|continue|target|forward|out|away|link|u|r)$/i;
    const links = [];
    for (const a of document.querySelectorAll("a[href]")) {
      const href = a.getAttribute("href") || "";
      if (!/[?&]/.test(href)) continue;
      try { const u = new URL(href, location.href); for (const [k, v] of u.searchParams) { if (redirectParam.test(k) && /^(https?:)?\/\//i.test(decodeURIComponent(v))) { links.push(href.slice(0, 140)); break; } } } catch {}
      if (links.length >= 10) break;
    }

    // clickfix lure: run-dialog + paste/verification instructions in the visible text
    let clickfix = false;
    try {
      const text = (document.body ? document.body.innerText : "").slice(0, 20000).toLowerCase();
      const runDialog = /win(dows)?\s*(key)?\s*\+\s*r\b/.test(text) || /⊞\s*\+?\s*r\b/.test(text) || /open (the )?run (dialog|box)/.test(text);
      const paste = /ctrl\s*\+\s*v/.test(text) || /press\s+(enter|paste)/.test(text) || /paste (it|the|this)/.test(text);
      const lure = /verify (you are |you're )?(a )?human|i'?m not a robot|not a robot|verification (code|required|steps)|to (continue|proceed|fix|verify)/.test(text);
      clickfix = runDialog && (paste || lure);
    } catch {}
    // a password field outside any <form> still submits somewhere
    if (!forms.some((f) => f.hasPassword) && document.querySelector('input[type="password"]')) forms.push({ action: location.href, https, crossSite: false, hasPassword: true });

    const externalScripts = [];
    for (const s of document.querySelectorAll("script[src]")) {
      const src = s.getAttribute("src") || "";
      if (/^https?:\/\//.test(src) && !sameSite(src)) externalScripts.push({ src: src.slice(0, 140), integrity: s.getAttribute("integrity") || "" });
      if (externalScripts.length >= 40) break;
    }

    // every distinct domain / subdomain this page pulled a resource from,
    // with how it was reached — so the audit can grade the page and its sub/domains.
    const hostMap = new Map();
    const note = (u) => {
      try {
        const url = new URL(u, location.href);
        if (!/^https?:$/.test(url.protocol)) return;
        const h = url.hostname.replace(/^www\./, "");
        const row = hostMap.get(h) || { host: h, https: true, thirdParty: !h.endsWith(here) && !here.endsWith(h) };
        if (url.protocol === "http:") row.https = false;
        hostMap.set(h, row);
      } catch {}
    };
    note(location.href);
    for (const node of document.querySelectorAll("script[src],link[href],img[src],iframe[src],video[src],audio[src],source[src],embed[src],object[data]")) {
      note(node.getAttribute("src") || node.getAttribute("href") || node.getAttribute("data") || "");
      if (hostMap.size >= 80) break;
    }
    const hosts = [...hostMap.values()];

    // serialized-object exposure in page storage (CWE-502), classified locally.
    // only the serializer kind and the key are reported — never the value.
    const sigs = [
      ["node-serialize", (s) => s.includes("_$$ND_FUNC$$_")],
      ["java", (s) => s.startsWith("rO0AB")],
      ["php-object", (s) => /O:\d+:"/.test(s)],
      ["python-pickle", (s) => s.startsWith("gASV") || s.startsWith("gAJ") || s.startsWith("gAN")],
      ["dotnet-viewstate", (s) => s.startsWith("/wEP") || s.startsWith("/wEW")],
    ];
    const classify = (v) => { const s = String(v || ""); if (s.length < 5) return null; for (const [kind, t] of sigs) { try { if (t(s)) return kind; } catch {} } return null; };
    const serialStorage = [];
    for (const [area, store] of [["localStorage", (() => { try { return localStorage; } catch { return null; } })()], ["sessionStorage", (() => { try { return sessionStorage; } catch { return null; } })()]]) {
      if (!store) continue;
      try { for (let i = 0; i < store.length && serialStorage.length < 20; i++) { const key = store.key(i); const kind = classify(store.getItem(key)); if (kind) serialStorage.push({ area, key: String(key).slice(0, 40), kind }); } } catch {}
    }
    // asp.net viewstate integrity signal
    let viewstate = null;
    const vs = document.querySelector('input[name="__VIEWSTATE"]');
    if (vs) viewstate = { present: true, protected: !!document.querySelector('input[name="__VIEWSTATEGENERATOR"]') && !/^\/wEP/.test(vs.value || "") };

    const metaCsp = !!document.querySelector('meta[http-equiv="Content-Security-Policy" i]');
    return { https, host: here, mixedContent, forms, externalScripts, metaCsp, hosts, serialStorage, viewstate, links, textSignals: { clickfix } };
  }

  api.runtime.onMessage.addListener((message, sender, reply) => {
    if (message && message.type === "audit.facts") {
      (async () => {
        let facts;
        try { facts = collect(); } catch { reply({ error: true }); return; }
        try { if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) { const regs = await navigator.serviceWorker.getRegistrations(); facts.serviceWorkers = regs.map((r) => ({ scope: String(r.scope).slice(0, 120) })); } } catch {}
        reply(facts);
      })();
      return true;
    }
  });
})();
