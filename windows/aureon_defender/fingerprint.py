"""Second pass after the metadata cleaner: hidden branches, identifiers and wasted bytes. Pixels never change.

What this removes (on top of clean.py's EXIF/XMP/IPTC/ID3/udta handling):
  JPEG  * everything after the end-of-image marker: motion-photo videos (Google / Samsung), Samsung SEFT trailers,
          appended secondary images, depth maps and anything else glued on.
        * APP2 blocks that are not the colour profile (MPF multi-picture index, FlashPix). The ICC colour profile
          stays: removing it shifts colours on wide-gamut phones, which would be a loss of quality.
  PNG   * every ancillary chunk that isn't needed to draw the image: C2PA content credentials (caBX), digital
          signatures (dSIG), editor and vendor chunks (Fireworks, Photoshop, Apple 'iDOT'...), plus bytes after IEND.
        * the compressed image data is recompressed at zlib level 9 and only kept when smaller. The decompressed
          scanlines are byte-identical, so the picture is exactly the same pixel for pixel.
  MP4   * C2PA content-credential 'uuid' boxes and Sony/GoPro-style vendor 'uuid' boxes inside moov (blanked to
          'free', so offsets stay valid and nothing is re-encoded).

What cannot be removed without changing the picture or sound, and is therefore left alone (said, not hidden):
  the camera sensor's noise pattern (PRNU), the encoder's quantisation tables, visible content and watermarks.
"""
import struct
import zlib

KEEP_PNG = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"sBIT", b"bKGD",
            b"pHYs", b"acTL", b"fcTL", b"fdAT", b"cICP", b"mDCv", b"cLLi"}
C2PA_UUID = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")


def jpeg(data):
    """-> (bytes, [removed]) for JPEG data that has already had EXIF/XMP removed."""
    if data[:2] != b"\xff\xd8":
        return data, []
    out, i, removed = bytearray(b"\xff\xd8"), 2, []
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return data, []
        m = data[i + 1]
        if m == 0xDA:                                         # entropy-coded data until the real end of image
            end = data.find(b"\xff\xd9", i + 2)               # byte stuffing means FF D9 only appears as EOI
            if end == -1:
                out += data[i:]
                return bytes(out), removed
            out += data[i:end + 2]
            tail = len(data) - (end + 2)
            if tail > 0:
                kind = data[end + 2:end + 2 + 64]
                removed.append("embedded motion-photo video" if b"ftyp" in kind else
                               "appended image or depth map" if kind[:2] == b"\xff\xd8" else
                               f"{tail:,} bytes appended after the picture")
            return bytes(out), removed
        if 0xD0 <= m <= 0xD7 or m == 0x01:
            out += data[i:i + 2]
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i:i + 2 + ln]
        if m == 0xE2 and not seg[4:16].startswith(b"ICC_PROFILE"):
            removed.append("multi-picture index (MPF)" if seg[4:8] == b"MPF\0" else "APP2 block")
        else:
            out += seg
        i += 2 + ln
    return bytes(out), removed


def png(data):
    """-> (bytes, [removed]). Drops non-essential chunks and recompresses IDAT losslessly when it saves space."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return data, []
    chunks, i, removed, idat = [], 8, [], bytearray()
    while i + 12 <= len(data):
        ln, typ = struct.unpack(">I", data[i:i + 4])[0], data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        if typ == b"IDAT":
            idat += body
            if not chunks or chunks[-1][0] != b"IDAT":
                chunks.append((b"IDAT", None))
        elif typ in KEEP_PNG:
            chunks.append((typ, body))
        else:
            removed.append({b"caBX": "content credentials (C2PA)", b"dSIG": "digital signature",
                            b"iDOT": "apple decoding hints"}.get(typ, f"{typ.decode('latin-1')} chunk"))
        i += 12 + ln
        if typ == b"IEND":
            if i < len(data):
                removed.append(f"{len(data) - i:,} bytes after the image end")
            break
    animated = any(t == b"acTL" for t, _ in chunks)
    packed = bytes(idat)
    if idat and not animated:
        try:
            raw = zlib.decompress(bytes(idat))
            again = zlib.compress(raw, 9)
            if len(again) < len(idat) and zlib.decompress(again) == raw:
                packed = again
                removed.append(f"{len(idat) - len(again):,} bytes of slack compression (pixels identical)")
        except zlib.error:
            return data, []

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    out = bytearray(data[:8])
    for t, b in chunks:
        out += chunk(t, packed if t == b"IDAT" else b)
    if not chunks or chunks[-1][0] != b"IEND":
        return data, []
    return bytes(out), removed


def mp4(data):
    """Blank C2PA and vendor uuid boxes (top level and inside moov/trak) to 'free'."""
    data = bytearray(data)
    removed = set()

    def walk(start, end):
        i = start
        while i + 8 <= end:
            size, typ, hdr = struct.unpack(">I", data[i:i + 4])[0], bytes(data[i + 4:i + 8]), 8
            if size == 1:
                size, hdr = struct.unpack(">Q", data[i + 8:i + 16])[0], 16
            elif size == 0:
                size = end - i
            if size < hdr or i + size > end:
                return
            if typ == b"uuid" and size >= hdr + 16:
                u = bytes(data[i + hdr:i + hdr + 16])
                removed.add("content credentials (C2PA)" if u == C2PA_UUID else "vendor uuid box")
                data[i + 4:i + 8] = b"free"
                data[i + hdr:i + size] = b"\0" * (size - hdr)
            elif typ in (b"moov", b"trak"):
                walk(i + hdr, i + size)
            i += size
    walk(0, len(data))
    return bytes(data), sorted(removed)


PASSES = {".jpg": jpeg, ".jpeg": jpeg, ".png": png, ".mp4": mp4, ".mov": mp4, ".m4v": mp4, ".3gp": mp4, ".m4a": mp4}
