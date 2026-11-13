// Media metadata stripper + lossless shrinker.
//
// Removes every metadata layer a media file carries — EXIF (camera make,
// model, serial, lens, settings), GPS coordinates, XMP, IPTC, Photoshop
// resources, embedded thumbnails, timestamps, comments — WITHOUT touching a
// single pixel. The image bytes (the DCT coefficients of a jpeg, the IDAT
// scanlines of a png) are carried over unchanged, so there is zero quality
// loss. Color profiles (ICC / gAMA / sRGB) are kept by default so colors do
// not shift; pass dropColor to remove them too.
//
// Honest limits, stated in `note`: this strips METADATA. It cannot remove a
// fingerprint that lives in the pixels themselves — an invisible watermark,
// sensor-pattern (PRNU) noise, or a perceptual hash — because those are part
// of the image content, not a removable layer; removing them means re-encoding
// and losing quality. Video/audio containers are not remuxed here.
"use strict";
(() => {
const Shield = (globalThis.Shield = globalThis.Shield || {});
const media = (Shield.media = Shield.media || {});

const u16 = (b, o) => (b[o] << 8) | b[o + 1];
const concat = (parts) => { let n = 0; for (const p of parts) n += p.length; const out = new Uint8Array(n); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; } return out; };

media.detect = function detect(bytes) {
  if (bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "jpeg";
  if (bytes.length > 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return "png";
  if (bytes.length > 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) return "gif";
  if (bytes.length > 12 && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50) return "webp";
  return null;
};

// --- JPEG: keep SOI, JFIF (APP0), ICC (APP2, unless dropColor); drop APP1(EXIF/XMP),
//     APP13(IPTC/Photoshop), other APPn, and COM comments. Pixel scan (SOS→EOI) is copied whole. ---
media.cleanJpeg = function cleanJpeg(bytes, opts = {}) {
  const removed = [];
  const out = [bytes.subarray(0, 2)]; // SOI
  let i = 2;
  while (i + 4 <= bytes.length) {
    if (bytes[i] !== 0xff) break;
    const marker = bytes[i + 1];
    if (marker === 0xd9) { out.push(bytes.subarray(i)); i = bytes.length; break; } // EOI
    if (marker === 0xda) { out.push(bytes.subarray(i)); i = bytes.length; break; } // SOS → rest is entropy-coded scan + EOI
    const len = u16(bytes, i + 2);
    if (len < 2 || i + 2 + len > bytes.length) { out.push(bytes.subarray(i)); i = bytes.length; break; }
    const seg = bytes.subarray(i, i + 2 + len);
    const label = (() => {
      if (marker === 0xe1) { const tag = String.fromCharCode(...seg.subarray(4, 10)); return /Exif/.test(tag) ? "exif" : /http/.test(tag) ? "xmp" : "app1"; }
      if (marker === 0xed) return "iptc/photoshop";
      if (marker === 0xee) return "adobe-app14";
      if (marker === 0xfe) return "comment";
      if (marker === 0xe2) return "icc-color";
      return null;
    })();
    let drop = false;
    if (marker === 0xe1 || marker === 0xed || marker === 0xfe || (marker >= 0xe3 && marker <= 0xef)) drop = true; // EXIF/XMP, IPTC, COM, misc APPn
    if (marker === 0xe2 && opts.dropColor) drop = true; // ICC only if asked
    if (drop) { if (label) removed.push(label); } else out.push(seg);
    i += 2 + len;
  }
  return { bytes: concat(out), removed };
};

// --- PNG: keep IHDR/PLTE/IDAT/IEND + color/transparency chunks; drop text/time/exif metadata. ---
const PNG_KEEP = new Set(["IHDR", "PLTE", "IDAT", "IEND", "tRNS", "gAMA", "cHRM", "sRGB", "iCCP", "sBIT", "bKGD", "pHYs"]);
const PNG_META = new Set(["tEXt", "zTXt", "iTXt", "tIME", "eXIf", "dSIG", "sPLT", "hIST"]);
media.cleanPng = function cleanPng(bytes, opts = {}) {
  const removed = [];
  const out = [bytes.subarray(0, 8)]; // signature
  let i = 8;
  const u32 = (o) => (bytes[o] * 0x1000000) + ((bytes[o + 1] << 16) | (bytes[o + 2] << 8) | bytes[o + 3]);
  while (i + 8 <= bytes.length) {
    const len = u32(i);
    const type = String.fromCharCode(bytes[i + 4], bytes[i + 5], bytes[i + 6], bytes[i + 7]);
    const end = i + 12 + len;
    if (end > bytes.length) { out.push(bytes.subarray(i)); break; }
    const chunk = bytes.subarray(i, end);
    let keep = PNG_KEEP.has(type);
    if (opts.dropColor && (type === "iCCP" || type === "gAMA" || type === "cHRM" || type === "sRGB")) keep = false;
    if (keep) out.push(chunk);
    else { removed.push(type); }
    if (type === "IEND") break;
    i = end;
  }
  return { bytes: concat(out), removed };
};

// --- GIF: drop Comment (0x21 0xFE) and Application (0x21 0xFF, incl. XMP) extensions. ---
media.cleanGif = function cleanGif(bytes) {
  const removed = [];
  const out = [];
  let i = 0;
  // header + logical screen descriptor
  if (bytes.length < 13) return { bytes, removed };
  let p = 13;
  const gctFlag = bytes[10] & 0x80;
  if (gctFlag) p += 3 * (1 << ((bytes[10] & 0x07) + 1));
  out.push(bytes.subarray(0, p));
  const skipSubBlocks = (o) => { while (o < bytes.length && bytes[o] !== 0) o += bytes[o] + 1; return o + 1; };
  while (p < bytes.length) {
    const b = bytes[p];
    if (b === 0x3b) { out.push(bytes.subarray(p, p + 1)); break; } // trailer
    if (b === 0x21) { // extension
      const label = bytes[p + 1];
      const start = p; p += 2; p = skipSubBlocks(p);
      if (label === 0xfe || label === 0xff) { removed.push(label === 0xfe ? "comment" : "application/xmp"); }
      else out.push(bytes.subarray(start, p));
    } else if (b === 0x2c) { // image descriptor
      let q = p + 10;
      const lctFlag = bytes[p + 9] & 0x80;
      if (lctFlag) q += 3 * (1 << ((bytes[p + 9] & 0x07) + 1));
      q += 1; // LZW min code size
      q = skipSubBlocks(q);
      out.push(bytes.subarray(p, q)); p = q;
    } else { out.push(bytes.subarray(p)); break; }
  }
  return { bytes: concat(out), removed };
};

// --- WebP (RIFF): drop EXIF and XMP chunks; keep VP8/VP8L/VP8X/ALPH/ANIM/ANMF/ICCP. ---
media.cleanWebp = function cleanWebp(bytes, opts = {}) {
  const removed = [];
  if (bytes.length < 12) return { bytes, removed };
  const body = [bytes.subarray(0, 12)];
  let i = 12;
  const u32le = (o) => (bytes[o] | (bytes[o + 1] << 8) | (bytes[o + 2] << 16) | (bytes[o + 3] * 0x1000000)) >>> 0;
  while (i + 8 <= bytes.length) {
    const fourcc = String.fromCharCode(bytes[i], bytes[i + 1], bytes[i + 2], bytes[i + 3]);
    const size = u32le(i + 4);
    const padded = size + (size & 1);
    const end = i + 8 + padded;
    if (end > bytes.length) { body.push(bytes.subarray(i)); i = bytes.length; break; }
    const drop = fourcc === "EXIF" || fourcc === "XMP " || (opts.dropColor && fourcc === "ICCP");
    if (drop) removed.push(fourcc.trim().toLowerCase()); else body.push(bytes.subarray(i, end));
    i = end;
  }
  // rebuild RIFF size
  const out = concat(body);
  const total = out.length - 8;
  out[4] = total & 0xff; out[5] = (total >> 8) & 0xff; out[6] = (total >> 16) & 0xff; out[7] = (total >>> 24) & 0xff;
  return { bytes: out, removed };
};

// Lossless re-deflate of PNG IDAT via the platform's zlib streams, kept only if smaller.
async function pngRedeflate(bytes) {
  if (typeof DecompressionStream === "undefined" || typeof CompressionStream === "undefined") return null;
  try {
    const u32 = (o) => (bytes[o] * 0x1000000) + ((bytes[o + 1] << 16) | (bytes[o + 2] << 8) | bytes[o + 3]);
    const idat = [];
    let i = 8, firstIdatAt = -1;
    const other = [];
    while (i + 8 <= bytes.length) {
      const len = u32(i); const type = String.fromCharCode(bytes[i + 4], bytes[i + 5], bytes[i + 6], bytes[i + 7]); const end = i + 12 + len;
      if (end > bytes.length) return null;
      if (type === "IDAT") { if (firstIdatAt < 0) firstIdatAt = other.length; idat.push(bytes.subarray(i + 8, i + 8 + len)); }
      else other.push({ type, chunk: bytes.subarray(i, end) });
      if (type === "IEND") break;
      i = end;
    }
    if (!idat.length) return null;
    const raw = new Response(new Blob([concat(idat)]).stream().pipeThrough(new DecompressionStream("deflate")));
    const inflated = new Uint8Array(await raw.arrayBuffer());
    const recomp = new Response(new Blob([inflated]).stream().pipeThrough(new CompressionStream("deflate")));
    const deflated = new Uint8Array(await recomp.arrayBuffer());
    if (deflated.length >= concat(idat).length) return null; // no gain → keep original
    // rebuild: signature + chunks before first IDAT + one new IDAT + chunks after
    const crc = makeCrc();
    const idatChunk = pngChunk("IDAT", deflated, crc);
    const parts = [bytes.subarray(0, 8)];
    let inserted = false;
    for (const o of other) {
      if (!inserted && o.type === "IEND") { parts.push(idatChunk); inserted = true; }
      parts.push(o.chunk);
    }
    if (!inserted) parts.push(idatChunk);
    return concat(parts);
  } catch { return null; }
}
function makeCrc() {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1); table[n] = c >>> 0; }
  return (buf) => { let c = 0xffffffff; for (let i = 0; i < buf.length; i++) c = table[(c ^ buf[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
}
function pngChunk(type, data, crc) {
  const t = new Uint8Array([type.charCodeAt(0), type.charCodeAt(1), type.charCodeAt(2), type.charCodeAt(3)]);
  const body = concat([t, data]);
  const c = crc(body);
  const out = new Uint8Array(12 + data.length);
  const len = data.length;
  out[0] = (len >>> 24) & 0xff; out[1] = (len >>> 16) & 0xff; out[2] = (len >>> 8) & 0xff; out[3] = len & 0xff;
  out.set(body, 4);
  out[8 + data.length] = (c >>> 24) & 0xff; out[9 + data.length] = (c >>> 16) & 0xff; out[10 + data.length] = (c >>> 8) & 0xff; out[11 + data.length] = c & 0xff;
  return out;
}

// Main entry: strip metadata (and optionally recompress png), losslessly.
media.clean = async function clean(input, opts = {}) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const format = media.detect(bytes);
  const before = bytes.length;
  if (!format) return { ok: false, format: null, bytes, before, after: before, removed: [], note: "not a supported image format (jpeg, png, gif, webp); metadata not stripped." };
  let result;
  try {
    if (format === "jpeg") result = media.cleanJpeg(bytes, opts);
    else if (format === "png") result = media.cleanPng(bytes, opts);
    else if (format === "gif") result = media.cleanGif(bytes, opts);
    else if (format === "webp") result = media.cleanWebp(bytes, opts);
  } catch (error) { return { ok: false, format, bytes, before, after: before, removed: [], note: "could not parse this file; returned unchanged so it is never corrupted." }; }
  let cleaned = result.bytes;
  if (format === "png" && opts.recompress !== false) { const smaller = await pngRedeflate(cleaned); if (smaller && smaller.length < cleaned.length) { cleaned = smaller; result.removed.push("(idat recompressed losslessly)"); } }
  const after = cleaned.length;
  return {
    ok: true, format, bytes: cleaned, before, after,
    saved: before - after, savedPct: before ? Math.round((1 - after / before) * 1000) / 10 : 0,
    removed: result.removed,
    note: "metadata stripped losslessly; pixels unchanged. invisible watermarks or sensor-pattern noise baked into the pixels cannot be removed without re-encoding and quality loss.",
  };
};
})();
