"""Empty the trash automatically: items deleted more than N days ago are removed for good.

Windows: every fixed drive's  X:\\$Recycle.Bin\\<user SID>\\  holds pairs  $Ixxxx (deletion record) + $Rxxxx (content).
         The deletion time is the FILETIME at byte 16 of $I (same in format v1 and v2).
Linux:   freedesktop trash  ~/.local/share/Trash/{info/*.trashinfo, files/*}  with  DeletionDate=YYYY-MM-DDThh:mm:ss.

Using the recorded deletion time (not the file's own date) means something deleted yesterday is never purged just
because the file itself is old. Windows restore points, shadow copies and File History are deliberately untouched:
they are how a machine recovers from ransomware.
"""
import os
import shutil
import struct
import time
from datetime import datetime
from pathlib import Path

EPOCH_DIFF = 11644473600          # seconds between 1601-01-01 and 1970-01-01


def _rm(p: Path):
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def recycle_deleted_at(info: Path):
    try:
        with open(info, "rb") as f:
            head = f.read(24)
        if len(head) < 24 or struct.unpack("<Q", head[:8])[0] not in (1, 2):
            return None
        ft = struct.unpack("<Q", head[16:24])[0]
        return ft / 10_000_000 - EPOCH_DIFF
    except OSError:
        return None


def recycle_bins():
    """$Recycle.Bin\\<SID> folders on every fixed drive (all users when running as SYSTEM)."""
    out = []
    if os.name == "nt":
        try:
            import psutil
            roots = [p.mountpoint for p in psutil.disk_partitions(all=False) if "fixed" in p.opts or "rw" in p.opts]
        except Exception:
            roots = [os.environ.get("SYSTEMDRIVE", "C:") + "\\"]
    else:
        roots = [r for r in os.environ.get("AUREON_RECYCLE_ROOTS", "").split(os.pathsep) if r]
    for r in roots:
        base = Path(r) / "$Recycle.Bin"
        try:
            out += [d for d in base.iterdir() if d.is_dir() and d.name.upper().startswith("S-1-")]
        except OSError:
            continue
    return out


def purge_recycle_bin(days, bins=None, now=None):
    now = time.time() if now is None else now
    cut = now - days * 86400
    removed = 0
    for b in (recycle_bins() if bins is None else bins):
        try:
            infos = [p for p in b.iterdir() if p.name.startswith("$I")]
        except OSError:
            continue
        for info in infos:
            t = recycle_deleted_at(info)
            if t is None or t > cut:
                continue
            content = info.with_name("$R" + info.name[2:])
            if content.exists() and not _rm(content):
                continue
            if _rm(info):
                removed += 1
    return removed


def linux_trash_dirs():
    if os.name == "nt":
        return []
    homes = [Path.home()]
    try:
        if os.geteuid() == 0:
            homes += [p for p in Path("/home").iterdir() if p.is_dir()]
    except OSError:
        pass
    return [h / ".local/share/Trash" for h in dict.fromkeys(homes) if (h / ".local/share/Trash").is_dir()]


def purge_freedesktop_trash(days, dirs=None, now=None):
    now = time.time() if now is None else now
    cut = now - days * 86400
    removed = 0
    for t in (linux_trash_dirs() if dirs is None else dirs):
        info_dir = t / "info"
        try:
            infos = list(info_dir.glob("*.trashinfo"))
        except OSError:
            continue
        for info in infos:
            try:
                text = info.read_text(encoding="utf-8", errors="replace")
                line = next(l for l in text.splitlines() if l.startswith("DeletionDate="))
                when = datetime.strptime(line.split("=", 1)[1].strip()[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
            except (OSError, StopIteration, ValueError):
                continue
            if when > cut:
                continue
            content = t / "files" / info.name[:-len(".trashinfo")]
            if (content.exists() or content.is_symlink()) and not _rm(content):
                continue
            if _rm(info):
                removed += 1
    return removed


def purge_all(days):
    if not days:
        return {"recycle_bin": 0, "trash": 0}
    return {"recycle_bin": purge_recycle_bin(days), "trash": purge_freedesktop_trash(days)}
