/**
 * noah shield — cognitive sovereignty overlay
 *
 * Detects Robert Cialdini's six influence weapons in live page content
 * (urgency, scarcity, social proof, authority, reciprocity/confirm-shaming,
 * commitment/pre-ticked traps) and gives the user a transparent, dismissable
 * summary so they can decide with a clear head rather than a manipulated one.
 *
 * Runs at document_idle in the ISOLATED world. Performance notes (v10.2):
 * the scan reads text through one TreeWalker (no layout, no per-tag
 * querySelectorAll), runs through the shared pace watcher a handful of times
 * per page instead of after every DOM change, and only unticks boxes that the
 * page itself pre-ticked (defaultChecked), never one the person ticked.
 *
 * The UI is a small collapsible pill fixed to the bottom-right corner.
 * It appears only when ≥ 2 distinct manipulation vectors are active, and
 * puts itself away after a while so it never sits on top of a page's buttons.
 */
(() => {
  "use strict";
  if (window.top !== window) return;
  const pace = window.__noahPace;

  const VECTORS = [
    {
      id: "urgency",
      label: "Urgency",
      desc: "Artificial time pressure is being used to rush your decision.",
      patterns: [
        /\blimited[\s-]?time\b/i,
        /\btoday only\b/i,
        /\bends?\s+(?:in|soon|tonight|at midnight)\b/i,
        /\b(?:hurry|act now|don't wait|last chance)\b/i,
        /\b(?:expires?|expiring)\s+(?:in|soon)\b/i,
        /\b(?:\d+\s+(?:hour|minute|second)s?\s+(?:left|remaining))\b/i,
      ],
    },
    {
      id: "scarcity",
      label: "Scarcity",
      desc: "Low-stock claims push FOMO — real scarcity rarely needs a banner.",
      patterns: [
        /\bonly\s+\d+\s+left\b/i,
        /\b\d+\s+(?:item|unit|seat|spot|ticket)s?\s+(?:left|remaining)\b/i,
        /\bselling\s+(?:fast|out)\b/i,
        /\balmost\s+(?:gone|sold out)\b/i,
        /\bhigh\s+demand\b/i,
        /\blimited\s+(?:stock|availability|supply|edition)\b/i,
      ],
    },
    {
      id: "social_proof",
      label: "Social Proof",
      desc: "Crowd-following cues are meant to replace your own judgement.",
      patterns: [
        /\b\d+[,\d]*\s+(?:people|customers|users|others)\s+(?:bought|viewed|watching|looking at this)\b/i,
        /\b#1\s+(?:choice|rated|selling)\b/i,
        /\bjoined\s+by\s+\d/i,
        /\bbest\s*seller\b/i,
      ],
    },
    {
      id: "authority",
      label: "Authority",
      desc: "Credential-dropping or endorsement claims signal deference pressure.",
      patterns: [
        /\b(?:as\s+seen\s+on|featured\s+in)\b/i,
        /\b(?:expert[- ]recommended|doctor[- ]approved|clinically\s+(?:tested|proven|validated))\b/i,
        /\b(?:award[- ]winning|industry[- ]leading|#1\s+trusted)\b/i,
        /\bscientifically\s+(?:proven|backed|validated)\b/i,
      ],
    },
    {
      id: "confirm_shame",
      label: "Confirm-Shaming",
      desc: "The 'No' option is written to make you feel bad for declining.",
      patterns: [
        /\bno[,\s]+(?:i\s+)?(?:don't|hate|never|refuse|won't)\b/i,
        /\bi\s+(?:hate|don't like|don't care about)\s+(?:saving|deals|discounts|money|health|fun)\b/i,
        /\bno\s+thanks,\s+i\s+(?:like|love|enjoy|prefer)\b/i,
        /\bskip\s+(?:and\s+)?(?:miss|lose)\b/i,
      ],
    },
    {
      id: "pretick",
      label: "Pre-ticked Opt-in",
      desc: "A checkbox was pre-checked to sign you up without active consent.",
      patterns: [],
      check: () => preTicked().length > 0,
    },
  ];

  const OPT_IN = /(?:newsletter|offers?|promotions?|marketing|deals?|discounts?|partners?|third.party|advertis|send me|keep me (?:posted|informed|updated))/i;
  // Pages where ticked boxes are the person's own saved choices.
  const SETTINGS_PAGE = /\/(settings|preferences|account|profile|notifications|subscriptions|my-?account|dashboard)\b/i;

  const getLabel = (input) => {
    if (input.labels && input.labels[0]) return input.labels[0].textContent;
    const parent = input.closest("label");
    if (parent) return parent.textContent;
    if (input.getAttribute("aria-label")) return input.getAttribute("aria-label");
    if (input.getAttribute("aria-labelledby")) {
      const ref = document.getElementById(input.getAttribute("aria-labelledby"));
      if (ref) return ref.textContent;
    }
    const next = input.nextSibling;
    if (next && next.nodeType === Node.TEXT_NODE) return next.textContent;
    return "";
  };

  // Boxes the page ticked for the person: ticked now, ticked in the markup
  // (defaultChecked), with a marketing label, outside a settings page.
  function preTicked() {
    if (SETTINGS_PAGE.test(location.pathname)) return [];
    const found = [];
    for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
      if (!cb.checked || !cb.defaultChecked || cb.disabled) continue;
      const label = getLabel(cb);
      if (label && OPT_IN.test(label) && !/terms|privacy|agree|accept|remember me/i.test(label)) found.push(cb);
    }
    return found;
  }

  const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "SVG", "CODE", "PRE"]);
  const visibleText = () => {
    const root = document.body;
    if (!root) return "";
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        const parent = node.parentElement;
        if (!parent || SKIP.has(parent.tagName) || (pace && pace.isOwn(parent))) return NodeFilter.FILTER_REJECT;
        return node.nodeValue.length > 4 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      },
    });
    const parts = [];
    let total = 0;
    let node;
    while ((node = walker.nextNode()) && total < 150000) {
      const value = node.nodeValue.replace(/\s+/g, " ");
      parts.push(value);
      total += value.length;
    }
    return parts.join(" ");
  };

  const unticked = new WeakSet();
  const autoUncheck = () => {
    let count = 0;
    for (const cb of preTicked()) {
      if (unticked.has(cb)) continue;
      unticked.add(cb);
      cb.checked = false;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
      count++;
    }
    return count;
  };

  const scan = () => {
    const text = visibleText();
    const active = [];
    for (const vec of VECTORS) {
      let hit = false;
      for (const pat of vec.patterns) {
        if (pat.test(text)) { hit = true; break; }
      }
      if (!hit && vec.check) hit = vec.check();
      if (hit) active.push(vec);
    }
    return active;
  };

  // ── UI ────────────────────────────────────────────────────────────────────
  let dismissed = false;
  let uncheckedCount = 0;
  let hideTimer = null;
  const PILL_ID = "__noah_cognition_pill";
  const Z = 2147483646;
  const dismissKey = "noah-shield-cognition:" + location.hostname;
  try { dismissed = sessionStorage.getItem(dismissKey) === "1"; } catch { /* fine */ }

  const buildPill = (active) => {
    if (document.getElementById(PILL_ID)) return;
    const host = document.createElement("div");
    host.id = PILL_ID;
    host.setAttribute("data-noah", "1");
    const shadow = host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = `
      :host { all: initial; }
      #wrap { position: fixed; bottom: 18px; right: 18px; z-index: ${Z}; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 13px; line-height: 1.4; max-width: 300px; background: rgba(11, 18, 13, 0.92); color: #e9e7d6; border: 1px solid rgba(201, 210, 122, 0.16); border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.6); overflow: hidden; transition: opacity .3s ease; user-select: none; }
      #wrap.fade { opacity: .35; }
      #wrap.fade:hover { opacity: 1; }
      #header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer; background: rgba(201, 210, 122, 0.06); }
      #icon { font-size: 15px; flex-shrink: 0; }
      #title { flex: 1; font-weight: 600; font-size: 12px; color: #d9c08a; letter-spacing: .03em; }
      #toggle { color: #555; font-size: 11px; }
      #close { color: #777; font-size: 14px; padding: 0 4px; cursor: pointer; }
      #close:hover { color: #fff; }
      #body { padding: 0 12px 10px; display: none; }
      #body.open { display: block; }
      .vec { margin-top: 8px; border-left: 2px solid #d9c08a; padding-left: 8px; }
      .vec-name { font-weight: 600; color: #d9c08a; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
      .vec-desc { color: #aaa; font-size: 11px; margin-top: 2px; }
      #uncheckNote { margin-top: 8px; color: #c9d27a; font-size: 11px; }
      #dismiss { display: block; margin-top: 10px; width: 100%; padding: 5px 0; background: none; border: 1px solid rgba(201, 210, 122, 0.16); border-radius: 6px; color: #777; font-size: 11px; cursor: pointer; text-align: center; }
      #dismiss:hover { color: #ccc; border-color: #444; }
      @media (prefers-reduced-motion: reduce) { #wrap { transition: none; } }
    `;
    const wrap = document.createElement("div");
    wrap.id = "wrap";
    const header = document.createElement("div");
    header.id = "header";
    const icon = document.createElement("span"); icon.id = "icon"; icon.textContent = "🛡";
    const title = document.createElement("span"); title.id = "title"; title.textContent = `Influence detected (${active.length})`;
    const toggle = document.createElement("span"); toggle.id = "toggle"; toggle.textContent = "▼";
    const close = document.createElement("span"); close.id = "close"; close.textContent = "×"; close.title = "Hide";
    header.append(icon, title, toggle, close);
    const body = document.createElement("div");
    body.id = "body";
    for (const v of active) {
      const vec = document.createElement("div"); vec.className = "vec";
      const name = document.createElement("div"); name.className = "vec-name"; name.textContent = v.label;
      const desc = document.createElement("div"); desc.className = "vec-desc"; desc.textContent = v.desc;
      vec.append(name, desc);
      if (v.quote) {
        const quote = document.createElement("div"); quote.className = "vec-desc";
        quote.textContent = "“" + v.quote + "”" + (v.ai ? " · local AI" : "");
        vec.append(quote);
      }
      body.append(vec);
    }
    if (uncheckedCount > 0) {
      const note = document.createElement("div"); note.id = "uncheckNote";
      note.textContent = `↩ ${uncheckedCount} pre-ticked marketing checkbox${uncheckedCount > 1 ? "es" : ""} unchecked for you.`;
      body.append(note);
    }
    const dismiss = document.createElement("button"); dismiss.id = "dismiss"; dismiss.textContent = "Dismiss for this site";
    body.append(dismiss);
    header.addEventListener("click", (event) => {
      if (event.target === close) { host.remove(); return; }
      clearTimeout(hideTimer);
      wrap.classList.remove("fade");
      const open = body.classList.toggle("open");
      toggle.textContent = open ? "▲" : "▼";
    });
    dismiss.addEventListener("click", () => {
      dismissed = true;
      try { sessionStorage.setItem(dismissKey, "1"); } catch { /* fine */ }
      host.remove();
    });
    wrap.append(header, body);
    shadow.append(style, wrap);
    document.documentElement.appendChild(host);
    if (window.__noahShieldDrag) window.__noahShieldDrag(wrap, header, "cognition");
    // Out of the way after a moment: faded, then gone, so it never covers a button.
    hideTimer = setTimeout(() => { wrap.classList.add("fade"); hideTimer = setTimeout(() => { if (!body.classList.contains("open")) host.remove(); }, 20000); }, 8000);
  };

  const removePill = () => {
    const el = document.getElementById(PILL_ID);
    if (el) el.remove();
  };

  // ── local AI second opinion (lib/local.js) ──────────────────────────────
  // When the patterns see at least one tactic, the page's text is shown to a
  // language model on this computer (only if you turned it on). It catches
  // reworded pressure the fixed patterns miss. Asked once per page.
  const api = globalThis.chrome ?? globalThis.browser;
  let aiAsked = false;
  const AI_LABELS = { urgency: "Urgency", scarcity: "Scarcity", "social proof": "Social proof", authority: "Authority", reciprocity: "Reciprocity", commitment: "Commitment", confirmshaming: "Confirm-shaming", fear: "Fear", "hidden costs": "Hidden costs", "fake discount": "Fake discount" };
  const askLocalAi = (text) => new Promise((resolve) => {
    try { api.runtime.sendMessage({ type: "ai.cognition", text: text.slice(0, 20000) }, (answer) => { void api.runtime.lastError; resolve(answer || {}); }); } catch { resolve({}); }
  });
  const merge = (active, tactics) => {
    const have = new Set(active.map((v) => v.label.toLowerCase()));
    const out = active.slice();
    for (const t of tactics) {
      const label = AI_LABELS[t.name] || t.name;
      const existing = out.find((v) => v.label.toLowerCase() === label.toLowerCase());
      if (existing) { if (!existing.quote) out[out.indexOf(existing)] = Object.assign({}, existing, { quote: t.quote, ai: true }); continue; }
      if (!have.has(label.toLowerCase())) out.push({ id: "ai-" + t.name, label, desc: t.why || "Seen by your local AI.", quote: t.quote, ai: true });
    }
    return out;
  };

  let shown = false;
  const runScan = () => {
    if (dismissed || document.hidden) return;
    uncheckedCount += autoUncheck();
    const active = scan();
    if (active.length >= 2 && !shown) {
      shown = true;
      removePill();
      buildPill(active);
    }
    if (active.length >= 1 && !aiAsked) {
      aiAsked = true;
      askLocalAi(visibleText()).then((answer) => {
        if (!answer || !Array.isArray(answer.tactics) || !answer.tactics.length || dismissed) return;
        if (shown && !document.getElementById(PILL_ID)) return; // you already closed it
        const merged = merge(scan(), answer.tactics);
        if (merged.length < 2) return;
        shown = true;
        removePill();
        buildPill(merged);
      });
    }
  };

  const begin = () => setTimeout(runScan, 900);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin, { once: true });
  else begin();

  // A few more looks as the page fills in (SPA navigation, lazy content); then quiet.
  if (pace) pace.watch(runScan, { delay: 3000, settledDelay: 8000, maxRuns: 6 });
  else {
    let timer = null;
    let runs = 0;
    const observer = new MutationObserver(() => {
      if (dismissed || timer) return;
      timer = setTimeout(() => { timer = null; runScan(); if (++runs >= 6) observer.disconnect(); }, 3000);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
