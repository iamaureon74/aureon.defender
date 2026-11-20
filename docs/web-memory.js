'use strict';
/* Browser memory (fold-memory for iPhone / iPad / any browser). Files you add are cut where their bytes say,
   each bite is named by its SHA-256 and stored once in this browser's own storage (IndexedDB), deflated when
   the browser supports it. Every file keeps its versions. A version only comes back if every bite and the
   whole file still match their fingerprints. Nothing is uploaded. */
(() => {
  const q = s => document.querySelector(s);
  if (!q('#memory')) return;
  const MIN = 2048, MASK = (1 << 13) - 1, MAX = 65536;
  const GEAR = new Uint32Array(256); { let x = 0x9E3779B9 >>> 0; for (let i = 0; i < 256; i++) { x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; GEAR[i] = x; } }
  const hex = b => [...new Uint8Array(b)].map(n => n.toString(16).padStart(2, '0')).join('');
  const sha = async b => hex(await crypto.subtle.digest('SHA-256', b));
  const canZip = typeof CompressionStream === 'function';
  const pipe = async (b, T) => new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new T('deflate-raw'))).arrayBuffer());
  const fmt = n => n >= 2 ** 30 ? (n / 2 ** 30).toFixed(1) + ' gb' : n >= 2 ** 20 ? (n / 2 ** 20).toFixed(1) + ' mb' : Math.max(1, Math.round(n / 1024)) + ' kb';
  const esc = v => String(v ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  let dbp = null;
  const db = () => dbp || (dbp = new Promise((ok, no) => {
    const r = indexedDB.open('aureon-memory', 1);
    r.onupgradeneeded = () => { r.result.createObjectStore('chunks'); r.result.createObjectStore('files'); };
    r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error);
  }));
  const tx = async (store, mode, fn) => { const d = await db(); return new Promise((ok, no) => { const t = d.transaction(store, mode); const out = fn(t.objectStore(store)); t.oncomplete = () => ok(out instanceof IDBRequest ? out.result : out); t.onerror = () => no(t.error); }); };
  const get = (s, k) => tx(s, 'readonly', o => o.get(k));
  const put = (s, k, v) => tx(s, 'readwrite', o => o.put(v, k));
  const del = (s, k) => tx(s, 'readwrite', o => o.delete(k));
  const all = s => tx(s, 'readonly', o => o.getAll());
  const keys = s => tx(s, 'readonly', o => o.getAllKeys());

  function* cut(bytes) {
    let start = 0, h = 0;
    for (let i = 0; i < bytes.length; i++) {
      h = ((h << 1) + GEAR[bytes[i]]) >>> 0;
      const len = i - start + 1;
      if ((len >= MIN && (h & MASK) === 0) || len === MAX) { yield bytes.subarray(start, i + 1); start = i + 1; h = 0; }
    }
    if (start < bytes.length) yield bytes.subarray(start);
  }

  async function fold(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const whole = await sha(bytes), name = file.webkitRelativePath || file.name;
    const rec = (await get('files', name)) || { name, versions: [] };
    if (rec.versions[0] && rec.versions[0].sha === whole) return 'same';
    const list = [];
    for (const part of cut(bytes)) {
      const id = await sha(part);
      list.push(id);
      if (await get('chunks', id)) continue;
      let body = part.slice(), z = 0;
      if (canZip) { const packed = await pipe(part, CompressionStream); if (packed.length < part.length) { body = packed; z = 1; } }
      await put('chunks', id, { z, body });
    }
    rec.versions.unshift({ sha: whole, size: bytes.length, modified: file.lastModified, held: Date.now(), chunks: list });
    await put('files', name, rec);
    return 'new';
  }

  async function unfold(v) {
    const parts = [];
    for (const id of v.chunks) {
      const c = await get('chunks', id);
      if (!c) throw Error('refused: a stored bite is missing');
      const data = c.z ? await pipe(c.body, DecompressionStream) : c.body;
      if (await sha(data) !== id) throw Error('refused: a stored bite is damaged');
      parts.push(data);
    }
    const blob = new Blob(parts);
    if (await sha(await blob.arrayBuffer()) !== v.sha) throw Error('refused: fingerprint does not match');
    return blob;
  }

  async function gc() {
    const live = new Set();
    for (const f of await all('files')) for (const v of f.versions) v.chunks.forEach(c => live.add(c));
    for (const k of await keys('chunks')) if (!live.has(k)) await del('chunks', k);
  }

  async function render() {
    const files = await all('files');
    let stored = 0; for (const c of await all('chunks')) stored += c.body.length;
    const logical = files.reduce((n, f) => n + f.versions.reduce((m, v) => m + v.size, 0), 0);
    const vers = files.reduce((n, f) => n + f.versions.length - 1, 0);
    q('#mem-stats').innerHTML = `<div><span>files kept</span><b>${files.length}</b></div><div><span>earlier versions</span><b>${vers}</b></div><div><span>space used</span><b>${fmt(stored)}</b></div><div><span>saved</span><b>${logical ? Math.max(0, Math.round((1 - stored / logical) * 100)) : 0}%</b></div>`;
    files.sort((a, b) => b.versions[0].held - a.versions[0].held);
    q('#mem-list').innerHTML = files.length ? files.map((f, i) => `<div class="mem-row"><div class="mem-name keep-case">${esc(f.name)}</div>${f.versions.map((v, j) => `<button class="link ghost sm" data-f="${i}" data-v="${j}">${j ? 'earlier ' + j : 'newest'} · ${new Date(v.held).toLocaleDateString([], { month: 'short', day: 'numeric' })} · ${fmt(v.size)}</button>`).join('')}<button class="link ghost sm forget" data-forget="${i}">forget</button></div>`).join('') : '<p>nothing kept yet. add files and each change you add later becomes a version you can get back.</p>';
    q('#mem-list').querySelectorAll('[data-v]').forEach(b => b.onclick = async () => {
      const f = files[+b.dataset.f], v = f.versions[+b.dataset.v];
      try { const blob = await unfold(v); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = f.name.split('/').pop(); a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); q('#mem-status').textContent = 'checked against its fingerprint and saved.'; }
      catch (e) { q('#mem-status').textContent = e.message; }
    });
    q('#mem-list').querySelectorAll('[data-forget]').forEach(b => b.onclick = async () => { await del('files', files[+b.dataset.forget].name); await gc(); render(); });
  }

  q('#mem-files').onchange = async e => {
    const list = [...e.target.files]; let n = 0, same = 0;
    for (const [i, f] of list.entries()) {
      q('#mem-status').textContent = `keeping ${i + 1} of ${list.length}…`;
      if (f.size > 512 * 2 ** 20) continue;
      (await fold(f)) === 'new' ? n++ : same++;
    }
    try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (_) {}
    q('#mem-status').textContent = `${n} new or changed, ${same} already kept. nothing left this device.`;
    e.target.value = ''; render();
  };
  if (!window.indexedDB || !crypto.subtle) { q('#mem-status').textContent = 'this browser can not keep files (needs https and indexeddb).'; return; }
  render().catch(e => { q('#mem-status').textContent = e.message; });
  window.aureonMemory = { fold, unfold, gc, all: () => all('files') };
})();
