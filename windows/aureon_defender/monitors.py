"""The 24/7 sensors. Each monitor has tick() -> list of event dicts, and keeps its own baseline on disk.

  FolderWatch   real-time: new/changed files in watched folders are scanned once their size settles
  Persistence   new autostart entries (Run keys, Startup folders, scheduled tasks, services)
  NetWatch      connections to known C2 IPs, new listening ports, hosts-file and DNS-server changes
  Canary        ransomware tripwire files in Documents/Desktop/Pictures
  Vitals        CPU/RAM/disk/battery + top processes (for dashboard and desktop widget)
"""
import hashlib
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

from .core import data_dir, expand, expand_all, is_system

NOWIN = 0x08000000  # CREATE_NO_WINDOW


def _load(name, default):
    p = data_dir() / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


_last_saved = {}


def _save(name, obj):
    """Write only when the content changed: idle disk writes keep SSDs out of low-power states and cost battery."""
    text = json.dumps(obj, indent=1)
    path = data_dir() / name
    if _last_saved.get(str(path)) == text and path.exists():
        return
    path.write_text(text, encoding="utf-8")
    _last_saved[str(path)] = text


def ev(severity, kind, title, detail="", **extra):
    return {"severity": severity, "kind": kind, "title": title, "detail": detail, **extra}


# ---------------- real-time folder watch ----------------
class FolderWatch:
    SKIP_EXT = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}

    def __init__(self, folders, on_file, depth=1, max_size=200 * 1024 * 1024):
        self.folders = [x for f in folders for x in expand_all(f)]
        self.on_file = on_file          # callback(path) -> event or None
        self.depth = depth
        self.max_size = max_size
        self.seen = {}                  # path -> (size, mtime) already scanned
        self.pending = {}               # path -> (size, mtime) waiting to settle
        self.primed = False

    def _walk(self, root, d):
        try:
            with os.scandir(root) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            st = e.stat()
                            yield e.path, (st.st_size, st.st_mtime)
                        elif d > 0 and e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "$")):
                            yield from self._walk(e.path, d - 1)
                    except OSError:
                        continue
        except OSError:
            return

    def snapshot(self):
        snap = {}
        for f in self.folders:
            snap.update(self._walk(f, self.depth))
        return snap

    def tick(self):
        snap = self.snapshot()
        if not self.primed:              # existing files are not rescanned on every start
            self.seen = snap
            self.primed = True
            return []
        out = []
        for p, sig in snap.items():
            if self.seen.get(p) == sig or Path(p).suffix.lower() in self.SKIP_EXT or sig[0] > self.max_size:
                continue
            if self.pending.get(p) == sig:           # unchanged since last tick -> download finished
                self.pending.pop(p)
                self.seen[p] = sig
                e = self.on_file(Path(p))
                if e:
                    out.append(e)
            else:
                self.pending[p] = sig
        for p in list(self.seen):
            if p not in snap:
                self.seen.pop(p)
        return out


# ---------------- persistence (autoruns) ----------------
RUN_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"),
]
WINLOGON_VALUES = {"Shell", "Userinit"}


def _user_hives():
    """(label, root, prefix): this user's HKCU, or every loaded user hive when running as SYSTEM."""
    import winreg
    if not is_system():
        return [("HKCU", winreg.HKEY_CURRENT_USER, "")]
    out, i = [], 0
    while True:
        try:
            sid = winreg.EnumKey(winreg.HKEY_USERS, i)
        except OSError:
            break
        i += 1
        if sid.startswith("S-1-5-21-") and not sid.endswith("_Classes"):
            out.append(("HKU\\" + sid, winreg.HKEY_USERS, sid + "\\"))
    return out


def read_run_keys():
    import winreg
    out = {}
    targets = []
    for h, k in RUN_KEYS:
        if h == "HKLM":
            targets.append(("HKLM", winreg.HKEY_LOCAL_MACHINE, k))
        else:
            targets += [(label, root, prefix + k) for label, root, prefix in _user_hives()]
    for h, root, k in targets:
        try:
            with winreg.OpenKey(root, k) as key:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if k.endswith("Winlogon") and name not in WINLOGON_VALUES:
                        continue
                    out[f"{h}\\{k}\\{name}"] = str(val)
        except OSError:
            continue
    return out


def read_startup_folders():
    out = {}
    dirs = expand_all("%APPDATA%/Microsoft/Windows/Start Menu/Programs/Startup") +         [expand("%PROGRAMDATA%/Microsoft/Windows/Start Menu/Programs/StartUp")]
    for d in dirs:
        if d.exists():
            for p in d.iterdir():
                if p.name.lower() != "desktop.ini":
                    out[f"startup:{p}"] = str(p)
    return out


