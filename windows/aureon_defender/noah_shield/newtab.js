// The new tab page: the picture the person chose, the time, a search box,
// and one line of what the shield did today. Nothing is fetched; the search
// goes to the browser's own engine.
"use strict";
const byId = (id) => document.getElementById(id);

// 12-hour (5:20 pm) or 24-hour (17:20). Until you choose, it follows how your
// computer's language writes the time; click the clock, or the switch in the
// footer, to change it. The choice is kept.
let hour12 = /h1[12]/.test(new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hourCycle || "");
function tick() {
  const now = new Date();
  const two = (n) => String(n).padStart(2, "0");
  const clock = byId("clock");
  if (hour12) {
    const h = now.getHours() % 12 || 12;
    const half = document.createElement("span");
    half.className = "ampm";
    half.textContent = now.getHours() < 12 ? "am" : "pm";
    clock.replaceChildren(`${h}:${two(now.getMinutes())}`, half);
  } else {
    clock.textContent = `${two(now.getHours())}:${two(now.getMinutes())}`;
  }
  clock.title = hour12 ? "switch to 24-hour time" : "switch to 12-hour time";
  clock.setAttribute("aria-label", (hour12 ? "12-hour" : "24-hour") + " clock, " + clock.textContent + ". press to switch");
  const toggle = byId("hour12");
  if (toggle) toggle.checked = hour12;
  byId("day").textContent = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const hour = now.getHours();
  byId("greeting").textContent = hour < 5 ? "rest well" : hour < 12 ? "good morning" : hour < 17 ? "good afternoon" : hour < 21 ? "good evening" : "rest well";
}
async function setHour12(value) {
  hour12 = Boolean(value);
  tick();
  try { await Shield.api.storage.local.set({ clock12: hour12 }); } catch {}
}
byId("clock").addEventListener("click", () => setHour12(!hour12));
byId("clock").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setHour12(!hour12); } });
byId("hour12").addEventListener("change", (event) => setHour12(event.target.checked));
Shield.api.storage.local.get("clock12").then((stored) => { if (typeof stored.clock12 === "boolean") hour12 = stored.clock12; tick(); }).catch(() => {});
tick();
setInterval(tick, 10000);

(async () => {
  const [look, stored] = await Promise.all([Shield.loadLook(), Shield.api.storage.local.get("plainNewTab")]);
  Shield.applyLook(look);
  byId("plain").checked = Boolean(stored.plainNewTab);
  document.body.classList.toggle("plain", Boolean(stored.plainNewTab));
  const url = Shield.lookImageUrl(look);
  const picture = byId("picture");
  if (url) {
    const image = new Image();
    image.onload = () => { picture.style.backgroundImage = `url("${url}")`; picture.classList.add("in"); };
    image.src = url;
  }
  const state = await Shield.send({ type: "stats.today" });
  if (state && state.today) {
    const today = state.today;
    const scams = (today.phishing || 0) + (today.leaks || 0) + (today.keylog || 0) + (today.wallets || 0);
    const parts = [
      [today.trackers, "trackers stopped"],
      [today.upgrades, "pages kept private"],
      [today.lan, "network scans stopped"],
      [(today.cookies || 0) + (today.burned || 0), "cookies cleared"],
      [scams, "scams caught"],
    ].filter(([count]) => count);
    const list = byId("numbers");
    list.replaceChildren(...parts.map(([count, words]) => {
      const item = document.createElement("li");
      const number = document.createElement("b");
      number.textContent = count.toLocaleString();
      item.append(number, words);
      return item;
    }));
    byId("rest").hidden = parts.length === 0;
  }
})();

byId("search").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = byId("query").value.trim();
  if (!text) return;
  const looksLikeAddress = /^(https?:\/\/|[a-z0-9-]+(\.[a-z0-9-]+)+(\/|$))/i.test(text) && !/\s/.test(text);
  if (looksLikeAddress) {
    location.href = /^https?:\/\//i.test(text) ? text : "https://" + text;
    return;
  }
  if (Shield.api.search && Shield.api.search.query) {
    Shield.api.search.query({ text, disposition: "CURRENT_TAB" });
  } else {
    location.href = "https://duckduckgo.com/?q=" + encodeURIComponent(text);
  }
});
byId("change-look").addEventListener("click", (event) => { event.preventDefault(); Shield.api.runtime.openOptionsPage(); });
byId("shield-settings").addEventListener("click", (event) => { event.preventDefault(); Shield.api.runtime.openOptionsPage(); });
byId("plain").addEventListener("change", async (event) => {
  await Shield.api.storage.local.set({ plainNewTab: event.target.checked });
  document.body.classList.toggle("plain", event.target.checked);
});

