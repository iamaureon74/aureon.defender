// Annoyances: cookie banners rejected, overlays and newsletter walls
// removed, autoplay stopped, fake countdowns flagged, copying and right-click
// unblocked, and a dark mode for sites that lack one.
//
// Performance notes (v10.2): every pass used to read innerText and computed
// style for thousands of elements on every DOM change, which froze busy
// pages. Passes now read textContent (no layout), look at a small pool of
// candidates, run through the shared pace watcher, and leave alone anything
// the person opened themselves (an image lightbox, a menu, a dialog).
(() => {
  "use strict";
  if (window.top !== window && !/consent|cookie|privacy|cmp|sourcepoint|didomi|quantcast|onetrust|trustarc|usercentrics/i.test(location.href)) return;
  const api = globalThis.chrome ?? globalThis.browser;
  const pace = window.__noahPace;
  const send = (message) => new Promise((resolve) => {
    try { api.runtime.sendMessage(message, (response) => { void api.runtime.lastError; resolve(response || {}); }); } catch { resolve({}); }
  });
  // textContent, never innerText: innerText forces a layout for every call.
  const text = (node) => (node && node.textContent || "").replace(/\s+/g, " ").trim();

  function waitForConfig() {
    return new Promise((resolve) => {
      if (window.__noahShieldSiteConfig) return resolve(window.__noahShieldSiteConfig);
      document.addEventListener("noah-shield:site-config", () => resolve(window.__noahShieldSiteConfig), { once: true });
      setTimeout(() => resolve(window.__noahShieldSiteConfig || null), 4000);
    });
  }
  function visible(element) {
    if (!element || !element.isConnected) return false;
    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || parseFloat(style.opacity) === 0) return false;
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }
  const userBusy = () => pace ? pace.inputWithin(2500) : false;

  // ---- cookie banners: "reject all" first, then the known consent managers ----------
  const REJECT_SELECTORS = [
    "#onetrust-reject-all-handler", ".onetrust-close-btn-handler", "#CybotCookiebotDialogBodyButtonDecline", "#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
    "#didomi-notice-disagree-button", ".didomi-continue-without-agreeing", "#truste-consent-required", ".truste-button2", "#uc-btn-deny-banner", "button[data-testid='uc-deny-all-button']",
    ".cmpboxbtnno", "#cmpwelcomebtnno", ".sp_choice_type_13", "button[title='Reject All']", "button[title='Reject all']", ".qc-cmp2-summary-buttons button[mode='secondary']",
    "#cookie-banner .reject", ".cc-btn.cc-deny", ".cc-deny", "button#rejectAll", "button.reject-all", "[data-cookiebanner='reject_button']", "#consent-reject-all", ".js-reject-cookies",
    "button[aria-label='Reject all']", "button[aria-label='Reject All']", "#W0wltc", "button.fc-cta-do-not-consent", ".fc-cta-do-not-consent",
  ];
  const REJECT_TEXT = /^(reject( all)?|decline( all)?|refuse( all)?|only (necessary|essential|required)( cookies)?|necessary (cookies )?only|essential only|continue without (accepting|agreeing)|do not (accept|consent|sell)|no,? thanks|disagree( and close)?|alle ablehnen|ablehnen|nur notwendige|tout refuser|refuser|rechazar( todo)?|rifiuta( tutto)?|weigeren|alles afwijzen|odrzuć( wszystkie)?|отклонить( все)?|拒绝(全部)?|全部拒绝|すべて拒否|拒否|모두 거부|거부|recusar( tudo)?|rejeitar( todos)?|avvis(a|e)( alla)?|afvis( alle)?|hylkää( kaikki)?|reddet|tümünü reddet|odmítnout( vše)?|elutasít(om|ás)?|respinge( tot)?|απόρριψη( όλων)?|رفض( الكل)?|सभी अस्वीकार करें|अस्वीकार)$/i;
  const CMP_HINT = /cookie|consent|privacy|gdpr|tracking|personalis|personaliz|datenschutz|zustimm|çerez|куки|印象|クッキー|쿠키|隐私|隱私/i;
  let bannerDone = false;
  function rejectBanner() {
    if (bannerDone) return;
    for (const selector of REJECT_SELECTORS) {
      const button = document.querySelector(selector);
      if (button && visible(button)) {
        button.click();
        bannerDone = true;
        window.__noahShieldBannerDone = true;
        send({ type: "safety.event", kind: "banners", amount: 1 });
        return;
      }
    }
    // Text first (a cheap string test), visible() only for the few that match.
    const buttons = Array.from(document.querySelectorAll("button, a[role='button'], input[type='button'], input[type='submit'], [role='button']"))
      .filter((element) => REJECT_TEXT.test(text(element) || element.value || "") && visible(element));
    for (const button of buttons) {
      const container = button.closest("[class*='cookie' i], [id*='cookie' i], [class*='consent' i], [id*='consent' i], [class*='cmp' i], [id*='cmp' i], [class*='gdpr' i], [id*='gdpr' i], [class*='privacy' i], [id*='privacy' i], [aria-label*='cookie' i], [aria-modal='true'], dialog, [role='dialog']");
      if (!container || !CMP_HINT.test(text(container).slice(0, 600))) continue;
      button.click();
      bannerDone = true;
      window.__noahShieldBannerDone = true;
      send({ type: "safety.event", kind: "banners", amount: 1 });
      return;
    }
    // A banner with only "accept" and "settings": open settings, save without consent.
    const settingsButton = Array.from(document.querySelectorAll("button, a")).find((element) => /^(manage|cookie|customi[sz]e|more) (settings|preferences|options|choices)$|^(settings|preferences|customi[sz]e)$/i.test(text(element)) && visible(element) && CMP_HINT.test(text(element.closest("[class*='cookie' i], [id*='cookie' i], [class*='consent' i], [id*='consent' i], dialog, [role='dialog']") || document.body).slice(0, 600)));
    if (settingsButton && !settingsButton.dataset.noahTried) {
      settingsButton.dataset.noahTried = "1";
      settingsButton.click();
      setTimeout(() => {
        const save = Array.from(document.querySelectorAll("button")).find((element) => /^(save( (my )?(settings|preferences|choices))?|confirm( my)? choices|reject all|allow (necessary|selection)|save and (exit|close))$/i.test(text(element)) && visible(element));
        if (save) { save.click(); bannerDone = true; window.__noahShieldBannerDone = true; send({ type: "safety.event", kind: "banners", amount: 1 }); }
      }, 900);
    }
  }

  // ---- overlays and walls ---------------------------------------------------------------
  const WALL = /subscribe|newsletter|sign up|signup|create (a |an )?(free )?account|log in to continue|register to continue|continue reading|you've reached|articles? left|support (our|independent) journalism|become a member|unlock (this|unlimited)|premium|paywall|already a subscriber|get unlimited access|enable notifications|turn on notifications|download (the|our) app|open in (the )?app|install (the|our) app/i;
  const KEEP = /cookie|consent|gdpr|privacy|checkout|payment|cart|sign in|log in$|login|password|captcha|verify|search/i;
  const handledOverlays = new WeakSet();
  // A lightbox, a video player, a map or a gallery is something the person
  // opened on purpose: a big picture or frame inside the overlay says so.
  function looksLikeViewer(element) {
    const media = element.querySelectorAll("img, video, picture, canvas, iframe, svg, figure, [role='img']");
    for (const item of media) {
      const box = item.getBoundingClientRect();
      if (box.width >= innerWidth * 0.25 || box.height >= innerHeight * 0.25) return true;
    }
    return element.querySelector("input, textarea, select, [contenteditable='true'], [role='menu'], [role='listbox'], [role='tablist'], nav") !== null;
  }
  function removeOverlays() {
    // Something the person just opened is never a wall.
    if (userBusy()) return;
    const pool = document.querySelectorAll(
      "body > *, " +
      "[class*='overlay' i], [class*='modal' i], [class*='popup' i], [class*='paywall' i], [class*='subscribe' i], [class*='interstitial' i], " +
      "[id*='overlay' i], [id*='modal' i], [id*='popup' i], [id*='paywall' i], " +
      "dialog, [role='dialog'], [aria-modal='true']"
    );
    const walls = [];
    const backdrops = [];
    for (const element of pool) {
      if (handledOverlays.has(element) || (pace && pace.isOwn(element))) continue;
      const style = getComputedStyle(element);
      if (style.position !== "fixed" && style.position !== "sticky" && style.position !== "absolute") continue;
      const zIndex = parseInt(style.zIndex, 10);
      if (!(zIndex >= 100)) continue;
      const box = element.getBoundingClientRect();
      const covers = box.width >= innerWidth * 0.6 && box.height >= innerHeight * 0.5;
      if (!covers) continue;
      const words = text(element).slice(0, 1500);
      if (KEEP.test(words)) continue;
      if (looksLikeViewer(element)) continue;
      const isWall = WALL.test(words) && words.length < 1500;
      const isBackdrop = element.children.length <= 2 && words.length < 40 && (style.backgroundColor !== "rgba(0, 0, 0, 0)" || style.backdropFilter !== "none");
      if (isWall) walls.push(element);
      else if (isBackdrop) backdrops.push(element);
    }
    // A bare backdrop goes only when a wall came with it, or when it was
    // there from the start (a wall whose words sit in a sibling, a timed
    // "subscribe" curtain). Later on, a backdrop alone is a menu or a viewer.
    const young = pace ? pace.age() < 12000 : false;
    const candidates = walls.concat(walls.length || young ? backdrops : []);
    if (!candidates.length) return;
    for (const element of candidates) {
      handledOverlays.add(element);
      element.style.setProperty("display", "none", "important");
    }
    // Sites lock scrolling under the wall; give it back.
    for (const element of [document.documentElement, document.body]) {
      if (!element) continue;
      const style = getComputedStyle(element);
      if (style.overflow === "hidden" || style.overflowY === "hidden") element.style.setProperty("overflow", "auto", "important");
      if (style.position === "fixed") element.style.setProperty("position", "static", "important");
    }
    for (const element of document.querySelectorAll("[style*='blur']")) {
      if (/blur\(/.test(element.style.filter) && element.getBoundingClientRect().height > innerHeight * 0.4) element.style.setProperty("filter", "none", "important");
    }
    send({ type: "safety.event", kind: "overlays", amount: candidates.length });
  }

  // ---- autoplay ---------------------------------------------------------------------------
  const mediaSeen = new WeakSet();
  function stopAutoplay() {
    for (const media of document.querySelectorAll("video, audio")) {
      if (mediaSeen.has(media)) continue;
      mediaSeen.add(media);
      let userStartedIt = false;
      const userStarted = () => { userStartedIt = true; };
      media.addEventListener("click", userStarted, true);
      const parent = media.closest("[class*='player' i], [id*='player' i]") || media.parentElement;
      if (parent) parent.addEventListener("click", userStarted, true);
      if (media.autoplay) { media.autoplay = false; media.removeAttribute("autoplay"); }
      const stop = () => {
        if (userStartedIt || userBusy() || (navigator.userActivation && navigator.userActivation.isActive)) return;
        if (!media.paused) { media.pause(); send({ type: "safety.event", kind: "autoplay", amount: 1 }); }
      };
      media.addEventListener("play", () => setTimeout(stop, 50));
      media.addEventListener("loadeddata", stop);
      stop();
    }
  }

  // ---- fake countdowns and urgency ---------------------------------------------------------
  const URGENCY = /(only|just) \d+ left( in stock)?|\d+ (other )?people (are )?(looking|viewing)|(hurry|ends|expires|offer ends?|sale ends?|deal ends?) (in|soon)|\d{1,2}:\d{2}(:\d{2})? (left|remaining)|limited time|selling fast|almost gone|last chance/i;
  const urgencySeen = new WeakSet();
  function flagUrgency() {
    let key;
    try { key = "noah-shield-timer:" + location.pathname; } catch { return; }
    // Text first (pure string work), visible() only for matches.
    const elements = [];
    for (const element of document.querySelectorAll("span, p, b, strong, em, li, td, [class*='urgen' i], [class*='stock' i], [class*='countdown' i], [class*='timer' i]")) {
      if (urgencySeen.has(element) || element.children.length > 3) continue;
      const words = text(element);
      if (words.length < 120 && URGENCY.test(words) && visible(element)) elements.push(element);
      if (elements.length >= 8) break;
    }
    if (!elements.length) return;
    let previous = null;
    try { previous = JSON.parse(sessionStorage.getItem(key) || "null"); } catch { previous = null; }
    const now = elements.map((element) => text(element));
    const timers = now.map((words) => (words.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/) || []).slice(1).filter((part) => part !== undefined).map(Number));
    let reset = false;
    if (previous && previous.timers) {
      // A real countdown is lower than it was; a fake one starts over on reload.
      for (let index = 0; index < Math.min(timers.length, previous.timers.length); index++) {
        const before = previous.timers[index];
        const after = timers[index];
        if (before.length && after.length) {
          const seconds = (parts) => parts.reduce((sum, value) => sum * 60 + value, 0);
          if (seconds(after) >= seconds(before) - 1 && Date.now() - previous.at > 2500) reset = true;
        }
      }
    }
    const origin = Math.round(performance.timeOrigin);
    if (!previous || previous.origin !== origin) {
      try { sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), timers, origin })); } catch { /* fine */ }
    }
    elements.forEach((element, index) => {
      urgencySeen.add(element);
      element.style.setProperty("opacity", "0.55", "important");
      element.title = reset && timers[index] && timers[index].length ? "noah shield: this countdown restarted on reload; it is theatre" : "noah shield: urgency wording, take your time";
      if (reset && timers[index] && timers[index].length) element.style.setProperty("text-decoration", "line-through", "important");
    });
    send({ type: "safety.event", kind: "timers", amount: 1 });
  }

  // ---- copy and right-click ------------------------------------------------------------------
  function unblockCopy() {
    const style = document.createElement("style");
    style.textContent = "* { user-select: text !important; -webkit-user-select: text !important; } ::selection { background: rgba(95,138,88,.4) !important; }";
    (document.head || document.documentElement).append(style);
    for (const type of ["contextmenu", "copy", "cut", "paste", "selectstart", "dragstart", "mousedown", "mouseup", "keydown"]) {
      window.addEventListener(type, (event) => {
        if (type === "keydown" && !(event.ctrlKey || event.metaKey)) return;
        if (type === "mousedown" || type === "mouseup") { if (event.button !== 2) return; }
        event.stopImmediatePropagation();
      }, true);
    }
    for (const attribute of ["oncontextmenu", "oncopy", "oncut", "onpaste", "onselectstart", "ondragstart"]) {
      document.querySelectorAll("[" + attribute + "]").forEach((element) => element.removeAttribute(attribute));
      if (document.body) document.body[attribute] = null;
      document[attribute] = null;
    }
  }

  // ---- dark mode for sites without one ---------------------------------------------------------
  function darkMode() {
    const bodyColor = getComputedStyle(document.body || document.documentElement).backgroundColor;
    const match = /rgba?\((\d+), (\d+), (\d+)/.exec(bodyColor);
    const luminance = match ? (0.2126 * match[1] + 0.7152 * match[2] + 0.0722 * match[3]) / 255 : 1;
    const transparent = /rgba\(0, 0, 0, 0\)/.test(bodyColor);
    if (!transparent && luminance < 0.45) return;
    const style = document.createElement("style");
    style.id = "noah-shield-dark";
    style.textContent = "html { filter: invert(0.92) hue-rotate(180deg) !important; background: #0e0f0e !important; } img, video, picture, canvas, iframe, svg image, [style*='background-image'], .noah-keep { filter: invert(1) hue-rotate(180deg) !important; }";
    (document.head || document.documentElement).append(style);
  }

  waitForConfig().then((config) => {
    if (!config || config.trusted) return;
    const annoyances = config.annoyances || {};
    const isTop = window.top === window;
    const run = () => {
      if (annoyances.banners !== false) rejectBanner();
      if (annoyances.overlays !== false && isTop) removeOverlays();
      if (annoyances.autoplay !== false) stopAutoplay();
      // Urgency wording is part of the page as written; a minute is plenty.
      if (annoyances.timers !== false && isTop && (!pace || pace.age() < 60000)) flagUrgency();
    };
    if (annoyances.copy) unblockCopy();
    if (annoyances.dark) {
      if (document.body) darkMode();
      else document.addEventListener("DOMContentLoaded", darkMode, { once: true });
    }
    const start = () => { run(); setTimeout(run, 1500); setTimeout(run, 4000); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
    if (pace) {
      pace.watch(run, { delay: 1200, settledDelay: 5000 });
    } else {
      let pending = null;
      new MutationObserver(() => {
        if (pending) return;
        pending = setTimeout(() => { pending = null; run(); }, 1500);
      }).observe(document.documentElement, { childList: true, subtree: true });
    }
  });
})();
