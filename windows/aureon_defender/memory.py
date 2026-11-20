"""Silent memory: a deduplicated, versioned copy of the folders people care about, kept on this machine.

Built on aureon.fold-memory (fold_memory.py, vendored unchanged from github.com/iamaureon74/aureon.fold-memory):
identical bytes are stored once, every replaced version is remembered, and a file only comes back if its
SHA-256 still matches. No network, ever.

What Keeper does, with nobody pressing anything:
  * every hour (scaled by hwguard's budget) it folds Documents, Desktop and Pictures into the store. Files that
    have not changed (same size and date) cost one index lookup. It skips its turn on low battery, while the
    disk is nearly full, and while a ransomware alarm is open.
  * the store is capped (default: 15% of the free disk, never more than memory_max_gb). Over the cap it keeps
    fewer old versions and gives the space back. Unique bytes cannot shrink; that floor is reported honestly.
  * when the ransomware tripwire fires, rollback() puts back the last good version of every watched file that
    was overwritten with encrypted-looking bytes, or renamed to name.ext.<something> and encrypted, since just
    before the alarm. The encrypted copy is deleted. Files that changed normally are left alone.
  * dupes() lists the copies still sitting on the source disk. They are reported, never deleted: two copies of
    a file in two folders can be on purpose.
"""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from . import fold_memory as fm
from . import hwguard

EXCLUDES = ["*.tmp", "~$*", "*.crdownload", "*.part", "*.partial", "Thumbs.db", "desktop.ini", ".DS_Store",
            "node_modules", ".git", "__pycache__", ".venv", "*.iso", "*.vhd", "*.vhdx", "*.vmdk", "*.qcow2",
            "*.aureon-quarantined-*", ".fold-*"]
ENCRYPTED = 7.2          # bits per byte: compressed or encrypted
PLAIN = 6.6              # below this, ordinary documents, text and most office files


def default_folders(home=None):
    home = Path(home or Path.home())
    return [p for p in (home / "Documents", home / "Desktop", home / "Pictures") if p.is_dir()]


def default_store():
    base = os.environ.get("AUREON_MEMORY")
    if base:
        return Path(base)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aureon" / "memory"
    if os.sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Aureon" / "memory"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "aureon" / "memory"


def entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def _ts(iso):
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return 0.0


