"""noah.shield, imported into aureon.defender.

noah.shield is a browser extension. Some of what it does can only happen inside a browser (cookie walls, social
feeds, shopping, search, page capture...): Aureon ships the extension itself and manages it per browser. Everything
that makes sense for the whole computer is rebuilt here so it covers every app, not just the browser:

  rules        noah's tracker / ad / security block lists  -> system-wide DNS shield (hosts file)
  yara         noah's YARA rules                           -> Aureon's file scanner
  secrets      noah's ~220 secret patterns (Gitleaks)      -> clipboard guard + folder secret scan
  clean        noah's media metadata stripper              -> lossless EXIF/GPS/XMP/IPTC removal for photos
  breach       noah's password breach check              -> k-anonymity check (only 5 hash characters leave the PC)
  looks        noah's wallpaper looks                      -> Studio presets
  host         noah's desktop companion protocol          -> Aureon answers it: brightness, Tor, local LLM
"""
import base64
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .core import VERSION, user_dir

HERE = Path(__file__).resolve().parent
NOAH = HERE / "noah_shield"                    # the bundled extension, as shipped
HOST_NAME = "com.asherin.noah_shield"
GECKO_ID = "shield@noah.asherin.com"
TOR_PORT = 9350
NOWIN = 0x08000000 if os.name == "nt" else 0


def manifest():
    return json.loads((NOAH / "manifest.json").read_text(encoding="utf-8"))


def chromium_id(key_b64=None):
    """Chromium extension id from the manifest key: first 32 hex digits of sha256(key), mapped 0-f -> a-p."""
    key = base64.b64decode(key_b64 or manifest()["key"])
    return "".join(chr(ord("a") + int(c, 16)) for c in hashlib.sha256(key).hexdigest()[:32])


# ---------------- rules -> system-wide DNS shield ----------------
_DOMAIN = re.compile(r"^\|\|([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\^$")


def rule_domains(files=("trackers.json", "security.json")):
    """Domains noah blocks outright (||domain^ and requestDomains), as a sorted list."""
    out = set()
    for f in files:
        p = NOAH / "rules" / f
        if not p.exists():
            continue
        for r in json.loads(p.read_text(encoding="utf-8")):
            if r.get("action", {}).get("type") != "block":
                continue
            c = r.get("condition", {})
            m = _DOMAIN.match(c.get("urlFilter", ""))
            if m:
                out.add(m.group(1))
            for d in c.get("requestDomains", []) or []:
                out.add(d.lower())
    return sorted(out)


# ---------------- YARA ----------------
def yara_rules_path():
    return NOAH / "rules" / "yara" / "noah.yar"


# ---------------- secrets (Gitleaks patterns from noah) ----------------
_SECRETS = None


def _js_regex(src):
    src = re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", src)          # named groups
    src = src.replace(r"\/", "/")
    return src


def secret_rules():
    global _SECRETS
    if _SECRETS is None:
        text = (NOAH / "lib" / "secret_rules.js").read_text(encoding="utf-8")
        body = text[text.index("Shield.SECRET_RULES = [") + len("Shield.SECRET_RULES = "):]
        body = body[:body.index("];") + 1]
        rules = []
        for r in json.loads(body):
            try:
                flags = re.I if "i" in r.get("flags", "") else 0
                rules.append({**r, "rx": re.compile(_js_regex(r["re"]), flags)})
            except re.error:
                continue
        _SECRETS = rules
    return _SECRETS


def shannon(s):
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in (s.count(ch) for ch in set(s)))


CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SEED_WORDS = re.compile(r"^(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}$")