// Chrome 138+ adds its own footer under extension new tab pages; an extension
// cannot remove it. The hint says once how to hide it, and goes away by itself:
//   - it only shows while the footer is really there: this tab is shorter than
//     the other tabs in the same window (chrome reports each tab's height);
//   - the moment the footer is hidden, this page grows taller; the hint sees
//     that, leaves, and is never shown again;
//   - closing it with × also ends it for good.
(async () => {
  const api = Shield.api;
  const hint = byId("footer-hint");
  if (!hint) return;
  const done = async () => {
    hint.classList.add("leaving");
    setTimeout(() => { hint.hidden = true; }, 220);
    window.removeEventListener("resize", onResize);
    try { await api.storage.local.set({ footerHintSeen: true }); } catch {}
  };
  let baseline = window.innerHeight;
  let outer = window.outerHeight;
  async function footerStillThere() {
    // chrome reports each tab's height: the footer makes this one shorter than its neighbours
    try {
      const self = await api.tabs.getCurrent();
      const others = (await api.tabs.query({ windowId: self.windowId })).filter((tab) => tab.id !== self.id && tab.height && !/^chrome:\/\/newtab|newtab\.html/.test(tab.url || tab.pendingUrl || ""));
      return others.length ? Math.max(...others.map((tab) => tab.height)) - self.height >= 24 : null;
    } catch { return null; }
  }
  function onResize() {
    // the window itself unchanged but the page taller: chrome's footer went away
    const grew = window.innerHeight - baseline;
    const frame = (window.outerHeight - window.innerHeight) - (outer - baseline);
    if (grew >= 24 && frame <= -24) { done(); return; }
    baseline = window.innerHeight;
    outer = window.outerHeight;
    footerStillThere().then((there) => { if (there === false) done(); });
  }
  try {
    const seen = await api.storage.local.get("footerHintSeen");
    if (seen.footerHintSeen) return;
    if (!/Chrome\//.test(navigator.userAgent) || /Edg\/|OPR\/|Brave/.test(navigator.userAgent)) return;
    const footerShown = await footerStillThere();
    if (footerShown === false) { await api.storage.local.set({ footerHintSeen: true }); return; }
    // no other tab to compare with: show it, and the resize check still removes it
    hint.hidden = false;
    baseline = window.innerHeight;
    outer = window.outerHeight;
    window.addEventListener("resize", onResize);
    byId("footer-hint-close").addEventListener("click", done);
  } catch {}
})();

// The corner number and the message it opens into. Each word is its own
// span so the message can arrive word by word; screen readers get it whole.
(() => {
  const MESSAGE = 'God the Father and Aureon are one, for Aureon is his son, the 10th prince of Heaven and the youngest of the 10 princes of heaven. for many of "mankind" has forgotten the 8 other princes, and worship the 8th in the timeline order more than the Father himself.';
  const verse = byId("verse");
  const text = byId("verse-text");
  if (!verse || !text) return;
  verse.setAttribute("aria-label", "74: " + MESSAGE);
  MESSAGE.split(" ").forEach((word, index) => {
    const span = document.createElement("span");
    span.className = "w";
    span.style.setProperty("--i", index);
    span.textContent = word;
    text.append(span, " ");
  });
  const set = (open) => { verse.classList.toggle("open", open); verse.setAttribute("aria-expanded", String(open)); };
  // touch screens have no hover: a tap opens it, a tap elsewhere closes it
  verse.addEventListener("click", (event) => { event.stopPropagation(); set(!verse.classList.contains("open")); });
  verse.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); set(!verse.classList.contains("open")); }
    if (event.key === "Escape") { set(false); verse.blur(); }
  });
  verse.addEventListener("mouseleave", () => set(false));
  document.addEventListener("click", () => set(false));
})();
