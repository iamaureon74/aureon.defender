// Static file analysis: what a download really is, without ever running it.
//
// The file is fetched again into memory (the browser does not let an
// extension read files on disk), up to 50 MB, and read as bytes:
//   - its real type from the first bytes (magic numbers), compared with the
//     name it was given: a program named invoice.pdf is "disguised";
//   - names that hide the real ending: invoice.pdf.exe, right-to-left marks;
//   - archives: the list of what is inside, password-protected entries,
//     programs and scripts packed in;
//   - office files: macros (vbaProject.bin, _VBA_PROJECT);
//   - pdf: javascript, auto-run actions, launch actions, embedded files;
//   - rtf: embedded objects;
//   - its sha-256, matched against your intelligence and, with a free
//     abuse.ch key, against malwarebazaar (only the hash is sent).
// Nothing is executed, opened or rendered. Dynamic sandboxing (running the
// file and watching it) needs an isolated machine and is not done here.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const MAX_BYTES = 50 * 1024 * 1024;
const RUNNABLE = /\.(exe|scr|com|pif|bat|cmd|msi|msix|appx|ps1|psm1|vbs|vbe|js|jse|wsf|wsh|hta|lnk|jar|dll|cpl|reg|iso|img|vhd|vhdx|sh|app|dmg|pkg|apk|deb|rpm)$/i;
const DOCUMENT_NAME = /\.(pdf|docx?|xlsx?|pptx?|txt|rtf|jpe?g|png|gif|mp3|mp4|mov|csv|odt|ods)$/i;

function startsWith(bytes, signature, offset = 0) {
  if (bytes.length < offset + signature.length) return false;
  for (let i = 0; i < signature.length; i++) if (bytes[offset + i] !== signature[i]) return false;
  return true;
}
function ascii(bytes, start, length) {
  let out = "";
  for (let i = start; i < Math.min(bytes.length, start + length); i++) out += String.fromCharCode(bytes[i]);
  return out;
}
function contains(bytes, text, limit = bytes.length) {
  const needle = Array.from(text, (c) => c.charCodeAt(0));
  const end = Math.min(bytes.length, limit) - needle.length;
  outer: for (let i = 0; i <= end; i++) {
    for (let j = 0; j < needle.length; j++) if (bytes[i + j] !== needle[j]) continue outer;
    return true;
  }
  return false;
}

sec.fileType = function fileType(bytes) {
  if (startsWith(bytes, [0x4d, 0x5a])) {
    const offset = bytes.length > 0x40 ? bytes[0x3c] | (bytes[0x3d] << 8) | (bytes[0x3e] << 16) : 0;
    return startsWith(bytes, [0x50, 0x45, 0, 0], offset) ? "windows program (pe)" : "windows program (mz)";
  }
  if (startsWith(bytes, [0x7f, 0x45, 0x4c, 0x46])) return "linux program (elf)";
  if (startsWith(bytes, [0xcf, 0xfa, 0xed, 0xfe]) || startsWith(bytes, [0xce, 0xfa, 0xed, 0xfe]) || startsWith(bytes, [0xca, 0xfe, 0xba, 0xbe])) return "mac program (mach-o)";
  if (startsWith(bytes, [0x50, 0x4b, 0x03, 0x04]) || startsWith(bytes, [0x50, 0x4b, 0x05, 0x06])) return "zip archive";
  if (startsWith(bytes, [0x25, 0x50, 0x44, 0x46])) return "pdf";
  if (startsWith(bytes, [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])) return "old office / msi (ole)";
  if (startsWith(bytes, [0x52, 0x61, 0x72, 0x21])) return "rar archive";
  if (startsWith(bytes, [0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c])) return "7z archive";
  if (startsWith(bytes, [0x1f, 0x8b])) return "gzip archive";
  if (startsWith(bytes, [0x4c, 0, 0, 0, 0x01, 0x14, 0x02, 0])) return "windows shortcut (lnk)";
  if (bytes.length > 0x8005 && ascii(bytes, 0x8001, 5) === "CD001") return "disk image (iso)";
  if (startsWith(bytes, [0x7b, 0x5c, 0x72, 0x74, 0x66])) return "rtf document";
  if (startsWith(bytes, [0x23, 0x21])) return "script (#!)";
  if (startsWith(bytes, [0x89, 0x50, 0x4e, 0x47])) return "png image";
  if (startsWith(bytes, [0xff, 0xd8, 0xff])) return "jpeg image";
  const head = ascii(bytes, 0, 400).toLowerCase();
  if (/<script|<hta:application|activexobject|wscript\.shell/.test(head)) return "script (html/hta)";
  if (/^\s*(powershell|cmd \/c|@echo off|set-executionpolicy)/.test(head)) return "script (shell)";
  return "unknown";
};