def luhn(num):
    d = [int(c) for c in num if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    s = 0
    for i, v in enumerate(reversed(d)):
        if i % 2:
            v *= 2
            v -= 9 if v > 9 else 0
        s += v
    return s % 10 == 0


def find_secrets(text, limit=5):
    """[(rule id, plain description)] for secrets in text. Keyword pre-filter keeps this fast."""
    if not text or len(text) > 200_000:
        return []
    low = text.lower()
    hits = []
    for r in secret_rules():
        if r.get("kw") and not any(k in low for k in r["kw"]):
            continue
        m = r["rx"].search(text)
        if not m:
            continue
        secret = m.group(r.get("group") or 0) if (r.get("group") or 0) <= (m.re.groups or 0) else m.group(0)
        if r.get("entropy") and shannon(secret or "") < r["entropy"]:
            continue
        hits.append((r["id"], r["what"]))
        if len(hits) >= limit:
            break
    for m in CARD.finditer(text):
        if luhn(m.group(0)):
            hits.append(("payment-card", "a payment card number"))
            break
    if SEED_WORDS.match(text.strip().lower()):
        hits.append(("seed-phrase", "what looks like a crypto wallet recovery phrase"))
    return hits


def scan_secrets(root, max_files=20000, max_bytes=2_000_000):
    """Leaked keys in a folder (code, configs, notes). Returns [{path, rule, what}]."""
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    text_ext = {".txt", ".md", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env", ".py", ".js", ".ts",
                ".tsx", ".jsx", ".go", ".rs", ".java", ".cs", ".php", ".rb", ".sh", ".ps1", ".bat", ".xml", ".properties", ".tf", ""}
    out, n = [], 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            p = Path(dirpath) / f
            if p.suffix.lower() not in text_ext and not f.startswith(".env"):
                continue
            n += 1
            if n > max_files:
                return out
            try:
                if p.stat().st_size > max_bytes:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for rid, what in find_secrets(text, limit=3):
                out.append({"path": str(p), "rule": rid, "what": what})
    return out


# ---------------- clipboard guard ----------------
def clipboard_text():
    if os.name != "nt":
        return None
    import ctypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p
    k.GlobalLock.restype = ctypes.c_void_p
    if not u.IsClipboardFormatAvailable(13) or not u.OpenClipboard(None):     # CF_UNICODETEXT
        return None
    try:
        h = u.GetClipboardData(13)
        p = k.GlobalLock(ctypes.c_void_p(h)) if h else None
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            k.GlobalUnlock(ctypes.c_void_p(h))
    finally:
        u.CloseClipboard()


def clipboard_clear():
    if os.name != "nt":
        return False
    import ctypes
    u = ctypes.windll.user32
    if u.OpenClipboard(None):
        try:
            return bool(u.EmptyClipboard())
        finally:
            u.CloseClipboard()
    return False


def clipboard_seq():
    if os.name != "nt":
        return 0
    import ctypes
    return ctypes.windll.user32.GetClipboardSequenceNumber()


class ClipboardGuard:
    """Watches the clipboard (cheap: a sequence number). Secret found -> callback; optional auto-clear later."""
    def __init__(self, on_secret, clear_after=60):
        self.on_secret = on_secret
        self.clear_after = clear_after
        self.seq = clipboard_seq()
        self.armed = None                   # (seq, deadline) of a secret waiting to be cleared

    def tick(self, now=None):
        now = now or time.time()
        seq = clipboard_seq()
        if self.armed and seq == self.armed[0] and self.clear_after and now >= self.armed[1]:
            clipboard_clear()
            self.armed = None
            return "cleared"
        if seq == self.seq:
            return None
        self.seq = seq
        hits = find_secrets(clipboard_text() or "", limit=2)
        if hits:
            self.armed = (clipboard_seq(), now + self.clear_after) if self.clear_after else None
            self.on_secret(hits)
            return "secret"
        self.armed = None
        return None


# ---------------- media metadata (lossless) ----------------
JPEG_DROP = {0xE1: "EXIF/XMP", 0xED: "IPTC/Photoshop", 0xFE: "comment", 0xE3: "app3", 0xE4: "app4", 0xE5: "app5",
             0xE6: "app6", 0xE7: "app7", 0xE8: "app8", 0xE9: "app9", 0xEA: "app10", 0xEB: "app11", 0xEC: "app12", 0xEF: "app15"}
PNG_DROP = {b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME"}


def describe_metadata(path):
    """What a photo gives away: GPS, camera, serial, software, time. Uses Pillow to read, never to rewrite."""
    info = {}
    try:
        from PIL import Image, ExifTags
        with Image.open(path) as im:
            ex = im.getexif()
            if ex:
                tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
                for k in ("Make", "Model", "Software", "DateTime", "BodySerialNumber", "Artist"):
                    if tags.get(k):
                        info[k] = str(tags[k]).strip("\x00 ")
                gps = ex.get_ifd(0x8825)
                if gps:
                    info["GPS"] = "location recorded"
    except Exception:
        pass
    return info


def strip_jpeg(data):
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out, i, removed = bytearray(b"\xff\xd8"), 2, []
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError("bad JPEG marker")
        marker = data[i + 1]
        if marker == 0xDA:                                   # start of scan: copy the rest unchanged
            out += data[i:]
            break
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[i:i + 2]
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i:i + 2 + seg_len]
        keep = marker not in JPEG_DROP or (marker == 0xE2)     # keep ICC colour profile (APP2)
        if keep:
            out += seg
        else:
            removed.append(JPEG_DROP[marker])
        i += 2 + seg_len
    return bytes(out), removed


def strip_png(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    out, i, removed = bytearray(data[:8]), 8, []
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        chunk = data[i:i + 12 + ln]
        if typ in PNG_DROP:
            removed.append(typ.decode())
        else:
            out += chunk
        i += 12 + ln
        if typ == b"IEND":
            break
    return bytes(out), removed


def clean_media(path, out=None):
    """Lossless metadata removal. Writes alongside as name.clean.ext unless out is given. Returns a report."""
    p = Path(path)
    data = p.read_bytes()
    before = describe_metadata(p)
    if data[:2] == b"\xff\xd8":
        new, removed = strip_jpeg(data)
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        new, removed = strip_png(data)
    else:
        raise ValueError("only JPEG and PNG are cleaned losslessly")
    dst = Path(out) if out else p.with_name(p.stem + ".clean" + p.suffix)
    dst.write_bytes(new)
    return {"file": str(p), "written": str(dst), "removed": sorted(set(removed)), "had": before,
            "saved_bytes": len(data) - len(new)}


# ---------------- password breach check (k-anonymity) ----------------
def breach_count(password, fetch=None):
    """Times this password appears in known breaches. Only the first 5 hex digits of its SHA-1 are sent."""
    h = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, rest = h[:5], h[5:]
    if fetch is None:
        def fetch(pfx):
            req = urllib.request.Request(f"https://api.pwnedpasswords.com/range/{pfx}",
                                         headers={"User-Agent": "aureon.defender", "Add-Padding": "true"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode()
    for line in fetch(prefix).splitlines():
        suf, _, cnt = line.strip().partition(":")
        if suf == rest:
            return int(cnt or 0)
    return 0


# ---------------- looks (noah's wallpapers) ----------------
LOOKS = ["pasture", "sea", "lights", "halo", "meteor", "rings", "glitch"]


def look_path(name):
    return NOAH / "looks" / f"{name}.jpg"


def palette_from_image(path, n=4):
    """Darkest, two mids and the brightest of a 5-colour quantisation: a usable UI palette from a picture."""
    from PIL import Image
    with Image.open(path) as im:
        small = im.convert("RGB").resize((96, 54))
        q = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()[:18]
        cols = [tuple(pal[i:i + 3]) for i in range(0, 18, 3)]
        counts = sorted(q.getcolors(), reverse=True)
    lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    ordered = sorted(cols, key=lum)
    sat = lambda c: max(c) - min(c)
    accent = max(ordered[1:-1] or ordered, key=sat)
    pick = [ordered[0], ordered[1], accent, ordered[-1]][:n]
    return ["#%02x%02x%02x" % c for c in pick]


# ---------------- browsers ----------------
BROWSERS = {
    "Chrome": ("%PROGRAMFILES%/Google/Chrome/Application/chrome.exe", r"Software\Google\Chrome\NativeMessagingHosts", "chrome://extensions"),
    "Edge": ("%PROGRAMFILES(X86)%/Microsoft/Edge/Application/msedge.exe", r"Software\Microsoft\Edge\NativeMessagingHosts", "edge://extensions"),
    "Brave": ("%PROGRAMFILES%/BraveSoftware/Brave-Browser/Application/brave.exe", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts", "brave://extensions"),
    "Vivaldi": ("%LOCALAPPDATA%/Vivaldi/Application/vivaldi.exe", r"Software\Vivaldi\NativeMessagingHosts", "vivaldi://extensions"),
    "Opera": ("%LOCALAPPDATA%/Programs/Opera/opera.exe", r"Software\Opera Software\NativeMessagingHosts", "opera://extensions"),
    "Firefox": ("%PROGRAMFILES%/Mozilla Firefox/firefox.exe", r"Software\Mozilla\NativeMessagingHosts", "about:debugging#/runtime/this-firefox"),
}


PROFILE_DIRS = {"Chrome": "%LOCALAPPDATA%/Google/Chrome/User Data", "Edge": "%LOCALAPPDATA%/Microsoft/Edge/User Data",
                "Brave": "%LOCALAPPDATA%/BraveSoftware/Brave-Browser/User Data", "Vivaldi": "%LOCALAPPDATA%/Vivaldi/User Data",
                "Opera": "%APPDATA%/Opera Software/Opera Stable", "Firefox": "%APPDATA%/Mozilla/Firefox/Profiles"}


def _noah_in_profiles(browser):
    """Unpacked (Load unpacked) extensions live in the profile's Preferences, not the Extensions folder."""
    base = Path(os.path.expandvars(PROFILE_DIRS[browser]))
    if not base.exists():
        return False
    needles = (chromium_id(), GECKO_ID) if browser != "Firefox" else (GECKO_ID,)
    files = list(base.glob("*/Secure Preferences")) + list(base.glob("*/Preferences")) + list(base.glob("Secure Preferences")) \
        + list(base.glob("*/extensions.json"))
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(n in text for n in needles):
            return True
    return False


def browsers(extensions=None):
    """Installed browsers and whether noah.shield is loaded in each."""
    loaded = {e["browser"] for e in (extensions or []) if "noah" in e.get("name", "").lower()}
    loaded |= {b for b in PROFILE_DIRS if _noah_in_profiles(b)}
    out = []
    for name, (exe, _, page) in BROWSERS.items():
        p = Path(os.path.expandvars(exe))
        if not p.exists() and name == "Chrome":
            p = Path(os.path.expandvars("%PROGRAMFILES(X86)%/Google/Chrome/Application/chrome.exe"))
        if p.exists():
            out.append({"name": name, "exe": str(p), "page": page, "noah": name in loaded})
    return out


def staged_copy():
    """A stable, user-writable copy for 'Load unpacked' (browsers keep pointing at this folder)."""
    dst = user_dir() / "noah-shield"
    if not (dst / "manifest.json").exists() or json.loads((dst / "manifest.json").read_text(encoding="utf-8")).get("version") != manifest()["version"]:
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(NOAH, dst)
    return dst


def open_setup(browser):
    """Stage the extension, open the browser's extensions page and the folder to pick. Browsers don't allow
    silent installs from outside their stores, so the last click ('Load unpacked' -> this folder) is yours."""
    info = next((b for b in browsers() if b["name"] == browser), None)
    if not info:
        raise ValueError(f"{browser} is not installed")
    folder = staged_copy()
    subprocess.Popen([info["exe"], info["page"]])
    if os.name == "nt":
        subprocess.Popen(["explorer", str(folder)])
    return {"folder": str(folder), "page": info["page"]}


def register_host(exe_path=None):
    """Make Aureon noah.shield's desktop companion (brightness, Tor, local AI) for every browser, per user."""
    if os.name != "nt":
        return []
    import winreg
    exe_path = exe_path or (sys.executable if getattr(sys, "frozen", False) else None)
    if not exe_path:
        return []
    d = user_dir() / "native-host"
    d.mkdir(parents=True, exist_ok=True)
    chrome_m = {"name": HOST_NAME, "description": "aureon.defender companion for noah.shield", "path": exe_path,
                "type": "stdio", "allowed_origins": [f"chrome-extension://{chromium_id()}/"]}
    ff_m = {**{k: v for k, v in chrome_m.items() if k != "allowed_origins"}, "allowed_extensions": [GECKO_ID]}
    (d / "chromium.json").write_text(json.dumps(chrome_m, indent=1), encoding="utf-8")
    (d / "firefox.json").write_text(json.dumps(ff_m, indent=1), encoding="utf-8")
    done = []
    for name, (_, key, _) in BROWSERS.items():
        target = d / ("firefox.json" if name == "Firefox" else "chromium.json")
        try:                                     # noah's own desktop app may already be the companion: leave it
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key + "\\" + HOST_NAME) as k:
                current = winreg.QueryValueEx(k, "")[0]
            if current and Path(current).exists() and Path(current).resolve() != target.resolve():
                continue
        except OSError:
            pass
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key + "\\" + HOST_NAME, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(target))
        done.append(name)
    return done


# ---------------- native host: the protocol noah.shield speaks ----------------
def _wmi():
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        return win32com.client.GetObject("winmgmts:{impersonationLevel=impersonate}!//./root/wmi")
    except Exception:
        return None


_BRIGHT_CACHE = [0.0, None]


def brightness_get(max_age=5.0):
    """Laptop panel brightness in percent; None for external monitors. Direct WMI (ms); PowerShell only as fallback."""
    if time.time() - _BRIGHT_CACHE[0] < max_age:
        return _BRIGHT_CACHE[1]
    level = None
    w = _wmi()
    if w is not None:
        try:
            for m in w.InstancesOf("WmiMonitorBrightness"):
                level = int(m.CurrentBrightness)
                break
        except Exception:
            level = None
    else:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | Select -First 1).CurrentBrightness"],
                                 capture_output=True, text=True, timeout=30, creationflags=NOWIN).stdout.strip()
            level = int(out) if out.isdigit() else None
        except subprocess.TimeoutExpired:
            level = None
    _BRIGHT_CACHE[:] = [time.time(), level]
    return level


def brightness_set(level):
    level = max(0, min(100, int(level)))
    w = _wmi()
    if w is not None:
        try:
            for m in w.InstancesOf("WmiMonitorBrightnessMethods"):
                m.WmiSetBrightness(1, level)
                _BRIGHT_CACHE[:] = [time.time(), level]
                return True
        except Exception:
            pass
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | Select -First 1) | "
                        f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1;Brightness={level}}} | Out-Null"],
                       capture_output=True, text=True, timeout=30, creationflags=NOWIN)
    return r.returncode == 0


