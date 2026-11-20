"""Multi-engine file scanner. Works fully offline; online only refreshes the reputation feeds.

Engines, in order (cheapest first):
  1. Reputation    - SHA-256 against local known-bad DB (MalwareBazaar feed) and user allow-list
  2. Heuristics    - delivery tricks used by real malware (double extensions, RTLO, script cradles,
                     macro documents, disk images and archives from the internet, unsigned internet EXEs)
  3. YARA          - bundled rules + any .yar the user drops in the rules folder (if yara-python is present)
  4. Microsoft Defender engine - MpCmdRun custom scan (local signatures, offline capable)
Verdict: malicious (any engine certain), suspicious (score >= 50), clean.
"""
import hashlib
import math
import os
import re
import sqlite3
import subprocess
import threading
import zipfile
from pathlib import Path

from collections import OrderedDict

from .core import data_dir
from .governor import child_flags

EXEC_EXT = {".exe", ".scr", ".com", ".pif", ".dll", ".cpl", ".msi", ".msix", ".appx"}
SCRIPT_EXT = {".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".bat", ".cmd", ".lnk", ".url"}
CONTAINER_EXT = {".iso", ".img", ".vhd", ".vhdx"}
ARCHIVE_EXT = {".zip"}
MACRO_EXT = {".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".xlam"}
OLE_EXT = {".doc", ".xls", ".ppt"}
DOC_LURE = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".png", ".txt", ".mp4", ".mp3", ".zip"}
MAX_READ = 8 * 1024 * 1024
OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")

SCRIPT_IOC = [
    (r"frombase64string", 25, "decodes base64 payload"),
    (r"\b-e(nc(odedcommand)?)?\s+[a-z0-9+/=]{40,}", 40, "encoded PowerShell command"),
    (r"\biex\b|invoke-expression", 25, "executes downloaded text (IEX)"),
    (r"downloadstring|downloadfile|invoke-webrequest|\biwr\b|start-bitstransfer|net\.webclient", 25, "downloads from the internet"),
    (r"wscript\.shell|shell\.application", 15, "launches programs via WScript"),
    (r"-w(indowstyle)?\s+hidden|-nop\b|-noprofile", 15, "hides its window"),
    (r"add-mppreference|set-mppreference\s+-disable", 50, "tampers with Defender"),
    (r"vssadmin\s+delete\s+shadows|wbadmin\s+delete|bcdedit\s+/set.*recoveryenabled\s+no", 60, "deletes backups (ransomware behaviour)"),
    (r"mshta\s+(http|vbscript|javascript)", 40, "abuses mshta"),
    (r"regsvr32\s+/s\s+/n\s+/u\s+/i:http", 50, "abuses regsvr32 (squiblydoo)"),
    (r"certutil\s+-urlcache|certutil\s+-decode", 40, "abuses certutil to download/decode"),
    (r"rundll32\s+\S+,\s*\w+", 15, "runs DLL exports"),
]

_cache_sig = OrderedDict()           # bounded LRU: the engine runs for months
_CACHE_MAX = 4096
_lock = threading.Lock()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def zone_id(path: Path):
    """Mark-of-the-Web: 3 = Internet, 4 = Restricted. None if no Zone.Identifier stream."""
    try:
        with open(str(path) + ":Zone.Identifier", encoding="utf-8", errors="ignore") as f:
            m = re.search(r"ZoneId=(\d)", f.read())
            return int(m.group(1)) if m else None
    except OSError:
        return None


def authenticode(path: Path):
    """'Valid' / 'NotSigned' / 'HashMismatch' / ... via Get-AuthenticodeSignature (cached by path+mtime)."""
    st = path.stat()
    key = (str(path), st.st_mtime, st.st_size)
    with _lock:
        if key in _cache_sig:
            _cache_sig.move_to_end(key)
            return _cache_sig[key]
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              f"(Get-AuthenticodeSignature -LiteralPath '{str(path).replace(chr(39), chr(39) * 2)}').Status"],
                             capture_output=True, text=True, timeout=20, creationflags=child_flags()).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = "Unknown"
    out = out or "Unknown"
    with _lock:
        _cache_sig[key] = out
        while len(_cache_sig) > _CACHE_MAX:
            _cache_sig.popitem(last=False)
    return out


