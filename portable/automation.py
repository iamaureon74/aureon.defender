"""Background jobs for the mac/linux companion while it's open (shared code with the windows engine).

  protect     every file in ~/Downloads (and ~/Desktop) is scanned once it finishes arriving, plus one sweep of what
              is already there. found something -> it is removed silently, unless the hardware needs it
              (hwguard.decide): confirmed malware is overwritten and deleted, suspicious files go to an encrypted
              vault that empties itself after trash_days. one line in the activity log says what and why.
  autostart   user autostart entries (~/.config/autostart, systemd user units, macOS LaunchAgents) are read
              every minute; a new or changed entry whose program or own command is flagged is removed together
              with that program. system folders are never touched (the companion runs as you, not root).
  memory      documents, desktop and pictures are folded into a deduplicated, versioned store (fold-memory)
              on the hardware budget, so any earlier version can be put back. skipped on low battery or disk.
  downloads   new files that passed the scan get a metadata-clean copy (name.clean.ext); originals are never
              changed here.
  trash       freedesktop trash items deleted more than N days ago are emptied (linux); 0 turns it off.
  drain       per-program cpu time sampled once a minute for a rough 24 h battery picture.
Everything stays on this device. Nothing here needs administrator rights.
"""
import os
import sys
import threading
import time
from pathlib import Path

_WIN = Path(__file__).resolve().parent.parent / "windows"
if _WIN.is_dir() and str(_WIN) not in sys.path:
    sys.path.insert(0, str(_WIN))

def _data_home():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Aureon"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "aureon"


if os.name != "nt":                                 # keep state in the user's own data folder, not C:\ProgramData
    os.environ.setdefault("AUREON_DATA", str(_data_home()))
    os.environ.setdefault("AUREON_USER", str(_data_home()))

from aureon_defender import drain, hwguard  # noqa: E402
from aureon_defender.clean import SUPPORTED, clean_file  # noqa: E402
from aureon_defender.trash import purge_freedesktop_trash  # noqa: E402

def autostart_dirs(home=None):
    home = Path(home or Path.home())
    if sys.platform == "darwin":
        return [home / "Library" / "LaunchAgents"]
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return [cfg / "autostart", cfg / "systemd" / "user"]


def autostart_target(entry):
    """The program an autostart entry launches, or "" when it can't be read."""
    try:
        if entry.suffix == ".plist":
            import plistlib
            with open(entry, "rb") as f:
                d = plistlib.load(f)
            args = d.get("ProgramArguments") or []
            return str(d.get("Program") or (args[0] if args else ""))
        text = entry.read_text(encoding="utf-8", errors="ignore")
        key = "ExecStart=" if entry.suffix == ".service" else "Exec="
        for line in text.splitlines():
            if line.strip().startswith(key):
                cmd = line.split("=", 1)[1].strip().lstrip("-@!+:")
                import shlex
                try:
                    parts = shlex.split(cmd)
                except ValueError:
                    parts = cmd.split()
                return parts[0] if parts else ""
    except (OSError, ValueError, Exception):
        return ""
    return ""


PARTIAL = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}


