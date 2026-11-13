// Dark pattern detection and neutralization for noah shield.
//
// Pattern (from shepherd.intel): dark patterns are deception mechanisms.
// The mechanism: each one manipulates a specific cognitive vulnerability —
// pre-ticks exploit defaults, fake countdowns exploit urgency, confirm-shaming
// exploits shame, roach motels exploit friction asymmetry, fake anchoring
// exploits price relativity.
//
// We operate at the mechanism level, not the surface: we do not try to
// detect "bad buttons" by color or position. We detect the pattern by its
// behavioral signature and neutralize the specific exploit it uses.
//
// Runs in the ISOLATED world. Performance notes (v10.2): what has been looked
// at is remembered in WeakSets, not written into the page as data attributes
// (thousands of attribute writes per scan were themselves a storm of DOM
// changes for every other observer on the page); warnings are a tooltip and
// an outline, never an inserted element that shifts the layout; scans run
// through the shared pace watcher, and pre-ticked boxes are only unticked
// when the page ticked them (defaultChecked), never when the person did.
(() => {
  "use strict";
  if (window.__noahShieldDarkPatterns) return;
  window.__noahShieldDarkPatterns = true;
  if (window.top !== window) return;

  const api = globalThis.chrome ?? globalThis.browser;
  const pace = window.__noahPace;
  const send = (msg) => {
    try { api.runtime.sendMessage(msg, () => { void api.runtime.lastError; }); }
    catch { }
  };

  let config = { darkPatterns: true };
  try {
    api.runtime.sendMessage({ type: "dark.config" }, (r) => {
      void api.runtime.lastError;
      if (r && r.config) config = { ...config, ...r.config };
    });
  } catch { }

  const warned = new WeakSet();
  const COLORS = { "": "rgba(232,180,168,.75)", "noah-dp-countdown-warn": "rgba(220,200,150,.75)", "noah-dp-uncheck-notice": "rgba(169,207,159,.75)" };
  function warn(element, text, cls) {
    if (!element || warned.has(element)) return;
    warned.add(element);
    // A tooltip and a thin outline: nothing is inserted, nothing moves.
    element.title = (element.title ? element.title + " · " : "") + "noah shield: " + text;
    element.style.setProperty("outline", "1px dashed " + (COLORS[cls] || COLORS[""]), "important");
    element.style.setProperty("outline-offset", "1px", "important");
    send({ type: "safety.event", kind: "dark_pattern", pattern: text });
  }

  // ── 1. Pre-ticked opt-in checkboxes ─────────────────────────────────────
  const OPT_IN_PATTERNS = [
    /newsletter/i, /marketing/i, /promotional/i, /offers/i, /partner/i, /third.party/i,
    /advertising/i, /news.?letter/i, /agree to receive/i, /send me/i, /keep me (posted|informed|updated)/i,
  ];
  const SETTINGS_PAGE = /\/(settings|preferences|account|profile|notifications|subscriptions|my-?account|dashboard)\b/i;
  const boxesSeen = new WeakSet();
  function scanPreTicked() {
    if (!config.darkPatterns || SETTINGS_PAGE.test(location.pathname)) return;
    for (const cb of all('input[type="checkbox"]')) {
      if (boxesSeen.has(cb)) continue;
      boxesSeen.add(cb);
      // Only a box the page itself ticked in its markup; one the person ticked stays.
      if (!cb.checked || !cb.defaultChecked || cb.disabled) continue;
      const labelEl = cb.labels && cb.labels[0] ? cb.labels[0] : cb.closest("label");
      const labelText = labelEl ? labelEl.textContent || "" : cb.getAttribute("aria-label") || "";
      if (!labelText || /terms|privacy|agree to the|accept the|remember me/i.test(labelText)) continue;
      if (OPT_IN_PATTERNS.some((p) => p.test(labelText))) {
        cb.checked = false;
        cb.dispatchEvent(new Event("change", { bubbles: true }));
        warn(labelEl || cb, "pre-ticked opt-in unchecked by noah shield", "noah-dp-uncheck-notice");
      }
    }
  }

  // ── 2. Fake countdown timers ──────────────────────────────────────────────
  const COUNTDOWN_SELECTOR = "[class*='countdown'], [class*='count-down'], [id*='countdown'], [id*='count-down'], [data-countdown], [data-timer]";
  function looksLikeSalesCountdown(el) {
    const text = el.textContent || "";
    if (!/\d{1,2}\s*[:\s]\s*\d{1,2}/.test(text)) return false;
    const urgencyRoot = el.closest("[class*='banner'], [class*='promo'], [class*='sale'], [class*='offer'], [class*='deal'], header, aside") || el.parentElement;
    const urgencyText = (urgencyRoot && urgencyRoot.textContent) || "";
    return /sale|deal|off|discount|limited|hurry|ends|today|only|left/i.test(urgencyText);
  }
  const countdownsSeen = new WeakSet();
  function scanCountdowns() {
    if (!config.darkPatterns) return;
    for (const el of all(COUNTDOWN_SELECTOR)) {
      if (countdownsSeen.has(el)) continue;
      countdownsSeen.add(el);
      if (looksLikeSalesCountdown(el)) warn(el, "false urgency countdown — likely resets on refresh", "noah-dp-countdown-warn");
    }
  }

  // ── 3. Confirm-shaming language ───────────────────────────────────────────
  const SHAME_PATTERNS = [
    /no.{0,15}(hate|don.?t want|prefer not|i.?d rather)/i,
    /no thanks,.{0,30}(money|savings|deals|free|discount)/i,
    /i (hate|don.?t like|prefer not to) (save|get|have|receive|learn)/i,
    /i.?d rather (pay|miss|not|stay)/i,
    /not interested in (saving|deals|offers|learning|improving)/i,
    /no.{0,8}i.?m (fine|okay|good) (paying|without|spending)/i,
    /keep (paying|spending) (full|more)/i,
  ];
  const shameSeen = new WeakSet();
  function scanConfirmShaming() {
    if (!config.darkPatterns) return;
    // Shaming text sits on a choice: a button, a link, or a label.
    for (const el of all("a, button, label, [role='button']")) {
      if (shameSeen.has(el)) continue;
      shameSeen.add(el);
      const text = (el.textContent || "").trim();
      if (!text || text.length > 120) continue;
      if (SHAME_PATTERNS.some((p) => p.test(text))) warn(el, "confirm-shaming language detected", "");
    }
  }

  // ── 4. Roach motel unsubscribe patterns ──────────────────────────────────
  const ROACH_SELECTOR = "a[href*='unsubscribe'], a[href*='cancel'], a[href*='opt-out'], a[href*='optout'], a[href*='manage-preferences']";
  const roachSeen = new WeakSet();
  function scanRoachMotel() {
    if (!config.darkPatterns) return;
    for (const link of all(ROACH_SELECTOR)) {
      if (roachSeen.has(link)) continue;
      roachSeen.add(link);
      const style = window.getComputedStyle(link);
      const fontSize = parseFloat(style.fontSize) || 14;
      const opacity = parseFloat(style.opacity) || 1;
      if (fontSize < 10 || opacity < 0.3) {
        link.style.setProperty("font-size", "12px", "important");
        link.style.setProperty("opacity", "1", "important");
        link.style.setProperty("color", "#a9cf9f", "important");
        link.style.setProperty("text-decoration", "underline", "important");
        warn(link, "buried cancel link surfaced", "noah-dp-uncheck-notice");
      }
    }
  }

  // ── 5. Fake price anchoring strikethroughs ────────────────────────────────
  const STRIKE_SELECTOR = "s, del, [class*='original-price'], [class*='was-price'], [class*='list-price'], [class*='compare-at']";
  const priceSeen = new WeakSet();
  function scanFakePricing() {
    if (!config.darkPatterns) return;
    for (const el of all(STRIKE_SELECTOR)) {
      if (priceSeen.has(el)) continue;
      priceSeen.add(el);
      const originalMatch = (el.textContent || "").match(/[\d,.]+/);
      if (!originalMatch) continue;
      const originalPrice = parseFloat(originalMatch[0].replace(/,/g, ""));
      if (!originalPrice) continue;
      const container = el.closest("[class*='price'], [class*='pricing'], li, .product, [class*='card']") || el.parentElement;
      if (!container) continue;
      const priceEls = container.querySelectorAll("[class*='sale'], [class*='current'], [class*='now'], [class*='discounted'], [class*='our-price'], [class*='offer-price']");
      for (const priceEl of priceEls) {
        const currentMatch = (priceEl.textContent || "").match(/[\d,.]+/);
        if (!currentMatch) continue;
        const currentPrice = parseFloat(currentMatch[0].replace(/,/g, ""));
        if (!currentPrice || currentPrice >= originalPrice) continue;
        const discount = 1 - (currentPrice / originalPrice);
        if (discount > 0.6) {
          warn(el, `${Math.round(discount * 100)}% off claim — verify original price`, "noah-dp-countdown-warn");
          break;
        }
      }
    }
  }

  // ── 6. Hidden subscription triggers ─────────────────────────────────────
  const buttonsSeen = new WeakSet();
  function scanHiddenSubscriptions() {
    if (!config.darkPatterns) return;
    for (const btn of all("button, a, input[type='submit']")) {
      if (buttonsSeen.has(btn)) continue;
      buttonsSeen.add(btn);
      const text = (btn.textContent || btn.value || "").trim();
      if (!/free trial|start free|try free|get free/i.test(text)) continue;
      const container = btn.closest("section, .cta, [class*='pricing'], [class*='plan'], form") || btn.parentElement;
      if (!container) continue;
      const finePrint = container.querySelectorAll("p, span, small, .fine-print, [class*='disclaimer'], [class*='terms']");
      for (const fp of finePrint) {
        const fpText = fp.textContent || "";
        if (/(?:after|then|billed|charged|per month|per year|\$\d|credit card)/i.test(fpText) && fpText.length < 300) {
          const fpSize = parseFloat(window.getComputedStyle(fp).fontSize) || 14;
          if (fpSize < 12) {
            fp.style.setProperty("font-size", "12px", "important");
            fp.style.setProperty("opacity", "1", "important");
            warn(btn, "auto-billing after trial — read terms below", "noah-dp-countdown-warn");
            break;
          }
        }
      }
    }
  }

  // querySelectorAll that never throws and skips the shield's own elements.
  function all(selector) {
    let list;
    try { list = document.querySelectorAll(selector); } catch { return []; }
    if (!pace) return list;
    const out = [];
    for (const el of list) if (!pace.isOwn(el)) out.push(el);
    return out;
  }

  // ── scan orchestration ────────────────────────────────────────────────────
  function scanAll() {
    if (!config.darkPatterns || document.hidden) return;
    scanPreTicked();
    scanCountdowns();
    scanConfirmShaming();
    scanRoachMotel();
    scanFakePricing();
    scanHiddenSubscriptions();
  }

  let watcher = null;
  function begin() {
    scanAll();
    if (pace) watcher = pace.watch(scanAll, { delay: 1500, settledDelay: 6000, maxRuns: 40 });
    else {
      let timer = null;
      const mo = new MutationObserver(() => { if (!timer) timer = setTimeout(() => { timer = null; scanAll(); }, 1500); });
      mo.observe(document.documentElement, { childList: true, subtree: true });
      watcher = { stop: () => mo.disconnect() };
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin, { once: true });
  else begin();

  api.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "dark.set" && msg.config) {
      config = { ...config, ...msg.config };
      if (!config.darkPatterns && watcher) watcher.stop();
      else scanAll();
    }
  });
})();