def find_tor():
    cands = [shutil.which("tor")]
    for base in ("%USERPROFILE%/Desktop/Tor Browser", "%LOCALAPPDATA%/Tor Browser", "%PROGRAMFILES%/Tor Browser",
                 "%USERPROFILE%/OneDrive/Desktop/Tor Browser"):
        cands.append(str(Path(os.path.expandvars(base)) / "Browser/TorBrowser/Tor/tor.exe"))
    return next((c for c in cands if c and Path(c).exists()), None)


def tor_state():
    d = user_dir() / "tor"
    log = d / "notice.log"
    st = {"installed": bool(find_tor()), "running": False, "ready": False, "bootstrapped": 0, "problem": ""}
    pidf = d / "pid"
    if pidf.exists():
        try:
            import psutil
            st["running"] = psutil.pid_exists(int(pidf.read_text()))
        except Exception:
            pass
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="ignore")[-6000:]
        m = re.findall(r"Bootstrapped (\d+)%", tail)
        if m:
            st["bootstrapped"] = int(m[-1])
            st["ready"] = st["running"] and st["bootstrapped"] >= 100
        w = re.findall(r"\[(?:warn|err)\] (.+)", tail)
        st["problem"] = w[-1][:200] if w and not st["ready"] else ""
    return st


def tor_start(country=""):
    exe = find_tor()
    if not exe:
        return {"error": "Tor isn't on this PC. Install Tor Browser from torproject.org; Aureon uses its Tor and downloads nothing itself."}
    tor_stop()
    d = user_dir() / "tor"
    d.mkdir(parents=True, exist_ok=True)
    (d / "notice.log").write_text("", encoding="utf-8")
    args = [exe, "--SocksPort", f"127.0.0.1:{TOR_PORT}", "--DataDirectory", str(d / "data"),
            "--Log", f"notice file {d / 'notice.log'}"]
    if country and re.fullmatch(r"[a-z]{2}", country):
        geo = Path(exe).parent.parent / "Data" / "Tor" / "geoip"
        if not geo.exists():
            return {"error": "this Tor has no country tables"}
        args += ["--GeoIPFile", str(geo), "--GeoIPv6File", str(geo) + "6", "--ExitNodes", "{%s}" % country, "--StrictNodes", "1"]
    p = subprocess.Popen(args, creationflags=NOWIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (d / "pid").write_text(str(p.pid))
    time.sleep(0.5)
    return tor_state()


def tor_stop():
    pidf = user_dir() / "tor" / "pid"
    if pidf.exists():
        try:
            import psutil
            psutil.Process(int(pidf.read_text())).terminate()
        except Exception:
            pass
        pidf.unlink(missing_ok=True)
    return {"ok": True}


def handle(msg):
    """One request from noah.shield -> one answer. Never raises."""
    t = (msg or {}).get("type", "")
    try:
        if t == "hello":
            return {"host": f"aureon.defender {VERSION}", "platform": "windows", "brightness": brightness_get(max_age=600) is not None,
                    "tor": tor_state()}
        if t == "brightness.get":
            lvl = brightness_get()
            return {"level": lvl} if lvl is not None else {"error": "this screen doesn't report brightness (external monitor?)"}
        if t == "brightness.set":
            return {"ok": True} if brightness_set(msg.get("level", 50)) else {"error": "brightness can't be set on this screen"}
        if t == "tor.status":
            return tor_state()
        if t == "tor.start":
            return tor_start(msg.get("country", ""))
        if t == "tor.stop":
            return tor_stop()
        if t == "tor.install":
            return {"error": "Aureon doesn't download programs. Install Tor Browser from torproject.org, then connect again."}
        if t in ("llm.classify", "agent.prompt"):
            from aureon.analyst import llm  # local Ollama / OpenAI-compatible server
            os.environ.setdefault("AUREON_LLM_MODEL", msg.get("model") or "qwen2.5:3b")
            return {"text": llm(msg.get("prompt", ""))}
        if t == "opensnitch.status":
            return {"error": "OpenSnitch is Linux-only; on Windows Aureon's network watch covers this"}
        return {"error": f"unknown request {t!r}"}
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}"}


def native_host_loop(stdin=None, stdout=None):
    """Chrome/Firefox native messaging: 4-byte little-endian length + UTF-8 JSON, both ways."""
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        raw = stdin.read(4)
        if len(raw) < 4:
            return
        n = struct.unpack("<I", raw)[0]
        msg = json.loads(stdin.read(n).decode("utf-8") or "{}")
        out = json.dumps(handle(msg)).encode("utf-8")
        stdout.write(struct.pack("<I", len(out)) + out)
        stdout.flush()
