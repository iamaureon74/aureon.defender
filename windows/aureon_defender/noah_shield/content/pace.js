// Pace: one place for the content scripts to watch the page without slowing
// it down. Every script used to run its own MutationObserver and rescan the
// whole document on every change, some with no delay at all; on busy pages
// (feeds, editors, video sites) that was dozens of full-page scans a second,
// each forcing layout. This file gives them a shared, budgeted watcher:
//
//   - a callback runs at most once per `delay` ms, in idle time;
//   - nothing runs while the tab is hidden;
//   - once the page has settled (20 s after load) the delay grows, because a
//     banner or a wall shows up early and a feed scrolling forever does not;
//   - the shield's own elements never trigger a rescan, so a script cannot
//     wake itself up by touching the page.
//
// Loaded first, at document_start, in the isolated world shared by all of
// the shield's content scripts. Scripts fall back to their own timer if it
// is somehow missing.
(() => {
  "use strict";
  if (window.__noahPace) return;

  let lastInput = 0;
  const noteInput = () => { lastInput = Date.now(); };
  for (const type of ["pointerdown", "keydown", "touchstart", "wheel"]) {
    window.addEventListener(type, noteInput, { capture: true, passive: true });
  }

  const OWN = /^(NOAH-SHIELD|NS-[0-9A-F]{8})-/;
  const isOwn = (node) => {
    let element = node && node.nodeType === 1 ? node : node && node.parentElement;
    for (let depth = 0; element && depth < 6; depth++, element = element.parentElement) {
      if (OWN.test(element.tagName) || element.id === "__noah_cognition_pill" || element.dataset && element.dataset.noah) return true;
    }
    return false;
  };

  const idle = (fn, timeout) => {
    if (typeof requestIdleCallback === "function") requestIdleCallback(() => fn(), { timeout });
    else setTimeout(fn, 0);
  };

  const started = Date.now();

  // watch(callback, options) -> { stop() }
  //   delay: ms between runs while the page is young (default 1000)
  //   settledDelay: ms between runs after `settleAfter` ms (default 4000)
  //   settleAfter: ms after which the page counts as settled (default 20000)
  //   target: node to observe (default documentElement)
  //   attributes: watch attribute changes too (default false; expensive)
  //   maxRuns: stop for good after this many runs (default unlimited)
  function watch(callback, options = {}) {
    const delay = options.delay ?? 1000;
    const settledDelay = options.settledDelay ?? Math.max(delay, 4000);
    const settleAfter = options.settleAfter ?? 20000;
    const maxRuns = options.maxRuns ?? Infinity;
    let pending = null;
    let runs = 0;
    let stopped = false;
    const run = () => {
      pending = null;
      if (stopped) return;
      if (document.hidden) { pending = setTimeout(run, 5000); return; }
      runs++;
      idle(() => { try { callback(); } catch { /* a script's problem, not the page's */ } }, 1500);
      if (runs >= maxRuns) stop();
    };
    const observer = new MutationObserver((mutations) => {
      if (pending || stopped) return;
      let relevant = false;
      for (const mutation of mutations) {
        if (!isOwn(mutation.target)) { relevant = true; break; }
      }
      if (!relevant) return;
      const wait = Date.now() - started > settleAfter ? settledDelay : delay;
      pending = setTimeout(run, wait);
    });
    const start = () => {
      const target = options.target || document.documentElement;
      if (!target) return;
      observer.observe(target, { childList: true, subtree: true, attributes: Boolean(options.attributes), attributeFilter: options.attributeFilter });
    };
    const stop = () => { stopped = true; observer.disconnect(); if (pending) clearTimeout(pending); pending = null; };
    start();
    return { stop };
  }

  window.__noahPace = {
    watch,
    idle,
    isOwn,
    // Did the person click, type or scroll within the last `ms` milliseconds?
    inputWithin: (ms) => lastInput && Date.now() - lastInput < ms,
    lastInput: () => lastInput,
    age: () => Date.now() - started,
  };
})();
