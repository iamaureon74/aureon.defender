// YouTube ad removal, in the page's own world, by pattern.
//
// How YouTube serves ads: the ad slots arrive inside the data the player
// reads — the first page payload (ytInitialPlayerResponse / ytInitialData)
// and the later /youtubei/v1/{player,next,browse} replies. The watch-the-whole-
// ad behaviour happens when an ad is scheduled in that data and the player
// acts on it. So the shield removes the ad fields *before the player reads
// them*: it wraps JSON.parse and Response.json/text at document_start — before
// any YouTube script runs — and prunes keys that match ad patterns. Because it
// matches by pattern, a renamed ad field is still caught, and because the ad
// is gone from the data, there is no failed ad request for YouTube to notice.
//
// The "ad blockers are not allowed" wall is itself a renderer in that data; it
// is pruned the same way. Nothing here blocks a network request, so there is
// no adblock signal; the ISO-world script mutes and skips anything that still
// slips through.
//
// The patterns are data: a built-in set, plus any the shield's settings add,
// so the list can grow as YouTube changes without a new build.
(() => {
  "use strict";
  if (!/(^|\.)youtube(-nocookie)?\.com$/.test(location.hostname) && !/(^|\.)youtube\.com$/.test(location.hostname)) return;

  // Keys whose whole value is ad scheduling: removing them unschedules the ad.
  // Anchored, lowercased comparison; extendable from settings.
  let AD_KEYS = [
    "adplacements", "adslots", "playerads", "adbreakheartbeatparams",
    "adparams", "adsignalsinfo", "adplacementrenderer", "instreamadplayeroverlayrenderer",
    "playerlegacydesktopwatchadsrenderer", "ads", "adgcovid",
  ];
  // Renderer/message keys that carry the "turn off your ad blocker" wall.
  let ENFORCE = /enforcementmessage|adblock|ad_block|abd_|pagelevelbuttonsrenderer.*enforcement/i;
  // Containers worth walking: a payload is YouTube data only if it has one of these.
  const MARKERS = ["responsecontext", "playabilitystatus", "streamingdata", "playerads", "adplacements", "contents", "oncontextmenuendpoints", "playerresponse", "ytinitial"];
  const MAX_DEPTH = 14;

  const seenNovel = new Set();
  function reportNovel(key) {
    const k = String(key).slice(0, 60);
    if (seenNovel.has(k)) return;
    seenNovel.add(k);
    try { window.postMessage({ __ns_yt: { novel: k } }, location.origin); } catch {}
  }

  function isAdKey(key) {
    const k = String(key).toLowerCase();
    if (AD_KEYS.includes(k)) return true;
    // pattern net: a key that is exactly/decorated "ad(s)" or starts with "ad" + a word
    // seen in ad containers, caught so renamed fields still match
    if (/^player.*ads?$/.test(k) || /^ad[a-z]*(placement|slot|break|renderer|params|overlay)/.test(k)) return true;
    return false;
  }

  // Walk an object graph; delete ad keys and enforcement renderers in place.
  // Returns how many were pruned. Bounded in depth, skips primitives fast.
  function prune(node, depth, hits) {
    if (!node || typeof node !== "object" || depth > MAX_DEPTH) return;
    if (Array.isArray(node)) {
      for (let i = node.length - 1; i >= 0; i--) {
        const item = node[i];
        if (item && typeof item === "object") {
          // drop an array entry that is itself an enforcement/ad renderer
          const keys = Object.keys(item);
          if (keys.some((k) => ENFORCE.test(k) || isAdKey(k) && item[k] && typeof item[k] === "object" && keys.length <= 2)) {
            node.splice(i, 1); hits.n++;
            continue;
          }
          prune(item, depth + 1, hits);
        }
      }
      return;
    }
    for (const key of Object.keys(node)) {
      if (isAdKey(key)) {
        delete node[key]; hits.n++;
        if (!["adplacements", "adslots", "playerads", "ads", "adbreakheartbeatparams"].includes(key.toLowerCase())) reportNovel(key);
        continue;
      }
      if (ENFORCE.test(key)) { delete node[key]; hits.n++; continue; }
      const value = node[key];
      if (value && typeof value === "object") prune(value, depth + 1, hits);
    }
  }

  function looksLikeYouTubeData(obj) {
    if (!obj || typeof obj !== "object") return false;
    const keys = Object.keys(obj).map((k) => k.toLowerCase());
    for (const m of MARKERS) if (keys.includes(m)) return true;
    // nested common wrapper
    return keys.includes("playerresponse") || keys.includes("response");
  }

  let totalPruned = 0;
  function cleanse(obj) {
    if (!looksLikeYouTubeData(obj)) return obj;
    const hits = { n: 0 };
    try { prune(obj, 0, hits); } catch {}
    if (hits.n) { totalPruned += hits.n; try { window.postMessage({ __ns_yt: { pruned: hits.n } }, location.origin); } catch {} }
    return obj;
  }

  // ---- wrap JSON.parse (the first-page payloads go through here) ----------------------------
  const rawParse = JSON.parse;
  const parseWrap = function parse(text, reviver) {
    const result = rawParse.call(this, text, reviver);
    if (result && typeof result === "object") {
      // quick reject: only strings mentioning an ad/marker are worth walking
      if (typeof text !== "string" || /ad[A-Za-z]*(Placement|Slot|Break|s"\s*:)|playerAds|enforcement|streamingData|playabilityStatus/i.test(text)) cleanse(result);
    }
    return result;
  };
  // report native source, so a toString check does not reveal the wrapper
  try {
    const src = Function.prototype.toString.call(rawParse);
    Object.defineProperty(parseWrap, "toString", { value: () => src, configurable: true });
    Object.defineProperty(parseWrap, "name", { value: "parse", configurable: true });
    Object.defineProperty(parseWrap, "length", { value: rawParse.length, configurable: true });
  } catch {}
  try { JSON.parse = parseWrap; } catch {}

  // ---- wrap Response.json / Response.text (the youtubei api replies) -------------------------
  function wrapResponse(proto) {
    if (!proto) return;
    for (const method of ["json", "text"]) {
      const orig = proto[method];
      if (typeof orig !== "function") continue;
      const wrapped = function () {
        const url = (() => { try { return this.url || ""; } catch { return ""; } })();
        const youtubey = /youtubei\/v1\/(player|next|browse|reel|guide)|\/watch|get_video_info/.test(url) || !url;
        return orig.apply(this, arguments).then((data) => {
          if (!youtubey) return data;
          if (method === "json") { try { cleanse(data); } catch {} return data; }
          // text: only reparse if it smells of ads
          if (typeof data === "string" && /adPlacements|playerAds|adSlots|enforcement/i.test(data)) {
            try { const obj = rawParse(data); cleanse(obj); return JSON.stringify(obj); } catch { return data; }
          }
          return data;
        });
      };
      try {
        const src = Function.prototype.toString.call(orig);
        Object.defineProperty(wrapped, "toString", { value: () => src, configurable: true });
        Object.defineProperty(wrapped, "name", { value: method, configurable: true });
      } catch {}
      try { proto[method] = wrapped; } catch {}
    }
  }
  wrapResponse(typeof Response !== "undefined" && Response.prototype);

  // ---- accept pattern updates from the isolated-world youtube script -------------------------
  window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data || !event.data.__ns_yt_cfg) return;
    const cfg = event.data.__ns_yt_cfg;
    if (Array.isArray(cfg.adKeys)) AD_KEYS = [...new Set(AD_KEYS.concat(cfg.adKeys.map((k) => String(k).toLowerCase())))];
    if (typeof cfg.enforce === "string") { try { ENFORCE = new RegExp(cfg.enforce, "i"); } catch {} }
    // re-cleanse the already-parsed first payload if the player has not read it yet
    try { if (window.ytInitialPlayerResponse) cleanse(window.ytInitialPlayerResponse); } catch {}
    try { if (window.ytInitialData) cleanse(window.ytInitialData); } catch {}
  });
})();