// Zip central directory: names, sizes and the encrypted flag of every entry.
sec.zipEntries = function zipEntries(bytes) {
  let end = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 66000); i--) if (startsWith(bytes, [0x50, 0x4b, 0x05, 0x06], i)) { end = i; break; }
  if (end < 0) return [];
  const u16 = (o) => bytes[o] | (bytes[o + 1] << 8);
  const u32 = (o) => (bytes[o] | (bytes[o + 1] << 8) | (bytes[o + 2] << 16) | (bytes[o + 3] << 24)) >>> 0;
  const count = u16(end + 10);
  let offset = u32(end + 16);
  const entries = [];
  for (let n = 0; n < count && n < 5000 && offset + 46 <= bytes.length; n++) {
    if (!startsWith(bytes, [0x50, 0x4b, 0x01, 0x02], offset)) break;
    const flags = u16(offset + 8);
    const size = u32(offset + 24);
    const nameLength = u16(offset + 28), extraLength = u16(offset + 30), commentLength = u16(offset + 32);
    const name = new TextDecoder().decode(bytes.subarray(offset + 46, offset + 46 + nameLength));
    entries.push({ name, size, encrypted: Boolean(flags & 1) });
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
};

sec.scanBytes = async function scanBytes(input, name = "") {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const sha256 = Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
  const type = sec.fileType(bytes);
  const findings = [];
  let disguised = false, activeContent = false;
  const program = /program|script|shortcut|disk image/.test(type);
  const lowerName = String(name).toLowerCase();

  if (/[‮‭‏]/.test(name)) { findings.push("the name contains a right-to-left mark that reverses its ending"); disguised = true; }
  const parts = lowerName.split(".");
  if (parts.length >= 3 && DOCUMENT_NAME.test("." + parts[parts.length - 2]) && RUNNABLE.test(lowerName)) { findings.push(`double ending: looks like .${parts[parts.length - 2]} but is .${parts[parts.length - 1]}`); disguised = true; }
  if (program && DOCUMENT_NAME.test(lowerName)) { findings.push(`named like a document but is a ${type}`); disguised = true; }
  if (program) findings.push(`this is a ${type}: it can run code on your computer`);

  let entries = [];
  if (type === "zip archive") {
    entries = sec.zipEntries(bytes);
    const runnable = entries.filter((entry) => RUNNABLE.test(entry.name));
    if (runnable.length) findings.push(`archive contains ${runnable.length} program or script file${runnable.length > 1 ? "s" : ""}: ${runnable.slice(0, 5).map((e) => e.name).join(", ")}`);
    if (entries.some((entry) => entry.encrypted)) findings.push("archive is password-protected (often used to slip past scanners)");
    if (entries.some((entry) => /(^|\/)vbaProject\.bin$/i.test(entry.name))) { findings.push("office document with macros"); activeContent = true; }
    if (entries.some((entry) => /\.(docm|xlsm|pptm)$/i.test(entry.name)) || /\.(docm|xlsm|pptm)$/i.test(lowerName)) { findings.push("macro-enabled office format"); activeContent = true; }
    if (entries.some((entry) => /\.(pdf|docx?)\.(exe|scr|js|lnk|bat|cmd)$/i.test(entry.name))) { findings.push("archive holds a file with a double ending"); disguised = true; }
  }
  if (type === "old office / msi (ole)" && (contains(bytes, "_VBA_PROJECT") || contains(bytes, "VBA"))) { findings.push("old-format office file with macros"); activeContent = true; }
  if (type === "pdf") {
    const checks = [["/JavaScript", "javascript inside the pdf"], ["/JS", "javascript inside the pdf"], ["/OpenAction", "an action that runs when the pdf opens"], ["/Launch", "a launch action that can start a program"], ["/EmbeddedFile", "an embedded file"], ["/AA", "automatic actions"]];
    const seen = new Set();
    for (const [needle, words] of checks) if (contains(bytes, needle) && !seen.has(words)) { seen.add(words); findings.push(words); }
    if (seen.has("javascript inside the pdf") || seen.has("a launch action that can start a program")) activeContent = true;
  }
  if (type === "rtf document" && (contains(bytes, "\\objdata") || contains(bytes, "\\objupdate"))) { findings.push("rtf with embedded objects (used by old office exploits)"); activeContent = true; }

  // YARA rules (lib/sec/yara.js): the bundled set plus your own.
  // A YARA rule file contains the very strings its rules hunt for, so scanning
  // one with YARA "finds" stealers and miners in it. Only a file NAMED .yar or
  // .yara (nothing runs it on a double-click) whose whole text compiles as YARA
  // with no errors is exempt; a dropper with a fake rule header pasted on top
  // fails one of the two and is still scanned. Every other check above still ran.
  let yara = [], yaraMatch = false, yaraSkipped = "";
  if (sec.yaraCompile && /\.(yar|yara)$/i.test(String(name || "")) && bytes.length < 4 * 1024 * 1024) {
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      const parsed = sec.yaraCompile(text, "this file");
      if (parsed.rules.length && !parsed.errors.length) yaraSkipped = `this is a yara rule file (${parsed.rules.length} rules); noah's rules were not run on it, since a rule file always contains the strings it looks for`;
    } catch { /* not valid utf-8 text: scan it normally */ }
  }
  if (sec.yaraScan && !yaraSkipped) {
    try {
      yara = (await sec.yaraScan(bytes)).map((hit) => ({ rule: hit.rule, severity: String(hit.meta.severity || "medium"), description: String(hit.meta.description || ""), origin: hit.origin }));
      for (const hit of yara) findings.push(`yara rule ${hit.rule}${hit.description ? ": " + hit.description : ""}`);
      yaraMatch = yara.some((hit) => hit.severity === "critical" || hit.severity === "high");
      if (yara.length && !yaraMatch) activeContent = true;
    } catch (error) {
      findings.push("yara rules could not run: " + String(error.message || error));
    }
  }

  return { sha256, type, size: bytes.length, name, findings, disguised, activeContent, yara, yaraMatch, yaraSkipped, entries: entries.slice(0, 200) };
};

sec.fetchAndScan = async function fetchAndScan(url, name) {
  const response = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error("the site answered " + response.status);
  const declared = Number(response.headers.get("content-length") || 0);
  if (declared > MAX_BYTES) throw new Error("larger than 50 MB: not scanned");
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > MAX_BYTES) { reader.cancel(); throw new Error("larger than 50 MB: not scanned"); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return sec.scanBytes(bytes, name);
};

// MalwareBazaar: only the sha-256 leaves, and only with your own free key.
sec.malwareBazaar = async function malwareBazaar(sha256, key) {
  if (!key) return { skipped: "no abuse.ch key" };
  const response = await fetch("https://mb-api.abuse.ch/api/v1/", { method: "POST", credentials: "omit", headers: { "Auth-Key": key, "content-type": "application/x-www-form-urlencoded" }, body: "query=get_info&hash=" + encodeURIComponent(sha256) });
  if (!response.ok) return { error: "malwarebazaar answered " + response.status };
  const data = await response.json();
  if (data.query_status === "ok" && data.data && data.data[0]) return { known: true, signature: data.data[0].signature || null, tags: data.data[0].tags || [], firstSeen: data.data[0].first_seen || null };
  return { known: false, status: data.query_status };
};
})();
