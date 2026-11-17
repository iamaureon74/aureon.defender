"""Format-aware metadata removers added in 0.4.5. Each takes bytes and returns (new_bytes, [what was removed]).

Design rule: never re-encode audio/video/image data. Only container-level metadata is dropped or blanked, so
quality is identical and the file still plays/opens. Where removing bytes would shift offsets that other parts
of the file depend on (PDF xref, MP4 chunk offsets, Matroska seek heads) the metadata is blanked in place with
the same byte length instead.
"""
import re
import struct

# ---------------- JPEG orientation (keep the one EXIF field that changes how the photo looks) ----------------


def jpeg_orientation(data):
    """Orientation (1-8) from the first EXIF APP1 segment, or None."""
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:
            break
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + ln]
        if marker == 0xE1 and seg[:6] == b"Exif\0\0":
            t = seg[6:]
            try:
                e = "<" if t[:2] == b"II" else ">" if t[:2] == b"MM" else None
                if not e:
                    return None
                off = struct.unpack(e + "I", t[4:8])[0]
                n = struct.unpack(e + "H", t[off:off + 2])[0]
                for k in range(min(n, 512)):
                    ent = t[off + 2 + 12 * k: off + 14 + 12 * k]
                    tag, typ = struct.unpack(e + "HH", ent[:4])
                    if tag == 0x0112 and typ == 3:
                        v = struct.unpack(e + "H", ent[8:10])[0]
                        return v if 1 <= v <= 8 else None
            except (struct.error, IndexError):
                return None
            return None
        i += 2 + ln
    return None


def orientation_segment(v):
    """Minimal APP1: EXIF with a single Orientation tag. No camera, time, GPS or serial."""
    tiff = b"MM\x00\x2a" + struct.pack(">I", 8) + struct.pack(">H", 1) + \
        struct.pack(">HHIHH", 0x0112, 3, 1, v, 0) + struct.pack(">I", 0)
    body = b"Exif\0\0" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body


def reinsert_orientation(stripped, v):
    if not v or v == 1:
        return stripped
    i = 2
    if stripped[2:4] == b"\xff\xe0":                       # JFIF APP0 must stay first
        i = 4 + struct.unpack(">H", stripped[4:6])[0]
    return stripped[:i] + orientation_segment(v) + stripped[i:]


# ---------------- MP3 APEv2 ----------------
def strip_apev2(data):
    end = len(data)
    if data[end - 128:end - 125] == b"TAG":
        end -= 128
    f = data[end - 32:end]
    if f[:8] != b"APETAGEX":
        return data, []
    size, _, flags = struct.unpack("<III", f[12:24])
    total = size + (32 if flags & 0x80000000 else 0)
    if total > end:
        return data, []
    return data[:end - total] + data[end:], ["APE tags"]


# ---------------- PDF extras ----------------
_HEX_INFO = re.compile(rb"(/(?:Author|Creator|Producer|Title|Subject|Keywords|Company|CreationDate|ModDate)\s*)<([0-9A-Fa-f\s]*)>")
_ID = re.compile(rb"(/ID\s*\[\s*)<([0-9A-Fa-f]*)>(\s*)<([0-9A-Fa-f]*)>")


