// Things on your own computer and your own network that the shield can work
// with when they are there, and quietly does without when they are not:
//
//   * a local language model (Ollama at 127.0.0.1:11434, or noah's own when
//     noah answers "llm.classify"): a second opinion on pressure tactics a
//     page uses. Page text goes to that model on this computer and nowhere
//     else;
//   * WireGuard through noah (the native helper): a tunnel for the whole
//     computer, not only the browser;
//   * OpenSnitch through noah: the application firewall that can hold every
//     program, not only the browser, to "fail closed";
//   * a Noah Box on your network (a Raspberry Pi running the noah-box
//     stack): its DNS filter, VPN and intrusion alerts.
//
// The helper messages are documented in HELPER_PROTOCOL.md. A helper that
// does not know one answers with an error, which is shown as "not available".
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const local = (Shield.local = Shield.local || {});

const TACTICS = ["urgency", "scarcity", "social proof", "authority", "reciprocity", "commitment", "confirmshaming", "fear", "hidden costs", "fake discount"];

function withTimeout(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, done: () => clearTimeout(timer) };
}

function loopbackOnly(endpoint) {
  try {
    const url = new URL(endpoint);
    return url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ? url.origin : null;
  } catch { return null; }
}

// ---- local language model -------------------------------------------------------------------

async function ollama(cfg, prompt, ms = 25000) {
  const origin = loopbackOnly(cfg.endpoint || "http://127.0.0.1:11434");
  if (!origin) return { error: "the local model address must be on this computer (127.0.0.1)" };
  const timer = withTimeout(ms);
  try {
    const response = await fetch(origin + "/api/generate", {
      method: "POST",
      credentials: "omit",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: cfg.model || "llama3.2:3b", prompt, stream: false, format: "json", options: { temperature: 0 } }),
      signal: timer.signal,
    });
    if (response.status === 403) return { error: "Ollama refused the shield. Start it with OLLAMA_ORIGINS=chrome-extension://*,moz-extension://* set." };
    if (response.status === 404) return { error: `Ollama does not have the model "${cfg.model}". Run: ollama pull ${cfg.model}` };
    if (!response.ok) return { error: "Ollama answered " + response.status };
    const data = await response.json();
    return { text: String(data.response || "") };
  } catch (error) {
    return { error: error.name === "AbortError" ? "the local model took too long" : "Ollama is not running on this computer" };
  } finally {
    timer.done();
  }
}

local.ask = async function ask(prompt, settings) {
  const cfg = settings.localAi || {};
  if (!cfg.enabled) return { error: "local ai is off" };
  if (cfg.provider === "noah") {
    const answer = await Shield.host({ type: "llm.classify", prompt, model: cfg.model || "" });
    return answer.error ? { error: answer.error } : { text: String(answer.text || "") };
  }
  return ollama(cfg, prompt);
};

function parseJson(text) {
  try { return JSON.parse(text); } catch {}
  const m = /\{[\s\S]*\}/.exec(text || "");
  if (m) { try { return JSON.parse(m[0]); } catch {} }
  return null;
}

// Pressure tactics in a page's words. Returns { tactics: [{ name, quote, why }] }.
local.cognition = async function cognition(text, settings) {
  const sample = String(text || "").replace(/\s+/g, " ").slice(0, 6000);
  if (sample.length < 80) return { tactics: [] };
  const prompt = [
    "You check web pages for manipulative sales and persuasion tactics aimed at the reader.",
    "Tactics to look for: " + TACTICS.join(", ") + ".",
    "Only report a tactic when the text really uses it on the reader, with a short exact quote from the text.",
    "Ignore neutral product facts, news reporting about such tactics, and ordinary navigation text.",
    'Answer only JSON: {"tactics":[{"name":"<one of the tactics>","quote":"<exact words, under 120 characters>","why":"<one plain sentence>"}]}. Empty list if none.',
    "",
    "PAGE TEXT:",
    sample,
  ].join("\n");
  const answer = await local.ask(prompt, settings);
  if (answer.error) return { error: answer.error };
  const data = parseJson(answer.text);
  const list = data && Array.isArray(data.tactics) ? data.tactics : [];
  const seen = new Set();
  const tactics = [];
  for (const item of list) {
    const name = String((item && item.name) || "").toLowerCase().trim();
    const quote = String((item && item.quote) || "").trim().slice(0, 160);
    if (!TACTICS.includes(name) || !quote || seen.has(name)) continue;
    // A quote the page does not contain is the model inventing it: dropped.
    if (!sample.toLowerCase().includes(quote.toLowerCase().slice(0, 40))) continue;
    seen.add(name);
    tactics.push({ name, quote, why: String(item.why || "").slice(0, 200) });
  }
  return { tactics };
};

