// Reading a site's own pricing page into plans: name, price, period.
//
// The worker has no DOM, so the page is read as a stream of headings and
// text in document order. A price belongs to the heading above it (the plan's
// name). Structured data (schema.org Offer) wins when the page has it.
// Only what the page states is returned; a page with no readable prices
// returns no plans, never a guess.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});

const SYMBOLS = { "$": "USD", "US$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR", "C$": "CAD", "A$": "AUD", "R$": "BRL", "CHF": "CHF", "kr": "SEK" };
const PRICE = /(US\$|C\$|A\$|R\$|\$|€|£|¥|₹)\s?(\d{1,5}(?:[.,]\d{1,2})?)(?:\s*(?:USD|EUR|GBP))?\s*(?:\/\s*|per\s+|a\s+)?((?:user|seat|member|editor)\s*(?:\/|per)\s*)?(mo(?:nth)?|month(?:ly)?|yr|year(?:ly)?|annually|week)?/i;
const SKIP_HEADING = /pricing|faq|frequently|questions|compare|features|testimonials|trusted|customers|enterprise-grade|footer|newsletter|blog|resources|contact|support|security|integrations|why |how |what |all plans|plans for|choose|pick your|simple, |transparent/i;

function decode(text) {
  return text.replace(/&nbsp;|&#160;/g, " ").replace(/&amp;/g, "&").replace(/&#36;|&dollar;/g, "$").replace(/&euro;/g, "€").replace(/&pound;/g, "£").replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();
}

function fromJsonLd(html) {
  const plans = [];
  let currency = null;
  for (const match of html.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    let data;
    try { data = JSON.parse(match[1]); } catch { continue; }
    const visit = (node, name) => {
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) { node.forEach((n) => visit(n, name)); return; }
      const type = [].concat(node["@type"] || []).join(" ");
      if (/Offer/.test(type) && node.price !== undefined) {
        const price = Number(String(node.price).replace(",", "."));
        if (Number.isFinite(price)) {
          currency = currency || node.priceCurrency || null;
          const spec = node.priceSpecification || {};
          const unit = String(spec.unitText || spec.billingDuration || node.unitText || "").toLowerCase();
          const period = /year|p1y|annual/.test(unit) ? "yr" : /month|p1m/.test(unit) ? "mo" : "";
          plans.push({ name: String(node.name || name || "").slice(0, 30), price, period });
        }
      }
      for (const [key, value] of Object.entries(node)) if (value && typeof value === "object" && key !== "@context") visit(value, node.name || name);
    };
    visit(data, "");
  }
  return { plans, currency };
}

Shield.parsePricing = function parsePricing(html) {
  html = String(html || "").slice(0, 2_000_000);
  const structured = fromJsonLd(html);
  const cleaned = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<svg[\s\S]*?<\/svg>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<(nav|footer)\b[\s\S]*?<\/\1>/gi, " ");
  // headings become markers; everything else becomes text
  const stream = [];
  const re = /<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>|<([a-z0-9]+)\b[^>]*>|<\/[a-z0-9]+>|([^<]+)/gi;
  for (const m of cleaned.matchAll(re)) {
    if (m[2] !== undefined) { const t = decode(m[2].replace(/<[^>]+>/g, " ")); if (t) stream.push({ heading: t, level: Number(m[1]) }); }
    else if (m[4] !== undefined) { const t = decode(m[4]); if (t) stream.push({ text: t }); }
  }
  const plans = [];
  let current = null;
  let currency = structured.currency;
  for (const token of stream) {
    if (token.heading) {
      const name = token.heading.replace(/[^\p{L}\p{N} +&'-]/gu, "").trim();
      if (name && name.length <= 24 && !SKIP_HEADING.test(name) && token.level >= 2) current = { name, price: null, period: "", seen: false };
      else if (token.level <= 2) current = null;
      continue;
    }
    if (!current || current.seen) continue;
    const text = token.text;
    const found = PRICE.exec(text);
    if (found) {
      const amount = Number(found[2].replace(",", "."));
      if (!Number.isFinite(amount) || amount > 20000) continue;
      currency = currency || SYMBOLS[found[1]] || SYMBOLS[found[1].toUpperCase()] || "USD";
      const unit = (found[4] || "").toLowerCase();
      current.price = amount;
      current.period = /^y|annual/.test(unit) ? "yr" : /^mo|month/.test(unit) ? "mo" : /week/.test(unit) ? "wk" : "";
      if (found[3]) current.period = (current.period || "mo") + " per user";
      current.seen = true;
      plans.push(current);
    } else if (/^(free|\$0|0\s?\$|€0|£0)\b|free forever|always free|\bfree plan\b/i.test(text) && /^free\b/i.test(current.name) === true) {
      current.price = 0; current.seen = true; plans.push(current);
    }
  }
  let list = structured.plans.length >= 2 ? structured.plans : plans;
  const seen = new Set();
  list = list.filter((plan) => { const key = plan.name.toLowerCase(); if (!plan.name || seen.has(key)) return false; seen.add(key); return true; }).slice(0, 8)
    .map((plan) => ({ name: plan.name, price: plan.price, period: plan.period, monthly: plan.price === 0 ? 0 : /^yr/.test(plan.period) ? Math.round((plan.price / 12) * 100) / 100 : plan.price }));
  // A page that is not a pricing page mentions one stray price: need two plans.
  if (list.length < 2) list = [];
  return { plans: list, currency: currency || "USD" };
};
})();
