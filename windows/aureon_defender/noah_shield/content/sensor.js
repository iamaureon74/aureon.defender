// Page sensor (isolated world): reads the facts the security rules need and
// sends them to the worker as events. It sends no page text, form values
// or cookies: only yes/no facts, host names and short labels.
//   page.scan     password field? brand named in title/headings? fake browser
//                 window drawn in the page? instructions to open the run box?
//   form.submit   where a form (or a script, via sensor_main.js) sends a
//                 password: host, http or https, same site or not
//   clipboard.write   forwarded from sensor_main.js
//   page.tabnab   a background tab that turned into a login page
//   shop.scan     payment methods and contact pages on store pages
(() => {
  if (window.top !== window || window.__noahSensor) return;
  window.__noahSensor = true;
  const api = globalThis.browser || globalThis.chrome;
  const send = (event) => { try { api.runtime.sendMessage({ type: "sec.sense", event }).catch?.(() => {}); } catch {} };
  const host = location.hostname.toLowerCase();
  const siteOf = (h) => {
    const parts = String(h || "").toLowerCase().split(".");
    if (parts.length <= 2) return parts.join(".");
    const two = parts.slice(-2).join(".");
    return /^(co|com|org|net|gov|ac|edu)\.[a-z]{2}$/.test(two) ? parts.slice(-3).join(".") : two;
  };
  const site = siteOf(host);
  if (!/^https?:$/.test(location.protocol)) return;

  const SSO = /(^|\.)(accounts\.google\.com|google\.com|login\.microsoftonline\.com|login\.live\.com|microsoft\.com|appleid\.apple\.com|apple\.com|facebook\.com|github\.com|auth0\.com|okta\.com|oktapreview\.com|onelogin\.com|duosecurity\.com|amazoncognito\.com|paypal\.com|stripe\.com|shopify\.com|salesforce\.com|pingidentity\.com|jumpcloud\.com|login\.gov|id\.me|twitter\.com|x\.com|linkedin\.com|yahoo\.com|amazon\.com)$/;
  let brands = [];
  try { api.runtime.sendMessage({ type: "sec.brands" }).then((list) => { brands = Array.isArray(list) ? list : []; scanSoon(); }); } catch {}

  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 4 && r.height > 4 && s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.05; };
  const passwordFields = () => Array.from(document.querySelectorAll("input[type=password]")).filter(visible);

  // ---- page.scan -------------------------------------------------------------------------
  const RUN = /(press|hold)\s+(down\s+)?(the\s+)?(windows|win|⊞)\s*(logo\s*)?(key\s*)?(\+|and|&)\s*(the\s+)?["']?r\b|\bwin\s*\+\s*r\b|windows\s*\+\s*r\b|⊞\s*\+\s*r\b|open\s+(the\s+)?(run\s+(dialog|box|window)|terminal|powershell|command\s+prompt)|paste\s+(it\s+|the\s+code\s+|this\s+)?(into|in)\s+(the\s+)?(run|terminal|powershell|command)|(ctrl|control)\s*\+\s*v[^.]{0,40}(enter|return)|cmd\s*\+\s*space[^.]{0,40}terminal/i;
  let lastSent = "";
  function scan() {
    const pw = passwordFields();
    const headings = [document.title, ...Array.from(document.querySelectorAll("h1,h2,[class*=logo] img,[id*=logo] img,header img")).slice(0, 12).map((el) => el.alt || el.textContent || "")].join(" ").toLowerCase();
    let brand = null, brandDomain = true;
    for (const entry of brands) {
      if (new RegExp("\\b" + entry.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i").test(headings)) {
        brand = entry.name;
        brandDomain = entry.domains.some((d) => host === d || host.endsWith("." + d));
        if (!brandDomain) break;
      }
    }
    // a positioned box that shows an address-bar-like https://… line and a login inside
    let fakeWindow = false;
    for (const box of Array.from(document.querySelectorAll("div,section,dialog")).slice(0, 4000)) {
      const style = getComputedStyle(box);
      if (style.position !== "fixed" && style.position !== "absolute") continue;
      if (!visible(box) || box.getBoundingClientRect().width < 250) continue;
      if (!box.querySelector("input[type=password], iframe")) continue;
      const bar = Array.from(box.querySelectorAll("div,span,p,input")).slice(0, 60).find((el) => /^\s*(https?:\/\/)?[a-z0-9-]+(\.[a-z0-9-]+)+\/[^\s]*\s*$/i.test(el.value || el.textContent || "") && (el.textContent || el.value || "").length < 160);
      if (bar) {
        const shown = ((bar.value || bar.textContent).match(/[a-z0-9-]+(\.[a-z0-9-]+)+/i) || [""])[0].toLowerCase();
        if (shown && siteOf(shown) !== site) { fakeWindow = true; break; }
      }
    }
    const text = (document.body ? document.body.innerText : "").slice(0, 30000);
    const runInstruction = RUN.test(text);
    const data = { hasPassword: pw.length > 0, brand, brandDomain, fakeWindow, runInstruction, title: document.title.slice(0, 120) };
    const signature = JSON.stringify(data);
    if (signature !== lastSent && (data.hasPassword || data.runInstruction || data.fakeWindow)) { lastSent = signature; send({ kind: "page.scan", data }); }
    shopScan(text);
  }
  let timer = null, scans = 0;
  function scanSoon() { if (timer || scans > 12) return; timer = setTimeout(() => { timer = null; scans++; try { scan(); } catch {} }, 1200); }

  // ---- forms -------------------------------------------------------------------------------
  function reportSubmit(action, hasPassword, via) {
    let target;
    try { target = new URL(action || location.href, location.href); } catch { return; }
    const actionHost = target.hostname.toLowerCase();
    send({ kind: "form.submit", data: { hasPassword, via, actionHost, actionScheme: target.protocol.replace(":", ""), crossSite: siteOf(actionHost) !== site, knownSso: SSO.test(actionHost) } });
  }
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const hasPassword = Array.from(form.querySelectorAll("input[type=password]")).some((input) => input.value);
    reportSubmit(form.getAttribute("action") || location.href, hasPassword, "form");
  }, true);

  // ---- messages from the page-world sensor ---------------------------------------------------
  window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data || !event.data.__noahSensor) return;
    const p = event.data.__noahSensor;
    if (p.kind === "clipboard.write") send({ kind: "clipboard.write", data: { commandLike: Boolean(p.commandLike), length: Number(p.length) || 0, sample: String(p.sample || "").slice(0, 120), runInstruction: RUN.test((document.body ? document.body.innerText : "").slice(0, 30000)) } });
    if (p.kind === "form.submit") reportSubmit(p.action, true, String(p.via || "script"));
  });

  // ---- tab-nabbing ---------------------------------------------------------------------------
  let hiddenState = null;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { hiddenState = { title: document.title, url: location.href, password: passwordFields().length > 0 }; return; }
    if (!hiddenState) return;
    const changed = document.title !== hiddenState.title || location.href !== hiddenState.url;
    if (changed && !hiddenState.password && passwordFields().length > 0) send({ kind: "page.tabnab", data: { title: document.title.slice(0, 120), before: hiddenState.title.slice(0, 120) } });
    hiddenState = null;
  });

  // ---- stores ----------------------------------------------------------------------------------
  let shopSent = false;
  function shopScan(text) {
    if (shopSent) return;
    const lower = text.toLowerCase();
    const isStore = /add to (cart|bag|basket)|checkout|\bbuy now\b|shopping (cart|bag)/.test(lower);
    if (!isStore) return;
    const card = /\b(visa|mastercard|american express|amex|credit card|debit card|apple pay|google pay|paypal|klarna)\b/.test(lower);
    const signals = [];
    if (/\b(bitcoin|btc|usdt|tether|ethereum|crypto(currency)?)\b/.test(lower) && !card) signals.push("payment only by crypto");
    if (/\b(gift ?cards?|steam card|itunes card|google play card)\b[^.]{0,60}\b(pay|payment)/.test(lower)) signals.push("asks for payment by gift card");
    if (/\b(western union|moneygram|wire transfer|bank transfer only|zelle only|cash app only)\b/.test(lower) && !card) signals.push("payment only by wire or cash app");
    const links = Array.from(document.querySelectorAll("a[href]")).map((a) => (a.textContent + " " + a.getAttribute("href")).toLowerCase());
    if (!links.some((l) => /contact|about|return|refund|imprint|impressum|support|customer service/.test(l))) signals.push("no contact, about or returns page");
    if (/\b(9[0-9]|8[5-9])\s?% off\b/.test(lower)) signals.push("claims 85–99% off");
    shopSent = true;
    send({ kind: "shop.scan", data: { signals, signalCount: signals.length } });
  }

  const observer = new MutationObserver(scanSoon);
  const start = () => { scanSoon(); if (document.body) observer.observe(document.body, { childList: true, subtree: true }); setTimeout(() => observer.disconnect(), 60000); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true }); else start();
})();
