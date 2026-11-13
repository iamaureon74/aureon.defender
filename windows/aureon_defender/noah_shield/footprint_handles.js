// Username footprint: where a profile under one name exists, checked the way
// the Sherlock Project does it (lib/handles.js holds the site list and how
// each site says "no such user"). Requests go straight from this page to each
// site, without cookies or a referrer. Nothing is sent anywhere else.
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const SITES = (globalThis.Shield && Shield.HANDLE_SITES) || [];
  const PARALLEL = 8;
  const TIMEOUT = 12000;
  let stopping = false;

  if ($("h-count")) $("h-count").textContent = SITES.length.toLocaleString();

  function fill(template, name) { return template.split("{}").join(encodeURIComponent(name)); }

  // found | missing | unsure (the site blocked programs or failed) | skipped (name not allowed there)
  async function checkOne(site, name) {
    if (site.regex) {
      try { if (!new RegExp(site.regex).test(name)) return { site, state: "skipped" }; } catch {}
    }
    const profile = fill(site.url, name);
    const probe = site.probe ? fill(site.probe, name) : profile;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT);
    try {
      const response = await fetch(probe, {
        method: site.head ? "HEAD" : "GET",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        cache: "no-store",
        redirect: site.check === "response_url" ? "manual" : "follow",
        signal: controller.signal,
      });
      if (site.check === "response_url") {
        if (response.type === "opaqueredirect" || (response.status >= 300 && response.status < 400)) return { site, state: "missing", profile };
        return { site, state: response.ok ? "found" : "missing", profile };
      }
      if ([403, 429, 503].includes(response.status) && !(site.codes || []).includes(response.status)) return { site, state: "unsure", profile, note: "answered " + response.status };
      if (site.check === "status_code") {
        if ((site.codes || []).includes(response.status)) return { site, state: "missing", profile };
        return { site, state: response.ok ? "found" : "missing", profile };
      }
      // "message": the page itself says the user does not exist.
      const text = await response.text();
      const missing = (site.msg || []).some((needle) => text.includes(needle));
      return { site, state: missing || !response.ok ? "missing" : "found", profile };
    } catch (error) {
      return { site, state: "unsure", profile, note: error.name === "AbortError" ? "no answer in 12 s" : "could not connect" };
    } finally {
      clearTimeout(timer);
    }
  }

  function row(result) {
    const tr = document.createElement("tr");
    const site = document.createElement("td");
    site.textContent = result.site.name;
    const state = document.createElement("td");
    state.textContent = result.state === "found" ? "found" : "unsure: " + (result.note || "");
    if (result.state === "unsure") state.className = "muted";
    const link = document.createElement("td");
    const a = document.createElement("a");
    a.href = result.profile;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = result.profile;
    link.append(a);
    tr.append(site, state, link);
    return tr;
  }

  async function run() {
    const name = $("h-name").value.trim();
    if (!name) { $("h-status").textContent = "enter a username first."; return; }
    stopping = false;
    $("h-go").disabled = true;
    $("h-stop").hidden = false;
    $("h-progress").hidden = false;
    const table = $("h-results");
    table.replaceChildren();
    const bar = $("h-progress").firstElementChild;
    const queue = SITES.slice();
    const found = [], unsure = [];
    let done = 0;
    const worker = async () => {
      while (queue.length && !stopping) {
        const site = queue.shift();
        const result = await checkOne(site, name);
        done++;
        bar.style.width = Math.round((done / SITES.length) * 100) + "%";
        $("h-status").textContent = `${done} of ${SITES.length} checked · ${found.length} found`;
        if (result.state === "found") { found.push(result); table.append(row(result)); }
        else if (result.state === "unsure") unsure.push(result);
      }
    };
    await Promise.all(Array.from({ length: PARALLEL }, worker));
    // Sites that refused programs or did not answer: kept out of the way.
    const old = document.getElementById("h-unsure");
    if (old) old.remove();
    if (unsure.length) {
      const details = document.createElement("details");
      details.id = "h-unsure";
      const summary = document.createElement("summary");
      summary.className = "muted";
      summary.textContent = `${unsure.length} site${unsure.length > 1 ? "s" : ""} could not be checked (they block programs or did not answer): open them yourself`;
      const list = document.createElement("table");
      for (const result of unsure) list.append(row(result));
      details.append(summary, list);
      table.after(details);
    }
    $("h-status").textContent = `${stopping ? "stopped · " : ""}${found.length} found · ${unsure.length} unsure · ${done} of ${SITES.length} checked`;
    $("h-go").disabled = false;
    $("h-stop").hidden = true;
    $("h-progress").hidden = true;
  }

  if ($("h-go")) {
    $("h-go").addEventListener("click", () => { run().catch((error) => { $("h-status").textContent = String(error.message || error); $("h-go").disabled = false; }); });
    $("h-stop").addEventListener("click", () => { stopping = true; });
    $("h-name").addEventListener("keydown", (event) => { if (event.key === "Enter") $("h-go").click(); });
  }
})();