def pdf_extras(data):
    removed = []

    def hexblank(m):
        n = len(m.group(2))
        return m.group(1) + b"<" + (b"20" * (n // 2) + b"2" * (n % 2)) + b">"
    data, n = _HEX_INFO.subn(hexblank, data)
    if n:
        removed.append("document info (hex-encoded)")
    if b"/Encrypt" not in data:                               # the ID keys encryption; leave encrypted PDFs intact
        data, n = _ID.subn(lambda m: m.group(1) + b"<" + b"0" * len(m.group(2)) + b">" + m.group(3) +
                           b"<" + b"0" * len(m.group(4)) + b">", data)
        if n:
            removed.append("document ID fingerprint")
    return data, removed


# ---------------- MP4 extras ----------------
XMP_UUID = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")


def mp4_extras(data):
    """XMP uuid boxes (often hold GPS + editing history) and creation/modification times in mvhd/tkhd/mdhd."""
    data = bytearray(data)
    removed = set()

    def walk(start, end):
        i = start
        while i + 8 <= end:
            size = struct.unpack(">I", data[i:i + 4])[0]
            typ = bytes(data[i + 4:i + 8])
            hdr = 8
            if size == 1:
                size = struct.unpack(">Q", data[i + 8:i + 16])[0]
                hdr = 16
            elif size == 0:
                size = end - i
            if size < hdr or i + size > end:
                return
            if typ == b"uuid" and bytes(data[i + hdr:i + hdr + 16]) == XMP_UUID:
                data[i + 4:i + 8] = b"free"
                data[i + hdr:i + size] = b"\0" * (size - hdr)
                removed.add("XMP metadata")
            elif typ in (b"mvhd", b"tkhd", b"mdhd") and size >= hdr + 12:
                v = data[i + hdr]
                w = 8 if v == 1 else 4
                if size >= hdr + 4 + 2 * w:
                    data[i + hdr + 4:i + hdr + 4 + 2 * w] = b"\0" * (2 * w)
                    removed.add("recording date and time")
            elif typ in (b"moov", b"trak", b"mdia"):
                walk(i + hdr, i + size)
            i += size
    walk(0, len(data))
    return bytes(data), sorted(removed)


# ---------------- OOXML / ODF extras (applied to XML parts) ----------------
FIXED_DATE = b"2000-01-01T00:00:00Z"
_DATES = re.compile(rb"(<(dcterms:created|dcterms:modified|cp:lastPrinted)[^>]*>)(.*?)(</\2>)", re.S)
_RSID_ATTR = re.compile(rb'\s+w:rsid\w*="[0-9A-Fa-f]*"')
_RSIDS_BLOCK = re.compile(rb"<w:rsids>.*?</w:rsids>", re.S)
_WDATE = re.compile(rb'w:date="[^"]*"')
_PRESENCE = re.compile(rb'(w:(?:userId|providerId))="[^"]*"')
_TOTALTIME = re.compile(rb"(<TotalTime>)\d+(</TotalTime>)")
_ODF_BLANK = re.compile(rb"(<(meta:creation-date|dc:date|meta:print-date|meta:printed-by|meta:editing-duration)[^>]*>)(.*?)(</\2>)", re.S)
_ODF_USER = re.compile(rb"<meta:user-defined[^>]*?(?:/>|>.*?</meta:user-defined>)", re.S)


def office_part(name, data):
    removed = set()
    if name == "docprops/core.xml":
        data, n = _DATES.subn(lambda m: m.group(1) + FIXED_DATE + m.group(4), data)
        if n:
            removed.add("created / modified / printed dates")
    elif name == "docprops/app.xml":
        data, n = _TOTALTIME.subn(rb"\g<1>0\2", data)
        if n:
            removed.add("total editing time")
    elif name == "meta.xml":
        data, n = _ODF_BLANK.subn(lambda m: m.group(1) + (FIXED_DATE[:-1] if b"date" in m.group(2) else
                                  b"PT0S" if b"duration" in m.group(2) else b"") + m.group(4), data)
        data, k = _ODF_USER.subn(b"", data)
        if n or k:
            removed.add("dates, printer and custom fields")
    if name.endswith(".xml") and name.startswith(("word/", "xl/", "ppt/")):
        data, a = _RSID_ATTR.subn(b"", data)
        data, b = _RSIDS_BLOCK.subn(b"", data)
        if a or b:
            removed.add("editing-session IDs (rsid)")
        data, c = _WDATE.subn(b'w:date="' + FIXED_DATE + b'"', data)
        if c:
            removed.add("comment and revision times")
        data, d = _PRESENCE.subn(rb'\1=""', data)
        if d:
            removed.add("account identifiers")
    return data, removed


# ---------------- SVG ----------------
def svg(data):
    if b"<svg" not in data[:4096] and b"<svg" not in data:
        raise ValueError("not SVG")
    removed = []
    rules = [
        (re.compile(rb"<metadata\b.*?</metadata>|<metadata\b[^>]*/>", re.S), "metadata block"),
        (re.compile(rb"<!--.*?-->", re.S), "comments"),
        (re.compile(rb"<sodipodi:namedview\b.*?(?:/>|</sodipodi:namedview>)", re.S), "editor view settings"),
        (re.compile(rb'\s+(?:inkscape|sodipodi):[\w-]+="[^"]*"'), "editor attributes (may include file paths)"),
    ]
    for rx, why in rules:
        data, n = rx.subn(b"", data)
        if n:
            removed.append(why)
    return data, removed


# ---------------- AIFF ----------------
AIFF_DROP = {b"NAME", b"AUTH", b"(c) ", b"ANNO", b"COMT", b"ID3 ", b"id3 "}


def aiff(data):
    if data[:4] != b"FORM" or data[8:12] not in (b"AIFF", b"AIFC"):
        raise ValueError("not AIFF")
    out, i, removed = bytearray(data[:12]), 12, []
    while i + 8 <= len(data):
        tag, ln = data[i:i + 4], struct.unpack(">I", data[i + 4:i + 8])[0]
        step = 8 + ln + (ln & 1)
        if tag in AIFF_DROP:
            removed.append(tag.decode("latin-1").strip())
        else:
            out += data[i:i + step]
        i += step
    struct.pack_into(">I", out, 4, len(out) - 8)
    return bytes(out), sorted(set(removed))


# ---------------- Ogg (Vorbis / Opus) ----------------
def _ogg_crc_table():
    t = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else r << 1
        t.append(r & 0xFFFFFFFF)
    return t


_OGG_T = _ogg_crc_table()


def ogg_crc(b):
    c = 0
    for x in b:
        c = ((c << 8) & 0xFFFFFFFF) ^ _OGG_T[((c >> 24) & 0xFF) ^ x]
    return c


def _ogg_pages(data):
    i = 0
    while i < len(data):
        if data[i:i + 4] != b"OggS":
            raise ValueError("bad Ogg page")
        nseg = data[i + 26]
        lacing = data[i + 27:i + 27 + nseg]
        body_len = sum(lacing)
        hdr = data[i:i + 27]
        yield {"hdr": hdr, "lacing": lacing, "body": data[i + 27 + nseg:i + 27 + nseg + body_len]}
        i += 27 + nseg + body_len


def _page(flags, granule, serial, seq, lacing, body):
    h = bytearray(b"OggS\x00" + bytes([flags]) + struct.pack("<qIII", granule, serial, seq, 0) + bytes([len(lacing)]) + bytes(lacing))
    crc = ogg_crc(bytes(h) + body)
    struct.pack_into("<I", h, 22, crc)
    return bytes(h) + body


def _lace(packet):
    n = len(packet)
    return [255] * (n // 255) + [n % 255]


def ogg(data):
    pages = list(_ogg_pages(data))
    serials = {struct.unpack("<I", p["hdr"][14:18])[0] for p in pages}
    if len(serials) != 1:
        raise ValueError("Ogg files with several streams aren't supported; original retained")
    serial = serials.pop()
    # collect packets until the header packets are complete
    packets, cur, used_pages = [], b"", 0
    first = bytes(pages[0]["body"][:8])
    need = 3 if first[1:7] == b"vorbis" else 2 if first == b"OpusHead" else None
    if need is None:
        raise ValueError("Only Vorbis and Opus Ogg files are supported")
    for p in pages:
        used_pages += 1
        off = 0
        for lv in p["lacing"]:
            cur += p["body"][off:off + lv]
            off += lv
            if lv < 255:
                packets.append(cur)
                cur = b""
        if len(packets) >= need:
            break
    if len(packets) != need or cur:
        raise ValueError("Ogg header packets share a page with audio; original retained")
    tags = packets[1]
    if need == 3:
        if tags[:7] != b"\x03vorbis":
            raise ValueError("unexpected Vorbis comment header")
        vlen = struct.unpack("<I", tags[7:11])[0]
        vendor = tags[11:11 + vlen]
        ncom = struct.unpack("<I", tags[11 + vlen:15 + vlen])[0]
        packets[1] = b"\x03vorbis" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0) + b"\x01"
    else:
        if tags[:8] != b"OpusTags":
            raise ValueError("unexpected Opus tags header")
        vlen = struct.unpack("<I", tags[8:12])[0]
        vendor = tags[12:12 + vlen]
        ncom = struct.unpack("<I", tags[12 + vlen:16 + vlen])[0]
        packets[1] = b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)
    rest_lacing = [x for pk in packets[1:] for x in _lace(pk)]
    if len(rest_lacing) > 255:
        raise ValueError("Ogg header too large to repage; original retained")
    out = bytearray()
    seq = 0
    out += _page(0x02, 0, serial, seq, _lace(packets[0]), packets[0])     # identification header: own page
    seq += 1
    rest = packets[1:]
    out += _page(0x00, 0, serial, seq, rest_lacing, b"".join(rest))
    seq += 1
    for p in pages[used_pages:]:
        h = p["hdr"]
        granule = struct.unpack("<q", h[6:14])[0]
        out += _page(h[5], granule, serial, seq, p["lacing"], bytes(p["body"]))
        seq += 1
    return bytes(out), (["tags and embedded pictures"] if ncom else [])


# ---------------- Matroska / WebM ----------------
def _vint(data, i, is_id=False):
    b = data[i]
    w = 1
    mask = 0x80
    while w <= 8 and not (b & mask):
        mask >>= 1
        w += 1
    if w > 8:
        raise ValueError("bad EBML")
    val = b if is_id else b & (mask - 1)
    unknown = (b & (mask - 1)) == mask - 1
    for k in range(1, w):
        val = (val << 8) | data[i + k]
        unknown = unknown and data[i + k] == 0xFF
    return val, w, (unknown and not is_id)


def _void(data, start, hdr_len, total):
    w = hdr_len - 1
    if not 1 <= w <= 8:
        return False
    content = total - 1 - w
    if content >= (1 << (7 * w)) - 1:
        return False
    data[start] = 0xEC
    data[start + 1:start + 1 + w] = ((1 << (7 * w)) | content).to_bytes(w, "big")
    data[start + 1 + w:start + total] = b"\0" * content
    return True


MKV_SEGMENT, MKV_INFO, MKV_TAGS = 0x18538067, 0x1549A966, 0x1254C367
MKV_INFO_DROP = {0x4461: "recording date", 0x7BA9: "title"}


def matroska(data):
    data = bytearray(data)
    if data[:4] != b"\x1a\x45\xdf\xa3":
        raise ValueError("not Matroska/WebM")
    removed = set()
    _, w, _ = _vint(data, 0, True)
    sz, sw, _ = _vint(data, w)
    i = w + sw + sz
    while i < len(data):
        eid, iw, _ = _vint(data, i, True)
        esz, ew, unknown = _vint(data, i + iw)
        body = i + iw + ew
        if eid != MKV_SEGMENT:
            i = body + esz
            continue
        seg_end = len(data) if unknown else min(len(data), body + esz)
        j = body
        while j < seg_end:
            cid, cw, _ = _vint(data, j, True)
            csz, csw, cunk = _vint(data, j + cw)
            if cunk:
                break                                         # unknown-size cluster: metadata comes before it
            cbody, cend = j + cw + csw, j + cw + csw + csz
            if cend > seg_end:
                break
            if cid == MKV_TAGS and _void(data, j, cw + csw, cend - j):
                removed.add("tags")
            elif cid == MKV_INFO:
                k = cbody
                while k < cend:
                    kid, kw, _ = _vint(data, k, True)
                    ksz, ksw, _ = _vint(data, k + kw)
                    kend = k + kw + ksw + ksz
                    if kid in MKV_INFO_DROP and _void(data, k, kw + ksw, kend - k):
                        removed.add(MKV_INFO_DROP[kid])
                    k = kend
            j = cend
        break
    return bytes(data), sorted(removed)


# ---------------- ZIP archives ----------------
def zip_archive(path):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(path) as zin:
        items = zin.infolist()
        if len(items) > 20000 or sum(i.file_size for i in items) > 512 * 1024 * 1024:
            raise ValueError("Archive exceeds cleanup limits; original retained")
        if any(i.flag_bits & 0x1 for i in items):
            raise ValueError("Password-protected archive; original retained")
        had_comment = bool(zin.comment)
        with zipfile.ZipFile(buf, "w") as zout:
            for it in items:
                zi = zipfile.ZipInfo(it.filename, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = it.compress_type if it.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) else zipfile.ZIP_DEFLATED
                zi.external_attr = it.external_attr & 0xFFFF0000 if it.is_dir() else 0o644 << 16
                if it.is_dir():
                    zi.external_attr |= 0x10
                zout.writestr(zi, b"" if it.is_dir() else zin.read(it.filename))
    removed = ["file times, owners and comments inside the archive"]
    if had_comment:
        removed.append("archive comment")
    return buf.getvalue(), removed


# ---------------- download source trail (Windows Mark-of-the-Web) ----------------
def scrub_zone_identifier(path):
    """Keep the security zone (so Windows still warns before running downloads) but drop the HostUrl/ReferrerUrl
    lines that record exactly which site and page each file came from. Returns True if something was removed."""
    import os
    if os.name != "nt":
        return False
    ads = str(path) + ":Zone.Identifier"
    try:
        with open(ads, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    if not re.search(r"(?mi)^(HostUrl|ReferrerUrl|HostIpAddress|LastWriterPackageFamilyName|AppZoneId)=", text):
        return False
    m = re.search(r"(?m)^ZoneId=(\d)\s*$", text)
    if not m:
        return False
    try:
        st = os.stat(path)
        with open(ads, "w", encoding="utf-8") as f:
            f.write("[ZoneTransfer]\nZoneId=" + m.group(1) + "\n")
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        return True
    except OSError:
        return False
