"""Best-effort removal of selected metadata fields. Not universal fingerprint removal.

Layers removed:
  photos      JPEG (EXIF incl. GPS / camera serial, XMP, IPTC, comments, maker notes), PNG (text, EXIF, time),
              WebP (EXIF, XMP), GIF (comments, app extensions), TIFF/HEIC via re-save without metadata
  audio       MP3 (ID3v1 + ID3v2: artist, comments, embedded pictures, encoder), FLAC (Vorbis comments, pictures),
              WAV (LIST/INFO and bext chunks)
  documents   Word / Excel / PowerPoint (author, last editor, company, comments' authors, revision, template,
              app version, custom properties), OpenDocument (meta.xml), PDF (Info dictionary and XMP packet blanked)
  video       MP4 / MOV / M4A: the 'udta' and 'meta' boxes (device model, GPS, creation tool) neutralised in place
Every result says what was found and removed, in plain words.
"""
import io
import os
import re
import shutil
import struct
import zipfile
from pathlib import Path

PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".heic", ".heif", ".avif", ".svg"}
AUDIO = {".mp3", ".flac", ".wav", ".aif", ".aiff", ".ogg", ".oga", ".opus"}
DOCS = {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".odt", ".ods", ".odp", ".pdf"}
VIDEO = {".mp4", ".mov", ".m4a", ".m4v", ".3gp", ".mkv", ".webm", ".mka"}
ARCHIVES = {".zip"}
SUPPORTED = PHOTO | AUDIO | DOCS | VIDEO | ARCHIVES
REENCODE = {".heic", ".heif", ".avif"}           # no lossless path: re-encoded to a new .jpg copy, never in place
OFFICE = {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".odt", ".ods", ".odp"}


# ---------------- photos ----------------
def _jpeg(data):
    """Drop EXIF/XMP/IPTC/comments but keep Orientation, otherwise portrait photos display sideways."""
    from .media_strip import jpeg_orientation, reinsert_orientation
    from .noah import strip_jpeg
    orient = jpeg_orientation(data)
    new, removed = strip_jpeg(data)
    return reinsert_orientation(new, orient), removed


def _png(data):
    from .noah import strip_png
    return strip_png(data)


def _webp(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not WebP")
    out, i, removed = bytearray(data[:12]), 12, []
    while i + 8 <= len(data):
        tag, ln = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        chunk = data[i:i + 8 + ln + (ln & 1)]
        if tag in (b"EXIF", b"XMP "):
            removed.append(tag.decode().strip())
        else:
            if tag == b"VP8X":                         # clear the EXIF/XMP flags in the extended header
                chunk = bytearray(chunk)
                chunk[8] &= ~0x0C
                chunk = bytes(chunk)
            out += chunk
        i += 8 + ln + (ln & 1)
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out), removed


def _gif(data):
    if data[:3] != b"GIF":
        raise ValueError("not GIF")
    out, removed = bytearray(), []
    i = 13
    if data[10] & 0x80:
        i += 3 * (2 << (data[10] & 7))
    out += data[:i]
    while i < len(data):
        b = data[i]
        if b == 0x3B:
            out += b"\x3b"
            break
        if b == 0x21:
            label = data[i + 1]
            j = i + 2
            while data[j] != 0:
                j += data[j] + 1
            block = data[i:j + 1]
            if label in (0xFE, 0xFF) and b"NETSCAPE2.0" not in block[:16]:   # comments + app data (keep looping info)
                removed.append("comment" if label == 0xFE else "application data")
            else:
                out += block
            i = j + 1
        elif b == 0x2C:
            j = i + 10
            if data[i + 9] & 0x80:
                j += 3 * (2 << (data[i + 9] & 7))
            j += 1                                      # LZW min code size
            while data[j] != 0:
                j += data[j] + 1
            out += data[i:j + 1]
            i = j + 1
        else:
            raise ValueError("unexpected GIF block")
    return bytes(out), removed


