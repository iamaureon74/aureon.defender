"""Background jobs for the mac/linux companion while it's open (shared code with the windows engine).

  downloads   new files in ~/Downloads get a metadata-clean copy (name.clean.ext) once they finish arriving;
              originals are never changed here.
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

from aureon_defender import drain  # noqa: E402
from aureon_defender.clean import SUPPORTED, clean_file  # noqa: E402
from aureon_defender.trash import purge_freedesktop_trash  # noqa: E402

PARTIAL = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}


class Automation:
    def __init__(self, downloads=None, clean=True, trash_days=30, log=None, now=time.time):
        self.downloads = Path(downloads or Path.home() / "Downloads")
        self.clean = clean
        self.trash_days = trash_days
        self.now = now
        self.log = log if log is not None else []
        self.seen, self.pending = None, {}
        self.meter = drain.DrainMeter()
        self.next_trash = 0
        self.stop = threading.Event()

    def note(self, title, detail=""):
        self.log.insert(0, {"t": self.now(), "title": title, "detail": detail})
        del self.log[200:]

    def _snap(self):
        out = {}
        try:
            with os.scandir(self.downloads) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            st = e.stat()
                            out[e.path] = (st.st_size, st.st_mtime)
                    except OSError:
                        continue
        except OSError:
            pass
        return out

    def tick_downloads(self):
        if not self.clean:
            return
        snap = self._snap()
        if self.seen is None:                       # files already there aren't touched
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
            if p.suffix.lower() not in SUPPORTED or ".clean" in p.stem:
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

    def tick_trash(self):
        if not self.trash_days or self.now() < self.next_trash:
            return
        self.next_trash = self.now() + 6 * 3600
        n = purge_freedesktop_trash(self.trash_days)
        if n:
            self.note(f"emptied {n} old item{'s' if n != 1 else ''} from the trash",
                      f"they were deleted more than {self.trash_days} days ago.")

    def run(self):
        last_drain = 0
        while not self.stop.is_set():
            for job in (self.tick_downloads, self.tick_trash):
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
            self.stop.wait(5)

    def report(self):
        return {"drain_24h": self.meter.top(), "silent": drain.silent(), "listening": drain.listeners(),
                "method": "cpu time per program (rough battery estimate)."}
