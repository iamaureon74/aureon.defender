// Downloader: notices the media a page shows (video, audio, pictures,
// documents) so the downloader panel can offer them. Performance notes
// (v10.2): this used to rescan the whole document and message the worker
// with the full list on every DOM change, with no delay, which was the
// single heaviest thing the shield did on busy pages. Now it scans once the
// page is idle, rescans through the shared pace watcher a few seconds apart,
// sends only what is new, and stops growing past a few hundred items.
(() => {
  "use strict";
  if (window.top !== window) return;
  const api = globalThis.chrome ?? globalThis.browser;
  const pace = window.__noahPace;

  const MAX_ITEMS = 400;
  const _found = new Map(); // url → item
  let _unsent = [];

  function guessType(url) {
    const u = url.split("?")[0].toLowerCase();
    if (/\.(mp4|webm|mkv|mov|avi|m3u8|mpd|m4v)$/.test(u)) return "video";
    if (/\.(mp3|wav|ogg|flac|aac|m4a|opus|weba)$/.test(u)) return "audio";
    if (/\.(jpg|jpeg|png|gif|webp|svg|avif|bmp)$/.test(u)) return "image";
    if (/\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z)$/.test(u)) return "document";
    return null;
  }

  function guessMime(url) {
    const u = url.split("?")[0].toLowerCase();
    if (/\.mp4$/.test(u)) return "video/mp4";
    if (/\.webm$/.test(u)) return "video/webm";
    if (/\.mp3$/.test(u)) return "audio/mpeg";
    if (/\.png$/.test(u)) return "image/png";
    if (/\.jpg$|\.jpeg$/.test(u)) return "image/jpeg";
    if (/\.gif$/.test(u)) return "image/gif";
    if (/\.webp$/.test(u)) return "image/webp";
    if (/\.pdf$/.test(u)) return "application/pdf";
    if (/\.m3u8$/.test(u)) return "application/x-mpegURL";
    return "";
  }

  function guessFilename(url) {
    try {
      const path = new URL(url).pathname;
      const name = path.split("/").filter(Boolean).pop() || "download";
      return decodeURIComponent(name).slice(0, 120);
    } catch { return "download"; }
  }

  function addItem(url) {
    if (!url || _found.size >= MAX_ITEMS) return;
    if (typeof url !== "string" || !/^https?:/.test(url) || _found.has(url)) return;
    const type = guessType(url);
    if (!type) return;
    const item = { url, type, mimeType: guessMime(url), filename: guessFilename(url) };
    _found.set(url, item);
    _unsent.push(item);
  }

  function scanDom() {
    if (document.hidden) return;
    document.querySelectorAll("video[src], video > source[src], audio[src], audio > source[src]").forEach((el) => addItem(el.src || el.getAttribute("src")));
    // Pictures: only ones big enough to be worth saving; icons and pixels are noise.
    document.querySelectorAll("img[src]").forEach((el) => { if ((el.naturalWidth || el.width || 0) >= 200 || (el.naturalHeight || el.height || 0) >= 200) addItem(el.src); });
    document.querySelectorAll("a[href$='.mp4'], a[href$='.webm'], a[href$='.mp3'], a[href$='.pdf'], a[href$='.zip'], a[href*='.m3u8'], a[href$='.docx'], a[href$='.xlsx'], a[href$='.pptx']").forEach((el) => addItem(el.href));
    document.querySelectorAll('meta[property="og:video"], meta[property="og:image"], meta[property="og:audio"]').forEach((el) => addItem(el.content));
    document.querySelectorAll("[data-video-src], video[data-src], source[data-src]").forEach((el) => addItem(el.getAttribute("data-video-src") || el.getAttribute("data-src")));
    flush();
  }

  function flush() {
    if (!_unsent.length) return;
    const items = _unsent;
    _unsent = [];
    try {
      api.runtime.sendMessage({ type: "downloader.found", items }, () => { void api.runtime.lastError; });
    } catch { /* worker asleep; the panel asks again when opened */ }
  }

  const begin = () => {
    const idle = pace ? pace.idle : (fn) => setTimeout(fn, 0);
    idle(scanDom, 3000);
    if (pace) pace.watch(scanDom, { delay: 4000, settledDelay: 10000, maxRuns: 30 });
    else {
      let timer = null;
      new MutationObserver(() => { if (!timer) timer = setTimeout(() => { timer = null; scanDom(); }, 4000); })
        .observe(document.documentElement, { childList: true, subtree: true });
    }
  };
  if (document.readyState === "complete") setTimeout(begin, 1500);
  else window.addEventListener("load", () => setTimeout(begin, 1500), { once: true });

  // The panel asks for a fresh look when it opens.
  api.runtime.onMessage.addListener((msg, sender, reply) => {
    if (msg && msg.type === "downloader.scan") {
      _unsent = [];
      _found.clear();
      scanDom();
      reply({ items: [..._found.values()] });
      return true;
    }
    return false;
  });
})();