def _resave(path):
    """TIFF/HEIC/AVIF: re-encode without metadata (lossy for HEIC/AVIF, which become JPEG copies)."""
    from PIL import Image, ImageOps
    if Path(path).suffix.lower() in REENCODE:
        try:
            import pillow_heif                     # optional plug-in; without it Pillow can't read HEIC
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
    try:
        im0 = Image.open(path)
    except Exception as ex:
        raise ValueError(f"{Path(path).suffix} needs an image plug-in that isn't installed; original retained") from ex
    with im0 as im:
        im = ImageOps.exif_transpose(im)            # bake orientation into pixels before EXIF is dropped
        if getattr(im, "n_frames", 1) > 1:
            raise ValueError("Multi-page images require a format-aware tool; original retained")
        buf = io.BytesIO()
        fmt = "TIFF" if Path(path).suffix.lower() in (".tif", ".tiff") else "JPEG"
        im.convert("RGB" if fmt == "JPEG" else im.mode).save(buf, fmt, quality=95)
    return buf.getvalue(), ["all metadata (re-encoded)"]


# ---------------- audio ----------------
def _mp3(data):
    removed, start, end = [], 0, len(data)
    from .media_strip import strip_apev2
    data, ape = strip_apev2(data)
    removed += ape
    while data[start:start + 3] == b"ID3":
        size = 0
        for b in data[start + 6:start + 10]:
            size = (size << 7) | (b & 0x7F)
        footer = 10 if data[start + 5] & 0x10 else 0
        start += 10 + size + footer
        removed.append("ID3v2 tags")
    if data[end - 128:end - 125] == b"TAG":
        end -= 128
        removed.append("ID3v1 tags")
    if data[end - 227:end - 223] == b"TAG+":
        end -= 227
    return data[start:end], removed


def _flac(data):
    if data[:4] != b"fLaC":
        raise ValueError("not FLAC")
    out, i, removed = bytearray(b"fLaC"), 4, []
    blocks = []
    while True:
        hdr = data[i]
        last, typ = hdr & 0x80, hdr & 0x7F
        ln = int.from_bytes(data[i + 1:i + 4], "big")
        blocks.append((typ, data[i + 4:i + 4 + ln]))
        i += 4 + ln
        if last:
            break
    keep = [(t, b) for t, b in blocks if t not in (4, 6)]          # VORBIS_COMMENT, PICTURE
    removed += ["tags"] * any(t == 4 for t, _ in blocks) + ["embedded picture"] * any(t == 6 for t, _ in blocks)
    for n, (t, b) in enumerate(keep):
        out += bytes([(0x80 if n == len(keep) - 1 else 0) | t]) + len(b).to_bytes(3, "big") + b
    out += data[i:]
    return bytes(out), removed


def _wav(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not WAV")
    out, i, removed = bytearray(data[:12]), 12, []
    while i + 8 <= len(data):
        tag, ln = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        chunk = data[i:i + 8 + ln + (ln & 1)]
        if tag in (b"LIST", b"bext", b"iXML", b"id3 ", b"ID3 "):
            removed.append(tag.decode().strip())
        else:
            out += chunk
        i += 8 + ln + (ln & 1)
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out), removed


# ---------------- documents ----------------
CORE_BLANK = re.compile(rb"(<(dc:creator|cp:lastModifiedBy|cp:keywords|dc:description|cp:category|cp:contentStatus|dc:subject|cp:revision)[^>]*>)(.*?)(</\2>)", re.S)
APP_BLANK = re.compile(rb"(<(Company|Manager|Template|Application|AppVersion|HyperlinkBase)>)(.*?)(</\2>)", re.S)
AUTHOR_ATTR = re.compile(rb'(w:author|w:initials|author)="[^"]*"')