def read_tasks():
    try:
        out = subprocess.run(["schtasks", "/query", "/fo", "csv", "/v", "/nh"], capture_output=True, text=True,
                             timeout=60, creationflags=NOWIN, errors="ignore").stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    import csv
    tasks = {}
    for row in csv.reader(out.splitlines()):
        if len(row) > 8 and row[1].startswith("\\") and not row[1].startswith("\\Microsoft\\"):
            tasks[f"task:{row[1]}"] = row[8]
    return tasks


def read_services():
    try:
        import psutil
        services = list(psutil.win_service_iter())
    except Exception:
        return {}
    out = {}
    for s in services:
        try:
            out[f"service:{s.name()}"] = s.binpath() or ""
        except Exception:           # some services deny binpath to non-admins; still track the name
            out[f"service:{s.name()}"] = "?"
    return out


class Persistence:
    def __init__(self, readers=None, baseline_name="persistence.json"):
        self.readers = readers or [read_run_keys, read_startup_folders, read_tasks, read_services]
        self.name = baseline_name

    def current(self):
        cur = {}
        for r in self.readers:
            cur.update(r())
        return cur

    def tick(self):
        cur = self.current()
        base = _load(self.name, None)
        _save(self.name, cur)
        if base is None:
            return [ev("info", "persistence", f"Autostart baseline recorded ({len(cur)} entries)")]
        out = []
        for k, v in cur.items():
            if k not in base:
                where = k.split(":", 1)[0] if ":" in k else "registry Run key"
                out.append(ev("medium", "persistence", f"New program set to start automatically ({where})",
                              f"{k} -> {v}", target=v, key=k))
            elif base[k] != v:
                out.append(ev("medium", "persistence", "Autostart entry changed", f"{k}: {base[k]} -> {v}", target=v, key=k))
        return out


# ---------------- network ----------------
def hosts_hash():
    p = Path(r"C:\Windows\System32\drivers\etc\hosts")
    try:
        data = p.read_bytes()
    except OSError:
        return None
    # ignore Aureon's own DNS-shield block
    txt = data.decode("utf-8", errors="ignore")
    from .feeds import BEGIN, END
    if BEGIN in txt and END in txt:
        txt = txt[:txt.index(BEGIN)] + txt[txt.index(END) + len(END):]
    return hashlib.sha256(txt.strip().encode()).hexdigest()


def dns_servers():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-DnsClientServerAddress -AddressFamily IPv4 | ? ServerAddresses).ServerAddresses -join ','"],
                             capture_output=True, text=True, timeout=20, creationflags=NOWIN).stdout.strip()
        return sorted(set(filter(None, out.split(","))))
    except (OSError, subprocess.TimeoutExpired):
        return []


class NetWatch:
    RISKY = {21, 23, 135, 139, 445, 3389, 5900, 5985, 5986}

    def __init__(self, bad_ips=lambda: set(), conns=None, hosts=hosts_hash, dns=dns_servers):
        self.bad_ips = bad_ips
        self.conns = conns or self._psutil_conns
        self.hosts = hosts
        self.dns = dns
        self.alerted = set()
        self.slow_t = 0

    @staticmethod
    def _psutil_conns():
        import psutil
        out = []
        names = {}
        for c in psutil.net_connections(kind="inet"):
            name = ""
            if c.pid:
                if c.pid not in names:
                    try:
                        names[c.pid] = psutil.Process(c.pid).name()
                    except Exception:
                        names[c.pid] = ""
                name = names[c.pid]
            out.append({"status": c.status, "laddr": tuple(c.laddr) if c.laddr else None,
                        "raddr": tuple(c.raddr) if c.raddr else None, "pid": c.pid, "proc": name})
        return out

    def tick(self):
        out = []
        bad = self.bad_ips()
        listening = set()
        for c in self.conns():
            if c["raddr"] and c["raddr"][0] in bad:
                key = ("c2", c["raddr"][0], c["pid"])
                if key not in self.alerted:
                    if len(self.alerted) > 10000:
                        self.alerted.clear()
                    self.alerted.add(key)
                    out.append(ev("high", "network", f"{c['proc'] or 'A program'} is talking to a known botnet server",
                                  f"{c['raddr'][0]}:{c['raddr'][1]} (Feodo Tracker C2 list), pid {c['pid']}",
                                  pid=c["pid"], ip=c["raddr"][0]))
            if c["status"] == "LISTEN" and c["laddr"] and c["laddr"][0] in ("0.0.0.0", "::"):
                listening.add((c["laddr"][1], c["proc"]))
        base = _load("listening.json", None)
        ports = sorted({p for p, _ in listening})
        if base is None:
            _save("listening.json", ports)
        else:
            for p, proc in sorted(listening):
                if p not in base:
                    sev = "medium" if p in self.RISKY else "low"
                    out.append(ev(sev, "network", f"New port open to the network: {p}", f"opened by {proc or 'unknown'}", port=p))
            _save("listening.json", sorted(set(base) | set(ports)))
        if time.time() - self.slow_t > 60:      # hosts + DNS are cheap but not every few seconds
            self.slow_t = time.time()
            h, d = self.hosts(), self.dns()
            st = _load("netstate.json", {})
            if st.get("hosts") and h and h != st["hosts"]:
                out.append(ev("medium", "network", "The hosts file was changed",
                              "Malware edits it to redirect banks or block security updates."))
            if st.get("dns") and d and d != st["dns"]:
                out.append(ev("low", "network", "DNS servers changed", f"{', '.join(st['dns'])} -> {', '.join(d)}"))
            _save("netstate.json", {"hosts": h or st.get("hosts"), "dns": d or st.get("dns")})
        return out