# ---------------- reputation DB ----------------
class Reputation:
    def __init__(self, path: Path = None):
        self.path = path or (data_dir() / "reputation.db")
        with self._db() as db:
            db.execute("create table if not exists bad(sha256 text primary key, source text, name text)")
            db.execute("create table if not exists allow(sha256 text primary key, note text)")
            db.execute("create table if not exists meta(k text primary key, v text)")

    def _db(self):
        return sqlite3.connect(self.path, timeout=10)

    def lookup(self, h):
        with self._db() as db:
            if db.execute("select 1 from allow where sha256=?", (h,)).fetchone():
                return "allow", None
            r = db.execute("select source, name from bad where sha256=?", (h,)).fetchone()
            return ("bad", r) if r else (None, None)

    def add_bad(self, rows):
        with self._db() as db:
            db.executemany("insert or replace into bad values(?,?,?)", rows)

    def allow(self, h, note=""):
        with self._db() as db:
            db.execute("insert or replace into allow values(?,?)", (h, note))

    def count(self):
        with self._db() as db:
            return db.execute("select count(*) from bad").fetchone()[0]

    def set_meta(self, k, v):
        with self._db() as db:
            db.execute("insert or replace into meta values(?,?)", (k, str(v)))

    def meta(self, k, default=None):
        with self._db() as db:
            r = db.execute("select v from meta where k=?", (k,)).fetchone()
            return r[0] if r else default


# ---------------- engines ----------------
def heuristics(path: Path, head: bytes):
    """Returns list of (score, reason)."""
    hits = []
    name = path.name
    low = name.lower()
    ext = path.suffix.lower()
    zone = zone_id(path)
    from_net = zone in (3, 4)

    if "\u202e" in name:
        hits.append((80, "filename uses right-to-left override to fake its extension"))
    parts = low.split(".")
    if len(parts) >= 3 and "." + parts[-1] in EXEC_EXT | SCRIPT_EXT and "." + parts[-2] in DOC_LURE:
        hits.append((60, f"double extension: looks like .{parts[-2]} but is .{parts[-1]}"))
    if re.search(r"\s{5,}\.\w+$", name):
        hits.append((40, "long run of spaces hides the real extension"))

    if ext in SCRIPT_EXT or (ext == ".txt" and head[:2] != b"MZ"):
        text = head.decode("utf-8", errors="ignore").lower()
        if ext in {".ps1", ".bat", ".cmd", ".lnk", ".hta", ".vbs", ".js", ".wsf", ".jse", ".vbe", ".url"} or "powershell" in text:
            for pat, score, why in SCRIPT_IOC:
                if re.search(pat, text):
                    hits.append((score, why))
        if ext == ".lnk":
            raw = head.decode("utf-16-le", errors="ignore").lower() + head.decode("latin-1").lower()
            if any(t in raw for t in ("powershell", "cmd.exe", "mshta", "wscript", "rundll32", "certutil")):
                hits.append((55, "shortcut launches a command interpreter"))
        if ext in {".hta", ".vbe", ".jse", ".wsf"} and from_net:
            hits.append((35, f"{ext} script downloaded from the internet"))

    if ext in CONTAINER_EXT and from_net:
        hits.append((35, "disk image from the internet (common way to bypass Mark-of-the-Web)"))

    if ext in MACRO_EXT or ext in {".docx", ".xlsx", ".pptx"}:
        try:
            with zipfile.ZipFile(path) as z:
                if any(n.lower().endswith("vbaproject.bin") for n in z.namelist()):
                    hits.append((45 if from_net else 25, "Office document contains macros"))
        except (zipfile.BadZipFile, OSError):
            pass
    if ext in OLE_EXT and head[:8] == OLE_MAGIC and ("_VBA_PROJECT".encode("utf-16-le") in head or b"Attribut\x00e VB_Name" in head):
        hits.append((45 if from_net else 25, "legacy Office document contains macros"))

    if ext in ARCHIVE_EXT:
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                inner = [i.filename.lower() for i in infos]
                if any(i.flag_bits & 0x1 for i in infos) and from_net:
                    hits.append((30, "password-protected archive from the internet (hides content from scanners)"))
                bad = [n for n in inner if Path(n).suffix in EXEC_EXT | SCRIPT_EXT | CONTAINER_EXT]
                if bad and from_net:
                    hits.append((30, f"archive from the internet contains executable content: {bad[0]}"))
        except (zipfile.BadZipFile, OSError):
            pass

    hits += posix_heuristics(path, head, ext, low)

    if head[:2] == b"MZ":
        if ext not in EXEC_EXT | {".sys", ".ocx", ".efi", ".node", ".pyd"}:
            hits.append((60, f"Windows program disguised as {ext or 'no extension'}"))
        if from_net or ext in EXEC_EXT and str(path.parent).lower().endswith(("downloads", "temp", "desktop")):
            sig = authenticode(path)
            if sig == "HashMismatch":
                hits.append((70, "digital signature is broken (file was modified after signing)"))
            elif sig == "NotSigned":
                hits.append((25 if from_net else 10, "program is not digitally signed"))
                if entropy(head[:262144]) > 7.4:
                    hits.append((15, "packed/encrypted program body"))
    return hits