class Keeper:
    def __init__(self, store=None, folders=None, settings=None, now=time.time, power=None, disk=None, hw=None):
        self.store = Path(store or default_store())
        self.folders = [Path(f) for f in (folders if folders is not None else default_folders())]
        self.s = settings or {}
        self.now = now
        self.power = power or self._power
        self.disk = disk or self._disk
        self.hw = hw or hwguard.profile()
        self.paused_until = 0.0
        self.next_run = 0.0
        self.status_path = self.store.parent / "memory-status.json"
        self.last = {}

    # ---------------- conditions ----------------
    @staticmethod
    def _power():
        try:
            import psutil
            b = psutil.sensors_battery()
            return {"plugged": True, "percent": None} if b is None else {"plugged": bool(b.power_plugged), "percent": b.percent}
        except Exception:
            return {"plugged": True, "percent": None}

    def _disk(self):
        import shutil
        self.store.mkdir(parents=True, exist_ok=True)
        u = shutil.disk_usage(str(self.store))
        return {"total": u.total, "free": u.free}

    def cap_bytes(self, store_bytes=0):
        d = self.disk()
        pct = float(self.s.get("memory_cap_percent", 15)) / 100
        hard = float(self.s.get("memory_max_gb", 50)) * 2**30
        return int(min(hard, (d["free"] + store_bytes) * pct))

    def why_not(self):
        """Reason to skip this turn, or '' when it should run."""
        if not self.s.get("memory", True):
            return "off"
        if self.now() < self.paused_until:
            return "paused while a ransomware alarm is handled"
        p = self.power()
        if not p.get("plugged") and (p.get("percent") or 100) < 40:
            return "on battery below 40%"
        d = self.disk()
        if d["free"] < max(2 * 2**30, d["total"] * 0.10):
            return "less than 10% of the disk is free"
        if not self.folders:
            return "no folders to keep"
        return ""

    def pause(self, seconds=3600):
        self.paused_until = max(self.paused_until, self.now() + seconds)

    # ---------------- the job ----------------
    def tick(self):
        if self.now() < self.next_run:
            return None
        self.next_run = self.now() + 3600 * self.hw.get("interval_scale", 1.0)
        why = self.why_not()
        if why:
            self._save({"t": self.now(), "skipped": why})
            return None
        return self.run_once()

    def run_once(self):
        limit_mb = 256 if self.hw.get("tier") == "lite" else 2048
        counts = {"new": 0, "unchanged": 0, "skip": 0}
        t0 = self.now()
        with fm.FoldMemory(self.store, level="fast" if self.hw.get("tier") == "lite" else "default",
                           jobs=self.hw.get("scan_workers", 1)) as m:
            for root in self.folders:
                for dirpath, dirs, names in os.walk(root):
                    dirs[:] = [d for d in dirs if not any(Path(d).match(p) for p in EXCLUDES) and not d.startswith(".")]
                    for name in names:
                        p = Path(dirpath) / name
                        if any(p.match(x) for x in EXCLUDES) or self.now() < self.paused_until:
                            counts["skip"] += 1
                            continue
                        try:
                            if p.stat().st_size > limit_mb * 2**20:
                                counts["skip"] += 1
                                continue
                        except OSError:
                            continue
                        r = m.ingest_file(p, commit=False)
                        st = r.get("status")
                        counts["unchanged" if st == "unchanged" else "skip" if st == "skip" else "new"] += 1
                m.flush()
            st = m.stats()
            trimmed = self._fit(m, st)
            if trimmed:
                st = m.stats()
        self.last = {"t": self.now(), "seconds": round(self.now() - t0, 1), **counts,
                     "files_held": st["files_held"], "old_versions": st["old_versions_held"],
                     "disk_bytes": st["disk_bytes"], "logical_bytes": st["logical_bytes"],
                     "saved_bytes": st["saved_by_copies"] + st["saved_by_squeeze"], "cap_bytes": self.cap_bytes(st["disk_bytes"]),
                     "trimmed": trimmed, "folders": [str(f) for f in self.folders]}
        self._save(self.last)
        return self.last

    def _fit(self, m, st):
        """Over the cap: keep fewer old versions (10 -> 5 -> 2) and give the space back."""
        cap = self.cap_bytes(st["disk_bytes"])
        if st["disk_bytes"] <= cap:
            return 0
        dropped = 0
        for keep in (10, 5, 2):
            dropped += m.prune(keep).get("versions_dropped", 0)
            m.gc()
            if m.stats()["disk_bytes"] <= cap:
                break
        return dropped

    def _save(self, d):
        try:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(d), encoding="utf-8")
            os.replace(tmp, self.status_path)
        except OSError:
            pass

    def status(self):
        try:
            return json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    # ---------------- ransomware rollback ----------------
    def _good_version(self, m, path, since, before):
        """Newest version held before the alarm that is trustworthy: held before the attack window began, or
        held inside it but not encrypted-looking (a dense original from inside the window could be ransom)."""
        try:
            vs = m.versions(str(path))["versions"]
        except LookupError:
            return None
        for v in vs:
            held = _ts(v["held_since"])
            if held >= before:
                continue
            head = b""
            for part in m.iter_unfold(v["file_sha"]):
                head += part
                if len(head) >= 65536:
                    break
            if held < since - 1 or entropy(head[:65536]) < ENCRYPTED or len(head) < 256:   # -1: held_since has 1 s resolution
                return v["file_sha"], head[:65536]
        return None

    def rollback(self, since, before=None):
        """Put back files encrypted or renamed-and-encrypted after `since` (unix time), from the last trustworthy
        version held before `before` (the alarm; default now). Returns what was restored."""
        before = self.now() if before is None else before
        self.pause(1800)
        restored, skipped = [], 0
        if not self.store.exists():
            return {"restored": [], "skipped": 0, "note": "nothing held yet"}
        with fm.FoldMemory(self.store) as m:
            rows = m.db().execute("SELECT DISTINCT path FROM locations UNION SELECT DISTINCT path FROM history").fetchall()
            roots = [os.path.abspath(str(f)) for f in self.folders]
            for (path,) in rows:
                if not any(os.path.abspath(path).startswith(r + os.sep) for r in roots):
                    continue
                p = Path(path)
                victim = None
                if p.exists():
                    try:
                        if p.stat().st_mtime < since:
                            continue
                        with open(p, "rb") as f:
                            now_head = f.read(65536)
                    except OSError:
                        continue
                    if entropy(now_head) >= ENCRYPTED:
                        victim = p
                else:
                    for sib in p.parent.glob(p.name + ".*") if p.parent.exists() else []:
                        try:
                            if sib.stat().st_mtime >= since:
                                with open(sib, "rb") as f:
                                    if entropy(f.read(65536)) >= ENCRYPTED:
                                        victim = sib
                                        break
                        except OSError:
                            continue
                if victim is None:
                    continue
                good = self._good_version(m, p, since, before)
                if not good:
                    skipped += 1
                    continue
                sha, old_head = good
                if victim == p and entropy(old_head) >= PLAIN and old_head[:4] == now_head[:4]:
                    skipped += 1                     # was already dense and kept its header: a normal edit, not ransom
                    continue
                res = m.unfold(sha, dest=str(p))
                if not res.get("ok"):
                    skipped += 1
                    continue
                if victim != p:
                    try:
                        victim.unlink()
                    except OSError:
                        pass
                restored.append(str(p))
        out = {"restored": restored, "skipped": skipped, "since": since, "t": self.now()}
        self._save({**self.status(), "rollback": out})
        return out

    def dupes(self, limit=20):
        if not self.store.exists():
            return {"groups": 0, "top": []}
        with fm.FoldMemory(self.store) as m:
            return m.dupes(limit=limit)