def _ooxml(path):
    from .media_strip import office_part
    removed = set()
    buf = io.BytesIO()
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        items=zin.infolist()
        if len(items)>10000 or sum(i.file_size for i in items)>128*1024*1024:
            raise ValueError("Expanded document exceeds cleanup limits")
        for item in items:
            data = zin.read(item.filename)
            name = item.filename.lower()
            if name == "docprops/core.xml":
                data, n = CORE_BLANK.subn(rb"\1\4", data)
                if n:
                    removed.add("author / editor / revision")
            elif name == "docprops/app.xml":
                data, n = APP_BLANK.subn(rb"\1\4", data)
                if n:
                    removed.add("company / app / template")
            elif name == "docprops/custom.xml":
                removed.add("custom properties")
                continue
            elif name.endswith(".xml") and (b'w:author="' in data or b'author="' in data) and ("comment" in name or "document" in name or "people" in name):
                data, n = AUTHOR_ATTR.subn(rb'\1=""', data)
                if n:
                    removed.add("comment and change authors")
            elif name in ("meta.xml",):                    # OpenDocument
                data, n = re.subn(rb"(<(meta:initial-creator|dc:creator|meta:generator|meta:editing-cycles)[^>]*>)(.*?)(</\2>)", rb"\1\4", data, flags=re.S)
                if n:
                    removed.add("creator / generator")
            data, extra = office_part(name, data)
            removed |= extra
            zi = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))   # zip timestamps are metadata too
            zi.compress_type = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)
    removed.add("file timestamps inside the document")
    return buf.getvalue(), sorted(removed)


def _pdf(data):
    """Blank the Info dictionary strings and XMP packet in place (same byte length, so offsets stay valid)."""
    removed = []

    def blank(m):
        return m.group(1) + b"(" + b" " * (len(m.group(2))) + b")"
    new, n = re.subn(rb"(/(?:Author|Creator|Producer|Title|Subject|Keywords|Company|SourceModified|CreationDate|ModDate)\s*)\(((?:[^()\\]|\\.)*)\)", blank, data)
    if n:
        removed.append("document info (author, creator, producer, dates)")
    from .media_strip import pdf_extras
    new, more = pdf_extras(new)
    removed += more
    m = re.search(rb"<\?xpacket begin.*?<\?xpacket end=['\"]w['\"]\?>", new, re.S)
    if m:
        packet = m.group(0)
        body_start = packet.index(b"?>") + 2
        body_end = packet.rindex(b"<?xpacket end")
        filler = b" " * (body_end - body_start)
        new = new[:m.start()] + packet[:body_start] + filler + packet[body_end:] + new[m.end():]
        removed.append("XMP metadata")
    return new, removed


# ---------------- video ----------------
def _mp4(data):
    """Rename 'udta' / 'meta' boxes inside 'moov' to 'free' (players skip them; sizes and offsets unchanged)."""
    data = bytearray(data)
    removed = []

    def walk(start, end, depth):
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
            if typ in (b"udta", b"meta") and depth >= 1:
                data[i + 4:i + 8] = b"free"
                data[i + hdr:i + size] = b"\0" * (size - hdr)
                removed.append({b"udta": "device and location data", b"meta": "metadata box"}[typ])
            elif typ in (b"moov", b"trak", b"mdia"):
                walk(i + hdr, i + size, depth + 1)
            i += size
    walk(0, len(data), 0)
    from .media_strip import mp4_extras
    out, more = mp4_extras(bytes(data))
    return out, sorted(set(removed) | set(more))


def _lazy(name):
    def f(data):
        from . import media_strip
        return getattr(media_strip, name)(data)
    return f


HANDLERS = {".svg": _lazy("svg"), ".aif": _lazy("aiff"), ".aiff": _lazy("aiff"), ".ogg": _lazy("ogg"), ".oga": _lazy("ogg"),
            ".opus": _lazy("ogg"), ".mkv": _lazy("matroska"), ".webm": _lazy("matroska"), ".mka": _lazy("matroska"),
            ".jpg": _jpeg, ".jpeg": _jpeg, ".png": _png, ".webp": _webp, ".gif": _gif, ".mp3": _mp3, ".flac": _flac,
            ".wav": _wav, ".pdf": _pdf, ".mp4": _mp4, ".mov": _mp4, ".m4a": _mp4, ".m4v": _mp4, ".3gp": _mp4}


