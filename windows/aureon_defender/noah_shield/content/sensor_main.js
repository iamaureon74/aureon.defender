// Page-world sensor: the two things only the page's own javascript can see.
//   1. text a page puts on your clipboard (clipboard.writeText / write /
//      execCommand("copy")), and whether it looks like a system command;
//   2. a password you typed leaving the page inside a script request
//      (fetch, XMLHttpRequest, sendBeacon), and to which host.
// It never reads or reports the password itself: it only compares, inside
// the page, whether the request body contains the value of a password field.
(() => {
  const __mk = "_" + crypto.getRandomValues(new Uint32Array(2))[0].toString(36) + crypto.getRandomValues(new Uint32Array(2))[0].toString(36);
  // non-enumerable: a page diffing window keys never sees it
  Object.defineProperty(window, __mk, { value: true, configurable: true });
  const COMMAND = /(powershell|pwsh|cmd(\.exe)?\s*\/[ck]|mshta|rundll32|regsvr32|certutil|bitsadmin|wscript|cscript|msiexec\s+\/[iq]|curl\s[^\n|]*\|\s*(ba|z)?sh|wget\s[^\n|]*\|\s*(ba|z)?sh|iex\s*[(`$]|invoke-expression|invoke-webrequest|frombase64string|-e(nc|ncodedcommand)?\s+[a-z0-9+/=]{20,}|start-process|osascript\s+-e|\bbash\s+-c|base64\s+(-d|--decode)|\.(hta|ps1|vbs)\b)/i;
  const post = (payload) => { try { window.postMessage({ __noahSensor: payload }, location.origin === "null" ? "*" : location.origin); } catch {} };

  function reportClipboard(text) {
    const value = String(text || "");
    if (!value) return;
    post({ kind: "clipboard.write", commandLike: COMMAND.test(value), length: value.length, sample: COMMAND.test(value) ? value.replace(/\s+/g, " ").slice(0, 120) : "" });
  }
  try {
    const clip = navigator.clipboard;
    if (clip && clip.writeText) {
      const original = clip.writeText.bind(clip);
      clip.writeText = function writeText(text) { reportClipboard(text); return original(text); };
    }
    if (clip && clip.write) {
      const original = clip.write.bind(clip);
      clip.write = async function write(items) {
        try { for (const item of items || []) if (item.types && item.types.includes("text/plain")) reportClipboard(await (await item.getType("text/plain")).text()); } catch {}
        return original(items);
      };
    }
    const exec = Document.prototype.execCommand;
    Document.prototype.execCommand = function execCommand(command, ...rest) {
      if (String(command).toLowerCase() === "copy") {
        const selection = String(window.getSelection ? window.getSelection() : "");
        const active = document.activeElement;
        reportClipboard(selection || (active && "value" in active ? active.value : ""));
      }
      return exec.call(this, command, ...rest);
    };
    document.addEventListener("copy", (event) => {
      setTimeout(() => { try { const data = event.clipboardData && event.clipboardData.getData("text/plain"); if (data) reportClipboard(data); } catch {} }, 0);
    }, true);
  } catch {}

  // ---- passwords leaving in script requests -------------------------------------------
  function passwords() {
    return Array.from(document.querySelectorAll("input[type=password]")).map((input) => input.value).filter((value) => value && value.length >= 4);
  }
  function bodyText(body) {
    if (body == null) return "";
    if (typeof body === "string") return body;
    if (body instanceof URLSearchParams) return body.toString();
    if (typeof FormData !== "undefined" && body instanceof FormData) { let out = ""; for (const [k, v] of body.entries()) out += k + "=" + (typeof v === "string" ? v : "") + "&"; return out; }
    return "";
  }
  function check(url, body, via) {
    const values = passwords();
    if (!values.length) return;
    const text = bodyText(body);
    if (!text) return;
    const hit = values.some((value) => text.includes(value) || text.includes(encodeURIComponent(value)) || (() => { try { return text.includes(btoa(value)); } catch { return false; } })());
    if (!hit) return;
    let target;
    try { target = new URL(url, location.href); } catch { return; }
    post({ kind: "form.submit", via, action: target.origin + target.pathname, hasPassword: true });
  }
  try {
    const originalFetch = window.fetch;
    window.fetch = function fetch(input, init) {
      try { check(typeof input === "string" ? input : input && input.url, init && init.body, "fetch"); } catch {}
      return originalFetch.apply(this, arguments);
    };
    const open = XMLHttpRequest.prototype.open;
    const send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) { this.__noahUrl = url; return open.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function (body) { try { check(this.__noahUrl, body, "xhr"); } catch {} return send.apply(this, arguments); };
    if (navigator.sendBeacon) {
      const beacon = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function sendBeacon(url, data) { try { check(url, data, "beacon"); } catch {} return beacon(url, data); };
    }
  } catch {}
})();