class Automation:
    def __init__(self, downloads=None, clean=True, trash_days=30, log=None, now=time.time, protect=True, watch=None):
        self.downloads = Path(downloads or Path.home() / "Downloads")
        self.watch = [Path(w) for w in (watch if watch is not None else [self.downloads, Path.home() / "Desktop"])]
        if self.downloads not in self.watch:
            self.watch.insert(0, self.downloads)
        self.clean = clean
        self.protect = protect
        self.hw = hwguard.profile()
        self.counts = {"scanned": 0, "removed": 0, "kept": 0}
        self._scanner = self._vault = None
        self.swept = False
        self.autostart_seen = None
        self.keeper = None
        self.next_autostart = 0
        self.trash_days = trash_days
        self.now = now
        self.log = log if log is not None else []
        self.seen, self.pending = None, {}
        self.meter = drain.DrainMeter()
        self.next_trash = 0
        self.stop = threading.Event()

    def note(self, title, detail="", blocked=False):
        self.log.insert(0, {"t": self.now(), "title": title, "detail": detail, **({"blocked": True} if blocked else {})})
        del self.log[200:]

    def _snap(self, folders=None):
        out = {}
        for folder in folders or [self.downloads]:
            try:
                with os.scandir(folder) as it:
                    for e in it:
                        try:
                            if e.is_file(follow_symlinks=False):
                                st = e.stat()
                                out[e.path] = (st.st_size, st.st_mtime)
                        except OSError:
                            continue
            except OSError:
                continue
        return out

    # ---------------- protection ----------------
    def scanner(self):
        if self._scanner is None:
            from aureon_defender.scanner import Scanner
            self._scanner = Scanner({"use_defender_engine": False, "use_yara": True})
        return self._scanner

    def vault(self):
        if self._vault is None:
            from aureon_defender.quarantine import Vault
            self._vault = Vault()
        return self._vault

    def check(self, path):
        """Scan one file and act on it. Returns True when the file is gone."""
        from aureon_defender.quarantine import ProtectedPath, wipe
        try:
            if path.stat().st_size > self.hw["hash_limit_mb"] * 2**20:
                return False
        except OSError:
            return False
        r = self.scanner().scan(path)
        self.counts["scanned"] += 1
        d = hwguard.decide(r, path)
        if d["action"] == "none":
            return False
        why = "; ".join(r.get("reasons", []))
        if d["action"] == "keep":
            self.counts["kept"] += 1
            self.note(f"kept {path.name}", f"{why}. {d['why']}.")
            return False
        try:
            if d["action"] == "wipe":
                wipe(path, r)
                detail = f"why: {why}. it was permanently deleted."
            else:
                self.vault().put(path, r)
                detail = f"why: {why} ({d['why']}). an encrypted copy is held for {self.trash_days or 30} days, then deleted."
        except (ProtectedPath, OSError, ValueError) as ex:
            self.note(f"found {path.name} but couldn't remove it", f"{why} ({ex})".lower())
            return False
        self.counts["removed"] += 1
        self.note(f"removed {path.name}", detail, blocked=True)
        return True

    def tick_protect(self):
        """One bounded sweep of what is already in the watched folders, the first time only."""
        if not self.protect or self.swept:
            return
        self.swept = True
        n = 0
        for path in list(self._snap(self.watch)):
            if n >= self.hw["sweep_files"] or self.stop.is_set():
                break
            p = Path(path)
            if p.suffix.lower() in PARTIAL:
                continue
            n += 1
            self.check(p)

    def tick_downloads(self):
        if not self.clean and not self.protect:
            return
        snap = self._snap(self.watch)
        if self.seen is None:                       # files already there aren't cleaned (tick_protect swept them for threats)
            self.seen = snap
            return
        for path, sig in snap.items():
            p = Path(path)
            if self.seen.get(path) == sig or p.suffix.lower() in PARTIAL:
                continue
            if self.pending.get(path) != sig:       # wait one tick so the download can finish
                self.pending[path] = sig
                continue
            self.pending.pop(path, None)
            self.seen[path] = sig
            if self.protect and self.check(p):
                self.seen.pop(path, None)
                continue
            if not self.clean or p.parent != self.downloads or p.suffix.lower() not in SUPPORTED or ".clean" in p.stem:
                continue
            try:
                res = clean_file(p, in_place=False)
                self.seen[res["written"]] = (Path(res["written"]).stat().st_size, Path(res["written"]).stat().st_mtime)
                self.note(f"clean copy made: {p.name}", "removed: " + (", ".join(res["removed"]) or "nothing we know to look for"))
            except Exception as ex:
                self.note(f"couldn't clean {p.name}", str(ex).lower())
        for path in list(self.seen):
            if path not in snap:
                self.seen.pop(path)

    def tick_autostart(self, dirs=None):
        """Remove new or changed autostart entries that launch something flagged (or are flagged themselves)."""
        if not self.protect or self.now() < self.next_autostart:
            return
        self.next_autostart = self.now() + 60 * self.hw.get("interval_scale", 1.0)
        cur = {}
        for d in dirs or autostart_dirs():
            try:
                for e in d.iterdir():
                    if e.is_file() and e.suffix in (".desktop", ".service", ".plist"):
                        st = e.stat()
                        cur[str(e)] = (st.st_size, st.st_mtime)
            except OSError:
                continue
        first = self.autostart_seen is None
        old = self.autostart_seen or {}
        self.autostart_seen = dict(cur)
        for path, sig in cur.items():
            if not first and old.get(path) == sig:
                continue
            entry = Path(path)
            target = autostart_target(entry)
            gone = False
            if target and Path(target).is_file() and not hwguard.needed_by_hardware(target):
                gone = self.check(Path(target))
            r = self.scanner().scan(entry)
            if gone or r["verdict"] in ("malicious", "suspicious"):
                why = "; ".join(r.get("reasons", [])) or "it launched a program that was just removed"
                try:
                    self.vault().put(entry, {**r, "verdict": r["verdict"] if r["verdict"] != "clean" else "suspicious"})
                    self.autostart_seen.pop(path, None)
                    self.counts["removed"] += 1
                    self.note(f"removed autostart entry {entry.name}", f"why: {why}. it will no longer start when you log in.", blocked=True)
                except (OSError, ValueError) as ex:
                    self.note(f"found autostart entry {entry.name} but couldn't remove it", f"{why} ({ex})".lower())

    def tick_memory(self):
        if not self.protect:
            return
        if self.keeper is None:
            from aureon_defender.memory import Keeper
            self.keeper = Keeper(hw=self.hw)
        res = self.keeper.tick()
        if res and res.get("new"):
            self.note(f"kept {res['new']} new or changed file{'s' if res['new'] != 1 else ''} in memory",
                      f"{res['files_held']} files held, earlier versions included. nothing left this device.")

    def tick_trash(self):
        if not self.trash_days or self.now() < self.next_trash:
            return
        self.next_trash = self.now() + 6 * 3600
        n = purge_freedesktop_trash(self.trash_days)
        try:
            self.vault().purge_older(self.trash_days)
        except OSError:
            pass
        if n:
            self.note(f"emptied {n} old item{'s' if n != 1 else ''} from the trash",
                      f"they were deleted more than {self.trash_days} days ago.")

    def run(self):
        last_drain = 0
        while not self.stop.is_set():
            for job in (self.tick_protect, self.tick_autostart, self.tick_downloads, self.tick_trash, self.tick_memory):
                try:
                    job()
                except Exception as ex:
                    self.note("a background job hit a problem", f"{type(ex).__name__}: {ex}".lower())
            if self.now() - last_drain >= 60:
                last_drain = self.now()
                try:
                    self.meter.tick()
                except Exception:
                    pass
            self.stop.wait(5 * self.hw.get("interval_scale", 1.0))

    def status(self):
        return {"protect": self.protect, "counts": dict(self.counts), "hardware": {k: self.hw.get(k) for k in
                ("tier", "capacity", "cpus", "ram_gb", "disk", "arch", "os", "interval_scale", "sweep_files")},
                "watching": [str(w) for w in self.watch if w.is_dir()], "vault": len(self.vault().list()),
                "memory": self.keeper.status() if self.keeper else {}}

    def report(self):
        return {"drain_24h": self.meter.top(), "silent": drain.silent(), "listening": drain.listeners(),
                "method": "cpu time per program (rough battery estimate)."}