def clean_file(path, in_place=False, out=None):
    """Returns {file, written, removed: [...], saved_bytes}. Raises ValueError for unsupported files."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Choose a regular file, not a link")
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"{ext or 'this file'} isn't a supported type")
    before = p.stat().st_size
    if before > 128 * 1024 * 1024:
        raise ValueError("File exceeds the 128 MiB cleanup limit; original retained")
    if ext in REENCODE and in_place:
        raise ValueError(f"{ext} files are re-encoded to a JPEG copy; in-place cleaning would change the format")
    if ext in OFFICE:
        new, removed = _ooxml(p)
    elif ext in ARCHIVES:
        from .media_strip import zip_archive
        new, removed = zip_archive(p)
    elif ext in (".tif", ".tiff") or ext in REENCODE:
        new, removed = _resave(p)
    else:
        new, removed = HANDLERS[ext](p.read_bytes())
    out_suffix = ".jpg" if ext in REENCODE else p.suffix
    dst = p if in_place else Path(out) if out else p.with_name(p.stem + ".clean" + out_suffix)
    if in_place:
        tmp = p.with_name(p.name + ".aureon-tmp")
        tmp.write_bytes(new)
        shutil.copystat(p, tmp)
        os.replace(tmp, p)
    else:
        # Never overwrite an existing clean copy or an explicitly supplied original path.
        if dst.resolve() == p.resolve():
            raise ValueError("Output must differ from the original")
        if dst.exists():
            import uuid
            dst = dst.with_name(dst.stem + '-' + uuid.uuid4().hex[:8] + dst.suffix)
        with dst.open('xb') as f:
            f.write(new)
    if os.name == 'nt' and not in_place:
        # Retain the OS trust zone but omit identifying source/referrer URLs from the new copy.
        try:
            zone=Path(str(p)+':Zone.Identifier').read_text(encoding='utf-8',errors='replace')
            match=re.search(r'(?m)^ZoneId=([0-4])\s*$',zone)
            if match:Path(str(dst)+':Zone.Identifier').write_text('[ZoneTransfer]\nZoneId='+match.group(1)+'\n',encoding='utf-8')
        except OSError:
            pass
    return {"file": str(p), "written": str(dst), "removed": removed, "saved_bytes": before - len(new),
            "scope": "Selected known metadata fields only; embedded content, watermarks, filesystem records and all fingerprints are not removed.",
            "limitations": "PDF compressed/object-stream metadata and embedded attachments may remain. Video track identifiers/timestamps may remain. Review documents for visible names, comments and embedded content."}


def clean_batch(paths, limit=2000):
    """Create separate copies, enumerate failures, bound traversal, and preserve originals."""
    if not isinstance(paths,list) or not paths or len(paths)>100:
        raise ValueError("Choose 1 to 100 files or folders")
    results,errors,skipped=[],[],0
    count=0
    def files(t):
        if t.is_file():
            yield t
        elif t.is_dir() and not t.is_symlink():
            for folder,dirs,names in os.walk(t,followlinks=False):
                dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink() and not (hasattr(Path(folder)/d,'is_junction') and (Path(folder)/d).is_junction())]
                for n in names:yield Path(folder)/n
        else:raise ValueError("File or folder unavailable")
    for target in paths:
        try:
            for f in files(Path(target).expanduser()):
                if count>=limit:break
                count+=1
                if f.suffix.lower() not in SUPPORTED or '.clean' in f.stem:
                    skipped+=1;continue
                try:results.append(clean_file(f,in_place=False))
                except (ValueError,OSError,zipfile.BadZipFile,struct.error,IndexError,RuntimeError) as ex:
                    errors.append({"file":str(f),"error":str(ex)})
        except (ValueError,OSError) as ex:errors.append({"file":str(target),"error":str(ex)})
        if count>=limit:break
    return {"results":results,"errors":errors,"skipped":skipped,"limit":limit,"limit_reached":count>=limit,"originals_retained":True}


def clean_any(target, in_place=False, limit=2000):
    """File or folder -> list of results (unsupported files skipped)."""
    t = Path(target)
    files = [t] if t.is_file() else [f for f in t.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED][:limit]
    out = []
    for f in files:
        try:
            out.append(clean_file(f, in_place=in_place))
        except (ValueError, OSError, zipfile.BadZipFile, struct.error, IndexError):
            continue
    return out


# ---------------- leaked keys: what next ----------------
REVOKE = {
    "github": ("GitHub", "https://github.com/settings/tokens"), "gitlab": ("GitLab", "https://gitlab.com/-/user_settings/personal_access_tokens"),
    "aws": ("AWS", "https://console.aws.amazon.com/iam/home#/security_credentials"), "gcp": ("Google Cloud", "https://console.cloud.google.com/apis/credentials"),
    "google": ("Google", "https://console.cloud.google.com/apis/credentials"), "azure": ("Azure", "https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps"),
    "slack": ("Slack", "https://api.slack.com/apps"), "stripe": ("Stripe", "https://dashboard.stripe.com/apikeys"),
    "openai": ("OpenAI", "https://platform.openai.com/api-keys"), "anthropic": ("Anthropic", "https://console.anthropic.com/settings/keys"),
    "discord": ("Discord", "https://discord.com/developers/applications"), "twilio": ("Twilio", "https://console.twilio.com/"),
    "sendgrid": ("SendGrid", "https://app.sendgrid.com/settings/api_keys"), "npm": ("npm", "https://www.npmjs.com/settings/~/tokens"),
    "pypi": ("PyPI", "https://pypi.org/manage/account/token/"), "huggingface": ("Hugging Face", "https://huggingface.co/settings/tokens"),
    "telegram": ("Telegram", "https://t.me/BotFather"), "shopify": ("Shopify", "https://admin.shopify.com/"),
    "digitalocean": ("DigitalOcean", "https://cloud.digitalocean.com/account/api/tokens"), "heroku": ("Heroku", "https://dashboard.heroku.com/account"),
    "vercel": ("Vercel", "https://vercel.com/account/tokens"), "supabase": ("Supabase", "https://supabase.com/dashboard/account/tokens"),
    "payment-card": ("your bank", None), "seed-phrase": ("your wallet", None),
}


def next_steps(rule_id):
    """Plain next steps for a leaked secret: where to revoke it, then what to do with the file."""
    key = next((k for k in REVOKE if rule_id.startswith(k) or k in rule_id), None)
    who, url = REVOKE.get(key, ("the service it belongs to", None))
    if rule_id == "seed-phrase":
        steps = ["Move the funds to a new wallet now: anyone who saw this phrase controls the wallet.", "Delete the file holding the phrase."]
    elif rule_id == "payment-card":
        steps = ["Call your bank or freeze the card in its app.", "Delete or redact the file."]
    else:
        steps = [f"Revoke this key at {who} and create a new one.", "Remove it from the file (Aureon can blank it).",
                 "If the file was ever shared or pushed to GitHub, treat the key as public even after removing it."]
    return {"who": who, "url": url, "steps": steps}


def redact_secret(path, rule_id):
    """Blank every match of that rule in a text file (keeps a .bak copy)."""
    from .noah import secret_rules
    rule = next((r for r in secret_rules() if r["id"] == rule_id), None)
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    if rule is None:
        return 0
    new, n = rule["rx"].subn(lambda m: "*" * min(len(m.group(0)), 40), text)
    if n:
        shutil.copy2(p, p.with_name(p.name + ".bak"))
        p.write_text(new, encoding="utf-8")
    return n