# Linux / macOS programs and droppers. Plain byte and text patterns; same scoring scale as above.
POSIX_MAGIC = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf")
POSIX_EXEC_EXT = {"", ".bin", ".run", ".elf", ".so", ".dylib", ".o", ".out", ".app", ".appimage", ".command", ".sh", ".x86_64", ".aarch64"}
SHELL_IOC = [
    (r"(curl|wget)\s[^|;]*\|\s*(ba|z|da)?sh\b", 45, "downloads a script and pipes it straight into a shell"),
    (r"base64\s+(-d|--decode)[^|]*\|\s*(ba|z)?sh", 50, "decodes hidden base64 and runs it"),
    (r"/dev/tcp/\d{1,3}(\.\d{1,3}){3}/\d+", 70, "opens a reverse shell over /dev/tcp"),
    (r"\bnc(at)?\b[^\n]*\s-e\s*/bin/(ba)?sh", 70, "netcat reverse shell"),
    (r"chmod\s+\+x\s+/tmp/\S+\s*(;|&&)\s*/tmp/", 40, "drops a program in /tmp and runs it"),
    (r"(crontab\s+-|/etc/cron\.d/|launchctl\s+load|~/library/launchagents)", 30, "installs itself to start automatically"),
    (r"xmrig|stratum\+tcp://|minerd\b", 60, "cryptocurrency miner"),
    (r"history\s+-c|unset\s+histfile|rm\s+-rf\s+~?/?\.bash_history", 30, "erases shell history to hide its tracks"),
    (r"osascript\s+-e\s+['\"]?.*(password|keychain)", 50, "asks for your password through a fake system dialog"),
    (r"security\s+(find-generic-password|dump-keychain)", 55, "reads passwords from the macOS keychain"),
]


def posix_heuristics(path, head, ext, low):
    """Disguised ELF/Mach-O programs, shell droppers and rogue launchers (Linux .desktop, macOS .command)."""
    hits = []
    if head[:4] in POSIX_MAGIC and ext not in POSIX_EXEC_EXT and not low.endswith((".so", ".dylib")) and ".so." not in low:
        hits.append((60, f"Linux/macOS program disguised as {ext or 'no extension'}"))
    if ext in {".sh", ".command", ".bash", ".zsh", ".desktop", ".py", ".pl", ".plist", ".service"} or head[:2] == b"#!":
        text = head[:262144].decode("utf-8", errors="ignore").lower()
        for pat, score, why in SHELL_IOC:
            if re.search(pat, text):
                hits.append((score, why))
        if ext in {".plist", ".service"} and hits:
            hits.append((25, "a login launcher runs that command every time you sign in"))
        if ext == ".desktop" and re.search(r"^exec\s*=.*(curl|wget|bash\s+-c|sh\s+-c|python3?\s+-c|base64)", text, re.M):
            hits.append((55, "desktop launcher runs a hidden command instead of an app"))
    return hits


class Yara:
    def __init__(self, rules_dirs):
        self.rules = None
        try:
            import yara
        except ImportError:
            self.error = "yara-python not installed"
            return
        files = {}
        for d in rules_dirs:
            for p in Path(d).glob("*.yar"):
                files[p.stem] = str(p)
        try:
            self.rules = yara.compile(filepaths=files) if files else None
            self.error = None if files else "no rules"
        except yara.Error as e:
            self.error = str(e)

    def scan(self, path):
        if not self.rules:
            return []
        try:
            return [m.rule for m in self.rules.match(str(path), timeout=30)]
        except Exception:
            return []


