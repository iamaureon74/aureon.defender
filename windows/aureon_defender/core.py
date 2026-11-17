"""Paths, settings and the event journal shared by engine, dashboard and studio."""
import json
import os
import threading
import time
import uuid
from pathlib import Path

VERSION = "0.4.4"
APP = "aureon.defender"


def _writable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        t = p / f".w{os.getpid()}"
        t.write_text("x")
        t.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """Machine-wide state (engine). Falls back to per-user when not installed / not admin."""
    if os.environ.get("AUREON_DATA"):
        p = Path(os.environ["AUREON_DATA"])
        p.mkdir(parents=True, exist_ok=True)
        return p
    pd = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Aureon"
    if (pd / "inbox").exists():          # installed: the engine owns it; users read it (and drop requests in inbox/)
        return pd
    if _writable(pd):
        return pd
    lp = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aureon"
    lp.mkdir(parents=True, exist_ok=True)
    return lp


def user_dir() -> Path:
    p = Path(os.environ.get("AUREON_USER") or Path(os.environ.get("APPDATA", Path.home())) / "Aureon")
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = {
    "realtime": True,
    "auto_quarantine": True,            # malicious verdicts only; suspicious = alert
    "use_defender_engine": True,
    "use_yara": True,
    "use_clamav": False,
    "canary": True,
    "canary_suspend_writer": False,     # opt-in: suspend the top unsigned writer on canary hit
    "network_monitor": True,
    "persistence_monitor": True,
    "wifi_watch": True,
    "hid_guard": True,
    "hid_lock": False,
    "dns_shield_hosts": False,          # opt-in: write URLhaus malware domains into hosts file
    "feeds_online": True,               # fetch free abuse.ch feeds when online (no user data sent)
    "daily_report": True,
    "radar": True,                      # hidden-software radar sweep every 30 min
    "device_history": True,             # log every device connect/disconnect (local only, clearable)
    "sentry": True,                     # watch mic / camera / hidden screen capture
    "asset_registry": True,             # roll-call of your devices, present and past
    "hide_from_capture": False,         # hide the aureon window from screen recording
    "device_history_days": 365,
    "defender_relay": True,             # show Microsoft Defender's detections as Aureon alerts
    "block_trackers": False,            # opt-in: noah.shield's tracker list blocked system-wide via hosts
    "clipboard_guard": True,            # warn when a key / card / seed phrase sits on the clipboard
    "clipboard_clear_seconds": 60,
    "leak_audit": True,
    "abusech_key": "",                  # free Auth-Key from https://auth.abuse.ch/ (MalwareBazaar, URLhaus, ThreatFox)
    "scan_removable": True,
    "auto_clean_downloads": False,      # strip metadata from photos, audio, documents and videos as they download
    "bt_limit": 4,
    "bt_allowed": ["audio", "input", "phone", "wearable"],             # scan USB drives / SD cards when they're plugged in
    "phone_watch": True,                # scan Android/iPhone automatically when plugged in (agent)
    "watch_folders": ["~/Downloads", "~/Desktop", "%TEMP%",
                      "%APPDATA%/Microsoft/Windows/Start Menu/Programs/Startup"],
}


class Settings:
    def __init__(self, path: Path = None):
        self.path = path or (data_dir() / "settings.json")
        self._lock = threading.Lock()

    def load(self) -> dict:
        try:
            cur = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cur = {}
        return {**DEFAULTS, **{k: v for k, v in cur.items() if k in DEFAULTS}}

    def save(self, changes: dict) -> dict:
        with self._lock:
            cur = self.load()
            for k, v in changes.items():
                if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                    cur[k] = v
            self.path.write_text(json.dumps(cur, indent=1), encoding="utf-8")
            return cur


def load_json(path, default=None):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def atomic_write(path: Path, text: str, tries=20):
    """Write then swap in. On Windows a reader holding the file makes os.replace fail; retry instead of crashing."""
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for i in range(tries):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    tmp.unlink(missing_ok=True)
    return False


def log(msg, name="aureon.log"):
    """Small diagnostic log next to the data (install steps, engine start, crashes). Never raises."""
    try:
        p = data_dir() / name
        if p.exists() and p.stat().st_size > 1_000_000:
            p.replace(p.with_suffix(".old.log"))
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{os.getpid()}] {msg}\n")
    except Exception:
        pass


def expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def is_system() -> bool:
    return os.environ.get("USERNAME", "").upper() in ("SYSTEM", f"{os.environ.get('COMPUTERNAME', '').upper()}$") \
        or os.environ.get("AUREON_ALL_USERS") == "1"


def user_profiles():
    root = Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\Users")
    skip = {"public", "default", "default user", "all users", "defaultapppool"}
    out = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return out
    for p in entries:                       # one locked profile must not hide the others
        try:
            if p.name.lower() not in skip and p.is_dir() and (p / "AppData").exists():
                out.append(p)
        except OSError:
            continue
    return out


def expand_all(p: str):
    """Expand a per-user path for every real user when running as the SYSTEM engine, else for this user."""
    if not is_system():
        return [expand(p)]
    subs = {"~": "", "%USERPROFILE%": "", "%APPDATA%": "AppData/Roaming", "%LOCALAPPDATA%": "AppData/Local",
            "%TEMP%": "AppData/Local/Temp"}
    for tok, rel in subs.items():
        if p.upper().startswith(tok.upper()):
            rest = p[len(tok):].lstrip("/\\")
            out = [prof / rel / rest if rel else prof / rest for prof in user_profiles()]
            if tok == "%TEMP%":
                out.append(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Temp")
            return out
    return [expand(p)]


SEV = {"info": 0, "low": 1, "medium": 2, "high": 3}


class Journal:
    """Append-only JSONL event log, rotated at 5 MB."""

    def __init__(self, path: Path = None):
        self.path = path or (data_dir() / "events.jsonl")
        self._lock = threading.Lock()
        self.listeners = []

    def add(self, severity, kind, title, detail="", **extra):
        ev = {"id": uuid.uuid4().hex[:12], "t": time.time(), "severity": severity, "kind": kind,
              "title": title, "detail": detail, **extra}
        with self._lock:
            if self.path.exists() and self.path.stat().st_size > 5_000_000:
                self.path.replace(self.path.with_suffix(".1.jsonl"))
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev) + "\n")
        for cb in list(self.listeners):
            try:
                cb(ev)
            except Exception:
                pass
        return ev

    def recent(self, n=200, min_sev="info"):
        if not self.path.exists():
            return []
        # Read only the tail (~2 MB covers 5000 events): the dashboard polls this, so a full 5 MB read each time
        # was wasted disk I/O and CPU.
        with open(self.path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 2_000_000))
            raw = f.read()
        if size > 2_000_000:
            raw = raw.split(b"\n", 1)[-1]               # drop the partial first line
        lines = raw.decode("utf-8", errors="ignore").splitlines()[-5000:]
        out = []
        for line in reversed(lines):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if SEV.get(e.get("severity"), 0) >= SEV[min_sev]:
                out.append(e)
                if len(out) >= n:
                    break
        return out