# ---------------- ransomware canary ----------------
CANARY_DIRS = ["~/Documents", "~/Desktop", "~/Pictures"]


class Canary:
    def __init__(self, dirs=None, top_writers=None, on_hit=None):
        self.dirs = [x for d in (dirs or CANARY_DIRS) for x in expand_all(d)]
        self.top_writers = top_writers or self._top_writers
        self.on_hit = on_hit
        self._locked = {}

    def _paths(self):
        return [d / f"~$aureon-canary-{i}{ext}" for d in self.dirs if d.exists()
                for i, ext in ((0, ".docx"), (1, ".xlsx"))]

    def plant(self):
        state = {}
        for p in self._paths():
            if not p.exists():
                p.write_bytes(b"PK\x03\x04" + secrets.token_bytes(4096))
                if os.name == "nt":
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x2)   # hidden
            state[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        _save("canary.json", state)
        return state

    @staticmethod
    def _top_writers(window=1.0):
        """Measured only when a tripwire fires: two I/O samples `window` seconds apart."""
        import psutil

        def sample():
            out = {}
            for p in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    out[p.pid] = (p.io_counters().write_bytes, p.info["name"], p.info["exe"])
                except Exception:
                    continue
            return out
        a = sample()
        time.sleep(window)
        b = sample()
        rows = [(w - a[pid][0], pid, n, exe) for pid, (w, n, exe) in b.items() if pid in a]
        return sorted(rows, reverse=True)[:3]

    def tick(self):
        state = _load("canary.json", None) or self.plant()
        hits = []
        for path, h in state.items():
            p = Path(path)
            try:
                # Always hash: decoys are a few KB, and ransomware can overwrite in place and put the old size and
                # timestamp back, so a (size, mtime) shortcut would miss exactly the attack this is here for.
                cur = hashlib.sha256(p.read_bytes()).hexdigest()
                self._locked.pop(path, None)
            except FileNotFoundError:
                cur = None
            except OSError:
                # Briefly locked (sync clients, indexer, backup) is not tampering. Only a lock that persists for a
                # minute counts, because ransomware that holds the file open while encrypting it would look like this.
                first = self._locked.setdefault(path, time.time())
                if time.time() - first < 60:
                    continue
                cur = "locked"
            if cur != h:
                hits.append(f"{p.name} in {p.parent} was {'deleted/renamed' if cur is None else 'modified'}")
        if not hits:
            return []
        writers = self.top_writers()
        who = ", ".join(f"{n} (pid {pid}, {d // 1024} KB written)" for d, pid, n, _ in writers if d > 0) or "unknown"
        e = ev("high", "ransomware", "Ransomware tripwire touched",
               "; ".join(hits) + f". Busiest writers right now: {who}", writers=[[pid, n, exe] for _, pid, n, exe in writers])
        if self.on_hit:
            self.on_hit(e)
        self.plant()           # re-arm
        return [e]


# ---------------- vitals ----------------
def vitals():
    import psutil
    bat = psutil.sensors_battery()
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            procs.append((p.info["cpu_percent"] or 0, p.info["memory_info"].rss, p.info["name"]))
        except Exception:
            pass
    procs.sort(reverse=True)
    du = psutil.disk_usage(os.environ.get("SYSTEMDRIVE", "C:") + "\\")
    return {"cpu": psutil.cpu_percent(interval=None), "ram": psutil.virtual_memory().percent,
            "disk": du.percent, "battery": bat.percent if bat else None, "plugged": bat.power_plugged if bat else None,
            "boot": psutil.boot_time(), "top": [[n, round(c, 1), r // (1 << 20)] for c, r, n in procs[:5]]}


def keyboards_fast():
    """Present HID keyboards from the kbdhid driver's Enum key: ~1 ms, no PowerShell."""
    import winreg
    out = {}
    for svc in ("kbdhid", "i8042prt"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\{svc}\Enum") as k:
                n = winreg.QueryValueEx(k, "Count")[0]
                for i in range(n):
                    ident = winreg.QueryValueEx(k, str(i))[0]
                    out[ident] = _device_name(ident)
        except OSError:
            continue
    return out


def _device_name(ident):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Enum\{ident}") as k:
            for v in ("FriendlyName", "DeviceDesc"):
                try:
                    return winreg.QueryValueEx(k, v)[0].split(";")[-1]
                except OSError:
                    continue
    except OSError:
        pass
    return ident