def mpcmdrun():
    plat = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows Defender/Platform"
    cands = sorted(plat.glob("*/MpCmdRun.exe"), reverse=True) if plat.exists() else []
    cands.append(Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Windows Defender/MpCmdRun.exe")
    return next((c for c in cands if c.exists()), None)


def defender_scan(path: Path):
    """Microsoft Defender engine, local signatures. Returns (status, detail): threat/clean/unavailable."""
    exe = mpcmdrun()
    if not exe:
        return "unavailable", "MpCmdRun.exe not found"
    try:
        p = subprocess.run([str(exe), "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
                           capture_output=True, text=True, timeout=120, creationflags=child_flags())
    except (OSError, subprocess.TimeoutExpired) as e:
        return "unavailable", str(e)
    out = p.stdout + p.stderr
    if p.returncode == 2 or re.search(r"found\s+[1-9]\d*\s+threats?", out, re.I):
        m = re.search(r"Threat\s*:\s*(\S+)", out)
        return "threat", m.group(1) if m else "threat found"
    if p.returncode == 0:
        return "clean", ""
    return "unavailable", out.strip().splitlines()[-1] if out.strip() else f"exit {p.returncode}"


class Scanner:
    def __init__(self, settings=None, reputation=None, rules_dirs=None):
        self.settings = settings or {}
        self.rep = reputation or Reputation()
        bundled = Path(__file__).parent / "rules"
        noah = Path(__file__).parent / "noah_shield" / "rules" / "yara"         # noah.shield's own rules
        self.yara = Yara([bundled, noah, data_dir() / "rules", *(rules_dirs or [])]) if self.settings.get("use_yara", True) else None

    def scan(self, path):
        path = Path(path)
        res = {"path": str(path), "verdict": "clean", "score": 0, "reasons": [], "engines": {}}
        try:
            st = path.stat()
            if not path.is_file():
                res["verdict"] = "skipped"
                return res
            res["size"] = st.st_size
            res["sha256"] = h = sha256(path)
            with open(path, "rb") as f:
                head = f.read(min(MAX_READ, st.st_size))
        except OSError as e:
            res.update(verdict="skipped" if isinstance(e, (PermissionError, FileNotFoundError)) or getattr(e,"winerror",None) in (2,3,5,32,33) else "error", reasons=[str(e)], skip_reason="File unavailable, access denied or locked" if isinstance(e,(PermissionError,FileNotFoundError)) or getattr(e,"winerror",None) in (2,3,5,32,33) else "")
            return res

        state, row = self.rep.lookup(h)
        res["engines"]["reputation"] = state or "unknown"
        if state == "allow":
            res["reasons"].append("on your allow-list")
            return res
        if state == "bad":
            res["verdict"] = "malicious"
            res["score"] = 100
            res["reasons"].append(f"known malware ({row[1] or 'unnamed'}, source {row[0]})")
            return res

        hits = heuristics(path, head)
        res["engines"]["heuristics"] = len(hits)
        if self.yara and self.yara.rules:
            matched = self.yara.scan(path)
            res["engines"]["yara"] = matched
            for r in matched:
                hits.append((70, f"YARA rule {r}"))
        if self.settings.get("use_defender_engine", True) and (hits or path.suffix.lower() in EXEC_EXT | SCRIPT_EXT | MACRO_EXT | OLE_EXT | CONTAINER_EXT | ARCHIVE_EXT):
            dst, detail = defender_scan(path)
            res["engines"]["defender"] = dst
            if dst == "threat":
                res["verdict"] = "malicious"
                res["score"] = 100
                res["reasons"].append(f"Microsoft Defender engine: {detail}")
        score = min(100, sum(s for s, _ in hits))
        if self.settings.get("use_clamav", False):
            from .integrations import clamav_scan
            state, detail = clamav_scan(path)
            res["engines"]["clamav"] = state
            if state == "threat":
                res["verdict"] = "malicious"
                res["score"] = 100
                res["reasons"].append("ClamAV: " + detail)
        res["score"] = max(res["score"], score)
        res["reasons"] += [r for _, r in hits]
        if res["verdict"] != "malicious":
            res["verdict"] = "malicious" if score >= 90 else "suspicious" if score >= 50 else "clean"
        return res