local.testAi = async function testAi(settings) {
  const cfg = Object.assign({}, settings.localAi, { enabled: true });
  const started = Date.now();
  const answer = await local.ask('Answer only JSON: {"ok":true}', Object.assign({}, settings, { localAi: cfg }));
  if (answer.error) return { ok: false, error: answer.error };
  return { ok: Boolean(parseJson(answer.text)), ms: Date.now() - started, model: cfg.model, provider: cfg.provider };
};

// ---- WireGuard and OpenSnitch through noah --------------------------------------------------

local.wireguard = async function wireguard(action, name) {
  if (!["status", "up", "down"].includes(action)) return { error: "unknown action" };
  const message = { type: "wireguard." + action };
  if (action !== "status") {
    if (!/^[A-Za-z0-9_.-]{1,40}$/.test(String(name || ""))) return { error: "give the tunnel's name (letters, numbers, - _ .)" };
    message.name = name;
  }
  const answer = await Shield.host(message);
  if (answer.error) return { available: false, error: answer.error };
  return Object.assign({ available: true }, answer);
};

local.opensnitch = async function opensnitch(action, hosts) {
  if (action === "status") {
    const answer = await Shield.host({ type: "opensnitch.status" });
    return answer.error ? { available: false, error: answer.error } : Object.assign({ available: true }, answer);
  }
  if (action === "sync") {
    // The shield's confirmed bad hosts become deny rules for every program.
    const list = (hosts || []).filter((host) => /^[a-z0-9.-]+$/.test(host)).slice(0, 50000);
    const answer = await Shield.host({ type: "opensnitch.denyHosts", hosts: list, list: "noah-shield" });
    return answer.error ? { available: false, error: answer.error } : Object.assign({ available: true, sent: list.length }, answer);
  }
  return { error: "unknown action" };
};

// ---- Noah Box ---------------------------------------------------------------------------------

// The box serves GET /status.json (see noah-box/README.md) on your network.
local.boxStatus = async function boxStatus(settings) {
  const cfg = settings.noahBox || {};
  const address = String(cfg.address || "").trim();
  if (!address) return { configured: false };
  let url;
  try { url = new URL("/status.json", /^https?:\/\//.test(address) ? address : "https://" + address); } catch { return { configured: true, error: "that is not an address" }; }
  const timer = withTimeout(6000);
  try {
    const headers = cfg.token ? { authorization: "Bearer " + cfg.token } : {};
    const response = await fetch(url.href, { credentials: "omit", cache: "no-store", headers, signal: timer.signal });
    if (!response.ok) return { configured: true, error: "the box answered " + response.status };
    const data = await response.json();
    return { configured: true, ok: true, url: url.origin, data };
  } catch (error) {
    return { configured: true, error: error.name === "AbortError" ? "the box did not answer" : "could not reach the box (is it on this network? is its certificate trusted?)" };
  } finally {
    timer.done();
  }
};

local.status = async function status(settings) {
  const host = await Shield.hostInfo(true);
  const [wg, snitch, box] = await Promise.all([
    host.present ? local.wireguard("status") : { available: false, error: host.error },
    host.present ? local.opensnitch("status") : { available: false, error: host.error },
    local.boxStatus(settings),
  ]);
  return { host, wireguard: wg, opensnitch: snitch, box, localAi: settings.localAi };
};
})();
