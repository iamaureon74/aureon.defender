// Every floating shield panel can be moved: press its title bar and drag.
// A short press is still a click (the panel's own buttons keep working); the
// panel stays fully on screen; double-click the title bar to send it home.
// Where each kind of panel was put is remembered for every site.
(() => {
  if (window.__noahShieldDrag) return;
  const api = globalThis.chrome ?? globalThis.browser;
  let saved = null;
  const ready = new Promise((resolve) => {
    try { api.storage.local.get("panelPos").then((got) => { saved = got.panelPos || {}; resolve(); }, () => { saved = {}; resolve(); }); } catch { saved = {}; resolve(); }
  });

  function place(target, left, top) {
    const rect = target.getBoundingClientRect();
    const maxLeft = Math.max(0, window.innerWidth - Math.min(rect.width, window.innerWidth) );
    const maxTop = Math.max(0, window.innerHeight - Math.min(rect.height, 48));
    const x = Math.round(Math.min(maxLeft, Math.max(0, left)));
    const y = Math.round(Math.min(maxTop, Math.max(0, top)));
    target.style.setProperty("left", x + "px", "important");
    target.style.setProperty("top", y + "px", "important");
    target.style.setProperty("right", "auto", "important");
    target.style.setProperty("bottom", "auto", "important");
    target.style.setProperty("position", "fixed", "important");
    return { x, y };
  }

  function remember(kind, value) {
    if (!saved) return;
    if (value) saved[kind] = Object.assign({}, saved[kind], value); else delete saved[kind];
    try { api.storage.local.set({ panelPos: saved }); } catch {}
  }
  function patch(kind, obj) {
    if (!saved) return;
    saved[kind] = Object.assign({}, saved[kind], obj);
    try { api.storage.local.set({ panelPos: saved }); } catch {}
  }
  function savedFor(kind) { return (saved && saved[kind]) || null; }

  window.__noahShieldDrag = function drag(target, handle, kind) {
    if (!target || !handle || handle.__noahDrag) return;
    handle.__noahDrag = true;
    handle.style.cursor = "grab";
    handle.style.touchAction = "none";
    handle.style.userSelect = "none";
    if (!handle.title) handle.title = "drag to move · double-click to put back";
    let start = null, moved = false, justDragged = false;
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest && event.target.closest("button, a, input, select, textarea, label")) return;
      const rect = target.getBoundingClientRect();
      start = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, id: event.pointerId };
      moved = false;
    });
    // Once pressed, the pointer is followed on the whole document: a quick
    // flick leaves the title bar before the first move arrives.
    const move = (event) => {
      if (!start) return;
      const dx = event.clientX - start.x, dy = event.clientY - start.y;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      if (!moved) { moved = true; handle.style.cursor = "grabbing"; document.documentElement.style.userSelect = "none"; }
      place(target, start.left + dx, start.top + dy);
      event.preventDefault();
    };
    const end = () => {
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointerup", end, true);
      document.removeEventListener("pointercancel", end, true);
      document.documentElement.style.userSelect = "";
      if (!start) return;
      if (moved) {
        const rect = target.getBoundingClientRect();
        remember(kind, { x: rect.left / window.innerWidth, y: rect.top / window.innerHeight });
        justDragged = true;
        setTimeout(() => { justDragged = false; }, 0);
      }
      handle.style.cursor = "grab";
      start = null;
    };
    handle.addEventListener("pointerdown", () => {
      if (!start) return;
      document.addEventListener("pointermove", move, true);
      document.addEventListener("pointerup", end, true);
      document.addEventListener("pointercancel", end, true);
    });
    handle.addEventListener("click", (event) => { if (justDragged) { event.stopPropagation(); event.preventDefault(); } }, true);
    handle.addEventListener("dblclick", (event) => {
      if (event.target.closest && event.target.closest("button, a, input")) return;
      for (const prop of ["left", "top", "right", "bottom"]) target.style.removeProperty(prop);
      remember(kind, null);
    });
    ready.then(() => {
      const spot = saved && saved[kind];
      if (spot) requestAnimationFrame(() => place(target, spot.x * window.innerWidth, spot.y * window.innerHeight));
    });
    window.addEventListener("resize", () => {
      if (!target.isConnected || !target.style.left) return;
      const rect = target.getBoundingClientRect();
      place(target, rect.left, rect.top);
    });
  };

  // Full floating treatment for any overlay: draggable (above), plus collapse
  // and scale, each remembered per site. opts.collapse(target, collapsed) lets
  // the overlay decide what "collapsed" hides; by default it keeps the handle
  // and hides the rest. Scale is ctrl/⌘ + wheel over the overlay, or opts hooks.
  window.__noahShieldFloat = function float(target, handle, kind, opts = {}) {
    if (!target || target.__noahFloat) return;
    target.__noahFloat = true;
    window.__noahShieldDrag(target, handle || target, kind);

    const applyScale = (s) => {
      s = Math.max(0.6, Math.min(1.8, s));
      target.style.setProperty("transform", "scale(" + s.toFixed(3) + ")", "important");
      target.style.setProperty("transform-origin", "left top", "important");
      target.__noahScale = s;
      return s;
    };
    const applyCollapsed = (c) => {
      target.__noahCollapsed = c;
      if (typeof opts.collapse === "function") opts.collapse(target, c);
      else for (const child of target.children) if (child !== handle && !child.__noahKeep) child.hidden = c;
      target.setAttribute("data-noah-collapsed", c ? "1" : "0");
    };

    // scale by ctrl/⌘ + wheel
    target.addEventListener("wheel", (event) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const next = applyScale((target.__noahScale || 1) + (event.deltaY < 0 ? 0.08 : -0.08));
      patch(kind, { scale: next });
    }, { passive: false });

    // restore remembered scale + collapsed
    ready.then(() => {
      const spot = savedFor(kind);
      if (spot && spot.scale) applyScale(spot.scale);
      if (spot && spot.collapsed) applyCollapsed(true);
    });

    return {
      toggleCollapsed() { const c = !target.__noahCollapsed; applyCollapsed(c); patch(kind, { collapsed: c }); return c; },
      setScale(s) { const v = applyScale(s); patch(kind, { scale: v }); return v; },
      scaleBy(d) { const v = applyScale((target.__noahScale || 1) + d); patch(kind, { scale: v }); return v; },
      reset() { for (const prop of ["left", "top", "right", "bottom", "transform"]) target.style.removeProperty(prop); applyCollapsed(false); target.__noahScale = 1; remember(kind, null); }
    };
  };
})();
