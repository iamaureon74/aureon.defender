// YARA rules for the file scanner, in plain JavaScript.
//
// Reads rules written in YARA's own language (https://virustotal.github.io/
// yara/) and runs them over a file's bytes in memory. No YARA code is used:
// this is a separate engine for the common part of the language, so rules
// written for YARA work here unchanged as long as they stay inside it:
//   strings   "text" (nocase, wide, ascii, fullword, private), hex strings
//             with ??, nibble wildcards, [n-m] jumps and (a|b) alternatives,
//             /regex/ with i and s
//   condition and, or, not, ( ), true, false, numbers (KB, MB), filesize,
//             $a, #a, @a[i], !a[i], $a at n, $a in (a..b), uint8/16/32(be),
//             any/all/none/N of them, of ($a, $b*), other rule names,
//             comparisons, + - * \ %, & | ^ ~ << >>
// Rules that use modules (import "pe"), for-loops, xor or base64 strings are
// skipped and listed as skipped, never guessed at.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const sec = (Shield.sec = Shield.sec || {});

const MAX_MATCHES = 1000;
const RESERVED = new Set(["and", "or", "not", "at", "in", "of", "them", "for", "rule", "meta", "strings", "condition", "import", "include", "private", "global", "contains", "matches", "defined"]);

class Unsupported extends Error {}

// ---- reading rule text ----------------------------------------------------------------------

function lexer(source) {
  let i = 0;
  const n = source.length;
  function skip() {
    for (;;) {
      while (i < n && /\s/.test(source[i])) i++;
      if (source.startsWith("//", i)) { while (i < n && source[i] !== "\n") i++; continue; }
      if (source.startsWith("/*", i)) { const end = source.indexOf("*/", i + 2); i = end < 0 ? n : end + 2; continue; }
      return;
    }
  }
  function quoted() {
    // i is on the opening quote
    let out = "";
    i++;
    while (i < n && source[i] !== '"') {
      if (source[i] === "\\") {
        const next = source[i + 1];
        if (next === "x") { out += String.fromCharCode(parseInt(source.substr(i + 2, 2), 16)); i += 4; continue; }
        out += { n: "\n", t: "\t", r: "\r", '"': '"', "\\": "\\" }[next] ?? next;
        i += 2;
        continue;
      }
      out += source[i++];
    }
    i++;
    return out;
  }
  function token() {
    skip();
    if (i >= n) return null;
    const c = source[i];
    if (c === '"') return { t: "str", v: quoted() };
    if (/[A-Za-z_]/.test(c)) { const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(source.slice(i, i + 200)); i += m[0].length; return { t: "id", v: m[0] }; }
    if (/[$#@!]/.test(c) && /[A-Za-z0-9_*]/.test(source[i + 1] || "")) {
      const m = /^[$#@!][A-Za-z0-9_]*\*?/.exec(source.slice(i, i + 200)); i += m[0].length; return { t: "sref", v: m[0] };
    }
    if (c === "$") { i++; return { t: "sref", v: "$" }; }
    if (/[0-9]/.test(c)) {
      const m = /^(0x[0-9a-fA-F]+|0o[0-7]+|[0-9]+(?:\.[0-9]+)?)(KB|MB)?/.exec(source.slice(i, i + 40));
      i += m[0].length;
      let v = m[1].startsWith("0x") ? parseInt(m[1], 16) : m[1].startsWith("0o") ? parseInt(m[1].slice(2), 8) : Number(m[1]);
      if (m[2] === "KB") v *= 1024; else if (m[2] === "MB") v *= 1048576;
      return { t: "num", v };
    }
    for (const op of ["..", "==", "!=", "<=", ">=", "<<", ">>"]) if (source.startsWith(op, i)) { i += 2; return { t: "op", v: op }; }
    i++;
    return { t: "op", v: c };
  }
  // Raw readers for the parts of a string definition that are not tokens.
  function hexBody() {
    skip();
    const end = source.indexOf("}", i);
    const body = source.slice(i + 1, end);
    i = end + 1;
    return body;
  }
  function regexBody() {
    skip();
    let j = i + 1, pattern = "";
    while (j < n && source[j] !== "/") {
      if (source[j] === "\\") { pattern += source[j] + source[j + 1]; j += 2; continue; }
      pattern += source[j++];
    }
    j++;
    let flags = "";
    while (j < n && /[is]/.test(source[j])) flags += source[j++];
    i = j;
    return { pattern, flags };
  }
  function peekChar() { skip(); return source[i]; }
  return { token, hexBody, regexBody, peekChar, get pos() { return i; }, set pos(v) { i = v; } };
}

function escapeForRegex(text) {
  let out = "";
  for (const ch of text) {
    const code = ch.charCodeAt(0);
    if (/[A-Za-z0-9 ]/.test(ch)) out += ch;
    else out += "\\x" + code.toString(16).padStart(2, "0").slice(-2);
  }
  return out;
}

function compileText(text, mods) {
  const nocase = mods.has("nocase");
  const ascii = mods.has("ascii") || !mods.has("wide");
  const forms = [];
  if (ascii) forms.push(escapeForRegex(text));
  if (mods.has("wide")) forms.push(Array.from(text, (ch) => escapeForRegex(ch) + "\\x00").join(""));
  let body = forms.length > 1 ? "(?:" + forms.join("|") + ")" : forms[0];
  if (mods.has("fullword")) body = "(?<![A-Za-z0-9])" + body + "(?![A-Za-z0-9])";
  return new RegExp(body, "g" + (nocase ? "i" : ""));
}

function compileHex(body) {
  const src = body.replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\s+/g, "");
  let out = "", k = 0;
  while (k < src.length) {
    const c = src[k];
    if (c === "[") {
      const end = src.indexOf("]", k);
      const range = src.slice(k + 1, end);
      if (range === "-") out += "[\\s\\S]*?";
      else if (range.includes("-")) { const [a, b] = range.split("-"); out += `[\\s\\S]{${a || 0},${b || ""}}?`; }
      else out += `[\\s\\S]{${range}}`;
      k = end + 1;
    } else if (c === "(") { out += "(?:"; k++; }
    else if (c === ")") { out += ")"; k++; }
    else if (c === "|") { out += "|"; k++; }
    else if (c === "~") throw new Unsupported("hex not (~)");
    else {
      const pair = src.substr(k, 2);
      if (!/^[0-9A-Fa-f?]{2}$/.test(pair)) throw new Error("bad hex string near " + src.slice(k, k + 8));
      if (pair === "??") out += "[\\s\\S]";
      else if (pair[0] === "?") { const lo = parseInt(pair[1], 16); out += "[" + Array.from({ length: 16 }, (_, h) => "\\x" + ((h << 4) | lo).toString(16).padStart(2, "0")).join("") + "]"; }
      else if (pair[1] === "?") { const hi = parseInt(pair[0], 16); out += "[\\x" + ((hi << 4)).toString(16).padStart(2, "0") + "-\\x" + ((hi << 4) | 15).toString(16).padStart(2, "0") + "]"; }
      else out += "\\x" + pair.toLowerCase();
      k += 2;
    }
  }
  return new RegExp(out, "g");
}

function compileRegex({ pattern, flags }, mods) {
  if (mods.has("wide")) throw new Unsupported("wide regex");
  return new RegExp(pattern, "g" + (flags.includes("i") || mods.has("nocase") ? "i" : "") + (flags.includes("s") ? "s" : ""));
}

// ---- condition parser (to a tree) ---------------------------------------------------------------

function parseCondition(tokens) {
  let p = 0;
  const peek = (v) => tokens[p] && (v === undefined || tokens[p].v === v) ? tokens[p] : null;
  const take = (v) => { const tk = tokens[p]; if (v !== undefined && (!tk || tk.v !== v)) throw new Error(`expected ${v} in condition`); p++; return tk; };
  const binary = (next, ops) => () => {
    let left = next();
    while (peek() && peek().t === "op" && ops.includes(peek().v)) { const op = take().v; left = { k: "bin", op, a: left, b: next() }; }
    return left;
  };
  function orExpr() { let a = andExpr(); while (peek("or")) { take(); a = { k: "or", a, b: andExpr() }; } return a; }
  function andExpr() { let a = notExpr(); while (peek("and")) { take(); a = { k: "and", a, b: notExpr() }; } return a; }
  function notExpr() { if (peek("not")) { take(); return { k: "not", a: notExpr() }; } return cmp(); }
  function cmp() {
    let a = bitor();
    while (peek() && ["==", "!=", "<", ">", "<=", ">="].includes(peek().v)) { const op = take().v; a = { k: "cmp", op, a, b: bitor() }; }
    if (peek("contains") || peek("icontains") || peek("startswith") || peek("matches")) throw new Unsupported("string operators");
    return a;
  }
  const mul = () => binary(unary, ["*", "\\", "%"])();
  const add = () => binary(mul, ["+", "-"])();
  const shift = () => binary(add, ["<<", ">>"])();
  const bitand = () => binary(shift, ["&"])();
  const bitxor = () => binary(bitand, ["^"])();
  const bitor = () => binary(bitxor, ["|"])();
  function unary() {
    if (peek("-")) { take(); return { k: "neg", a: unary() }; }
    if (peek("~")) { take(); return { k: "inv", a: unary() }; }
    return primary();
  }
  function setOf() {
    if (peek("them")) { take(); return { them: true }; }
    take("(");
    const items = [];
    while (!peek(")")) { const tk = take(); if (tk.t === "sref" || tk.t === "id") items.push(tk.v); if (peek(",")) take(); }
    take(")");
    return { items };
  }
  function primary() {
    const tk = peek();
    if (!tk) throw new Error("condition ended early");
    if (tk.v === "for") throw new Unsupported("for loops");
    if (tk.t === "num") {
      take();
      if (peek("of")) { take(); return { k: "of", q: { n: tk.v }, set: setOf() }; }
      if (peek("%")) { // "50% of them"
        const save = p; take();
        if (peek("of")) { take(); return { k: "of", q: { pct: tk.v }, set: setOf() }; }
        p = save;
      }
      return { k: "num", v: tk.v };
    }
    if (tk.v === "(") { take(); const e = orExpr(); take(")"); return e; }
    if (tk.t === "id") {
      take();
      if (tk.v === "true") return { k: "num", v: 1 };
      if (tk.v === "false") return { k: "num", v: 0 };
      if (tk.v === "filesize") return { k: "filesize" };
      if (tk.v === "entrypoint") throw new Unsupported("entrypoint");
      if (["any", "all", "none"].includes(tk.v)) { take("of"); return { k: "of", q: { word: tk.v }, set: setOf() }; }
      const int = /^(u?int)(8|16|32)(be)?$/.exec(tk.v);
      if (int) { take("("); const at = orExpr(); take(")"); return { k: "int", signed: int[1] === "int", bits: Number(int[2]), be: Boolean(int[3]), at }; }
      if (peek(".")) throw new Unsupported("module " + tk.v);
      if (RESERVED.has(tk.v)) throw new Error("unexpected " + tk.v + " in condition");
      return { k: "rule", name: tk.v };
    }
    if (tk.t === "sref") {
      take();
      const sigil = tk.v[0], name = "$" + tk.v.slice(1);
      if (sigil === "#") {
        if (peek("in")) throw new Unsupported("#a in range");
        return { k: "count", name };
      }
      if (sigil === "@" || sigil === "!") {
        let index = { k: "num", v: 1 };
        if (peek("[")) { take(); index = orExpr(); take("]"); }
        return { k: sigil === "@" ? "offset" : "length", name, index };
      }
      if (peek("at")) { take(); return { k: "at", name, at: unary() }; }
      if (peek("in")) { take(); take("("); const from = orExpr(); take(".."); const to = orExpr(); take(")"); return { k: "inrange", name, from, to }; }
      return { k: "has", name };
    }
    throw new Error("unexpected " + tk.v + " in condition");
  }
  const tree = orExpr();
  if (p < tokens.length) throw new Error("unexpected " + tokens[p].v + " in condition");
  return tree;
}

// ---- rule file parser ------------------------------------------------------------------------

sec.yaraCompile = function yaraCompile(source, origin = "rules") {
  const lex = lexer(String(source || ""));
  const rules = [], skipped = [], errors = [];
  let tk;
  while ((tk = lex.token())) {
    if (tk.v === "import" || tk.v === "include") { lex.token(); continue; }
    const flags = [];
    while (tk && (tk.v === "private" || tk.v === "global")) { flags.push(tk.v); tk = lex.token(); }
    if (!tk || tk.v !== "rule") { errors.push(`${origin}: expected "rule" but found "${tk && tk.v}"`); break; }
    const name = lex.token().v;
    const tags = [];
    let next = lex.token();
    if (next.v === ":") { while ((next = lex.token()) && next.v !== "{") tags.push(next.v); }
    const rule = { name, tags, meta: {}, strings: [], private: flags.includes("private"), global: flags.includes("global"), origin };
    let problem = null;
    try {
      let section = null, depth = 1;
      const condTokens = [];
      for (;;) {
        const t = lex.token();
        if (!t) throw new Error("rule " + name + " never closes");
        if (section !== "condition" && t.t === "id" && ["meta", "strings", "condition"].includes(t.v) && lex.peekChar() === ":") { lex.token(); section = t.v; continue; }
        if (section === "condition") {
          if (t.v === "{") depth++;
          if (t.v === "}" && --depth === 0) break;
          condTokens.push(t);
          continue;
        }
        if (t.v === "}") break;
        if (section === "meta") {
          lex.token(); // =
          const value = lex.token();
          let v = value.v;
          if (value.v === "-") v = -lex.token().v;
          rule.meta[t.v] = v;
        } else if (section === "strings") {
          let id = t.v === "$" ? "$__anon" + rule.strings.length : t.v;
          lex.token(); // =
          const first = lex.peekChar();
          let kind, raw;
          if (first === '"') { kind = "text"; raw = lex.token().v; }
          else if (first === "{") { kind = "hex"; raw = lex.hexBody(); }
          else if (first === "/") { kind = "regex"; raw = lex.regexBody(); }
          else throw new Error("bad string " + id);
          const mods = new Set();
          for (;;) {
            const save = lex.pos;
            const m = lex.token();
            if (m && m.t === "id" && ["nocase", "wide", "ascii", "fullword", "private", "xor", "base64", "base64wide"].includes(m.v)) {
              if (["xor", "base64", "base64wide"].includes(m.v)) problem = problem || new Unsupported(m.v + " strings");
              if (lex.peekChar() === "(") { while (lex.token().v !== ")") {} }
              mods.add(m.v);
              continue;
            }
            lex.pos = save;
            break;
          }
          if (!problem) {
            try {
              const regex = kind === "text" ? compileText(raw, mods) : kind === "hex" ? compileHex(raw) : compileRegex(raw, mods);
              rule.strings.push({ id, regex });
            } catch (error) { if (error instanceof Unsupported) problem = error; else throw error; }
          }
        }
      }
      if (!problem) rule.condition = parseCondition(condTokens);
    } catch (error) {
      if (error instanceof Unsupported) problem = error;
      else { errors.push(`${origin}: rule ${name}: ${error.message}`); continue; }
    }
    if (problem) { skipped.push(`${name} (${problem.message})`); continue; }
    rules.push(rule);
  }
  return { rules, skipped, errors };
};

// ---- running ----------------------------------------------------------------------------------

function binaryString(bytes) {
  const parts = [];
  for (let i = 0; i < bytes.length; i += 32768) parts.push(String.fromCharCode.apply(null, bytes.subarray(i, i + 32768)));
  return parts.join("");
}

function evaluate(node, ctx) {
  const ev = (x) => evaluate(x, ctx);
  switch (node.k) {
    case "num": return node.v;
    case "filesize": return ctx.bytes.length;
    case "or": return ev(node.a) || ev(node.b) ? 1 : 0;
    case "and": return ev(node.a) && ev(node.b) ? 1 : 0;
    case "not": return ev(node.a) ? 0 : 1;
    case "neg": return -ev(node.a);
    case "inv": return ~ev(node.a);
    case "cmp": {
      const a = ev(node.a), b = ev(node.b);
      return ({ "==": a === b, "!=": a !== b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b })[node.op] ? 1 : 0;
    }
    case "bin": {
      const a = ev(node.a), b = ev(node.b);
      switch (node.op) {
        case "+": return a + b; case "-": return a - b; case "*": return a * b;
        case "\\": return b ? Math.trunc(a / b) : NaN; case "%": return b ? a % b : NaN;
        case "&": return a & b; case "|": return a | b; case "^": return a ^ b;
        case "<<": return a << b; case ">>": return a >>> b;
      }
      return NaN;
    }
    case "int": {
      const at = ev(node.at), size = node.bits / 8, b = ctx.bytes;
      if (!(at >= 0) || at + size > b.length) return NaN;
      const view = new DataView(b.buffer, b.byteOffset + at, size);
      if (size === 1) return node.signed ? view.getInt8(0) : view.getUint8(0);
      if (size === 2) return node.signed ? view.getInt16(0, !node.be) : view.getUint16(0, !node.be);
      return node.signed ? view.getInt32(0, !node.be) : view.getUint32(0, !node.be);
    }
    case "has": return ctx.matches(node.name).length ? 1 : 0;
    case "count": return ctx.matches(node.name).length;
    case "offset": { const m = ctx.matches(node.name)[ev(node.index) - 1]; return m ? m.at : NaN; }
    case "length": { const m = ctx.matches(node.name)[ev(node.index) - 1]; return m ? m.len : NaN; }
    case "at": { const at = ev(node.at); return ctx.matches(node.name).some((m) => m.at === at) ? 1 : 0; }
    case "inrange": { const from = ev(node.from), to = ev(node.to); return ctx.matches(node.name).some((m) => m.at >= from && m.at <= to) ? 1 : 0; }
    case "rule": return ctx.ruleResult(node.name) ? 1 : 0;
    case "of": {
      const ids = node.set.them ? ctx.rule.strings.map((s) => s.id) : node.set.items.flatMap((item) => {
        if (item.endsWith("*")) { const prefix = item.slice(0, -1); return ctx.rule.strings.map((s) => s.id).filter((id) => id.startsWith(prefix)); }
        return [item];
      });
      const hits = ids.filter((id) => (id.startsWith("$") ? ctx.matches(id).length : ctx.ruleResult(id))).length;
      const q = node.q;
      if (q.word === "any") return hits >= 1 ? 1 : 0;
      if (q.word === "all") return ids.length && hits === ids.length ? 1 : 0;
      if (q.word === "none") return hits === 0 ? 1 : 0;
      if (q.pct !== undefined) return hits >= Math.ceil((q.pct / 100) * ids.length) ? 1 : 0;
      return hits >= q.n ? 1 : 0;
    }
  }
  throw new Error("unknown node " + node.k);
}

// Run compiled rules over bytes. Returns the rules that matched (private ones
// left out), each with its tags, meta and the strings that hit.
sec.yaraRun = function yaraRun(compiled, input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  let text = null;
  const results = new Map();
  const out = [];
  for (const rule of compiled.rules) {
    const cache = new Map();
    const matches = (id) => {
      if (cache.has(id)) return cache.get(id);
      const def = rule.strings.find((s) => s.id === id);
      const found = [];
      if (def) {
        if (text === null) text = binaryString(bytes);
        def.regex.lastIndex = 0;
        let m;
        while (found.length < MAX_MATCHES && (m = def.regex.exec(text))) {
          found.push({ at: m.index, len: m[0].length });
          if (m[0].length === 0) def.regex.lastIndex++;
        }
      }
      cache.set(id, found);
      return found;
    };
    const ctx = { bytes, rule, matches, ruleResult: (name) => results.get(name) || false };
    let ok = false;
    try { ok = Boolean(evaluate(rule.condition, ctx)); } catch { ok = false; }
    results.set(rule.name, ok);
    if (ok && !rule.private) out.push({ rule: rule.name, tags: rule.tags, meta: rule.meta, strings: [...cache.entries()].filter(([, list]) => list.length).map(([id]) => id), origin: rule.origin });
  }
  return out;
};

// The bundled rule set plus the rules you add in the security center.
let bundled = null;
let compiledFor = null, compiled = null;
async function loadBundled() {
  if (bundled !== null) return bundled;
  try {
    const url = Shield.api && Shield.api.runtime ? Shield.api.runtime.getURL("rules/yara/noah.yar") : null;
    bundled = url ? await (await fetch(url)).text() : "";
  } catch { bundled = ""; }
  return bundled;
}

sec.yaraRules = async function yaraRules() {
  const base = await loadBundled();
  let mine = "";
  try { mine = ((await Shield.loadSettings()).secCenter || {}).yaraRules || ""; } catch {}
  const key = base.length + ":" + mine;
  if (compiledFor !== key) {
    const a = sec.yaraCompile(base, "noah rules");
    const b = sec.yaraCompile(mine, "your rules");
    compiled = { rules: a.rules.concat(b.rules), skipped: a.skipped.concat(b.skipped), errors: a.errors.concat(b.errors), bundled: a.rules.length, yours: b.rules.length };
    compiledFor = key;
  }
  return compiled;
};

sec.yaraScan = async function yaraScan(bytes) {
  const rules = await sec.yaraRules();
  return sec.yaraRun(rules, bytes);
};
})();
