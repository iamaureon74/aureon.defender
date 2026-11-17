"""Quarantine: files are moved into the vault, XOR-scrambled so they can't run or be re-detected,
with metadata to restore them exactly.

Safety rules (removing a threat must never break the machine or lose data):
  * The scrambled copy is written, flushed to disk and re-hashed before the original is touched. If the copy
    doesn't verify (disk full, I/O error) the original stays where it is.
  * Operating-system files (Windows, boot, drivers, Program Files of the OS vendor) are never moved
    automatically: removing a loaded system DLL or driver can stop Windows from booting. They raise
    ProtectedPath so the caller reports them for review instead.
  * A file held open by a running program can't be deleted on Windows. Instead of failing, the original is
    renamed out of the way when possible, or scheduled for removal at the next restart (MoveFileEx), so the
    running process keeps working until reboot and the system never crashes mid-removal.
"""
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from .core import data_dir

KEY = bytes(range(37, 37 + 64))
_CHUNK = 1 << 20                       # multiple of len(KEY): every full chunk starts at key offset 0
_QID = re.compile(r"^[0-9a-f]{12}$")


class ProtectedPath(ValueError):
    """The file belongs to the operating system; it is reported, never moved automatically."""


def _keystream(n, offset=0):
    rep = KEY[offset % len(KEY):] + KEY * (n // len(KEY) + 2)
    return rep[:n]


def _xor_bytes(chunk, offset=0):
    """Whole-chunk XOR via big integers: ~100x faster than a per-byte generator (less CPU, less battery)."""
    if not chunk:
        return b""
    ks = _keystream(len(chunk), offset)
    return (int.from_bytes(chunk, "little") ^ int.from_bytes(ks, "little")).to_bytes(len(chunk), "little")


def _xor(src, dst):
    """Scramble/unscramble src into dst. Returns sha256 of the *plain* side read from src."""
    h_in = hashlib.sha256()
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        i = 0
        for chunk in iter(lambda: fi.read(_CHUNK), b""):
            h_in.update(chunk)
            fo.write(_xor_bytes(chunk, i))
            i += len(chunk)
        fo.flush()
        os.fsync(fo.fileno())
    return h_in.hexdigest()


def _unscrambled_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        i = 0
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(_xor_bytes(chunk, i))
            i += len(chunk)
    return h.hexdigest()


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p))).replace("/", "\\").rstrip("\\") + "\\"


def protected_roots():
    sysroot = os.environ.get("SYSTEMROOT", r"C:\Windows")
    drive = os.environ.get("SYSTEMDRIVE", "C:")
    roots = [sysroot, drive + r"\Boot", drive + r"\EFI", drive + r"\Recovery", drive + r"\System Volume Information",
             drive + r"\$Recycle.Bin", os.environ.get("PROGRAMFILES", r"C:\Program Files") + r"\Windows Defender",
             os.environ.get("PROGRAMFILES", r"C:\Program Files") + r"\WindowsApps",
             os.environ.get("PROGRAMDATA", r"C:\ProgramData") + r"\Microsoft\Windows Defender"]
    import sys
    if getattr(sys, "frozen", False):                       # Aureon's own program folder: never quarantine itself
        roots.append(str(Path(sys.executable).resolve().parent))
    return [_norm(r) for r in roots]


def scannable_exceptions():
    """Inside protected roots but writable by ordinary programs, so malware drops files there: still quarantined."""
    sysroot = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return [_norm(sysroot + r"\Temp"), _norm(sysroot + r"\Downloaded Program Files"),
            _norm(sysroot + r"\Tasks"), _norm(sysroot + r"\System32\Tasks")]


PROTECTED_NAMES = {"bootmgr", "pagefile.sys", "hiberfil.sys", "swapfile.sys", "ntldr", "bootnxt"}


def is_protected(path) -> bool:
    """True for files whose removal could stop Windows booting or break the security stack."""
    p = _norm(path)
    if Path(str(path)).name.lower() in PROTECTED_NAMES:
        return True
    if os.name != "nt" and not os.environ.get("AUREON_PROTECT_TEST"):
        return False
    if any(p.startswith(r) for r in scannable_exceptions()):
        return False
    return any(p.startswith(r) for r in protected_roots())


def _delete_on_reboot(path) -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
        return bool(ctypes.windll.kernel32.MoveFileExW(str(path), None, MOVEFILE_DELAY_UNTIL_REBOOT))
    except Exception:
        return False


def _remove_original(path: Path):
    """Returns 'removed' | 'renamed-pending-reboot' | 'pending-reboot'. Raises OSError if nothing worked."""
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass
    try:
        path.unlink()
        return "removed"
    except FileNotFoundError:
        return "removed"
    except OSError as first:
        # In use by a running program: move it aside (Windows allows renaming many open files) so it can't be
        # launched again by name, then finish removal on the next restart. The running process is left alone.
        aside = path.with_name(path.name + f".aureon-quarantined-{uuid.uuid4().hex[:6]}")
        try:
            os.replace(path, aside)
            if _delete_on_reboot(aside):
                return "renamed-pending-reboot"
            try:
                aside.unlink()
                return "removed"
            except OSError:
                return "renamed-pending-reboot"
        except OSError:
            pass
        if _delete_on_reboot(path):
            return "pending-reboot"
        raise first


def wipe(path, result=None):
    """Permanently remove a confirmed threat: overwrite its bytes, rename it to a random name, then delete it.

    Overwriting stops the content being trivially undeleted from the file system. On SSDs, wear-levelling means the
    old blocks can still physically exist until TRIM; no software can promise otherwise. Protected OS files are
    refused (ProtectedPath). A file held open by a running program is renamed and removed at the next restart.
    Returns {"path", "sha256", "removal"}.
    """
    path = Path(path)
    if is_protected(path):
        raise ProtectedPath(f"{path} is an operating-system file; it was reported but not deleted "
                            "(deleting it could stop Windows from starting). Use Microsoft Defender offline scan.")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Only regular files can be wiped")
    expected = str((result or {}).get("sha256") or "")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    if re.fullmatch(r"[0-9a-f]{64}", expected) and h.hexdigest() != expected:
        raise ValueError("File changed since scanning; rescan required")
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass
    try:
        size = path.stat().st_size
        with open(path, "r+b") as f:
            zero = b"\0" * _CHUNK
            left = size
            while left > 0:
                n = min(left, _CHUNK)
                f.write(zero[:n])
                left -= n
            f.flush()
            os.fsync(f.fileno())
            f.truncate(0)
        target = path.with_name(uuid.uuid4().hex)
        os.replace(path, target)
        path = target
    except OSError:
        pass                                   # locked: fall through to rename/delete-at-restart
    removal = _remove_original(path)
    return {"path": str(path), "sha256": h.hexdigest(), "removal": removal}


class Vault:
    def __init__(self, root: Path = None):
        self.root = root or (data_dir() / "quarantine")
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, qid):
        if not isinstance(qid, str) or not _QID.match(qid):
            raise ValueError("Invalid quarantine id")
        return self.root / f"{qid}.bin", self.root / f"{qid}.json"

    def put(self, path, result, allow_protected=False):
        path = Path(path)
        if not allow_protected and is_protected(path):
            raise ProtectedPath(f"{path} is an operating-system file; it was reported but not moved "
                                "(moving it could stop Windows from starting). Use Microsoft Defender offline scan.")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Only regular files can be quarantined")
        qid = uuid.uuid4().hex[:12]
        binp, metap = self._paths(qid)
        try:
            plain = _xor(path, binp)
            expected = str(result.get("sha256") or "")
            if re.fullmatch(r"[0-9a-f]{64}", expected) and plain != expected:
                raise ValueError("File changed since scanning; rescan required")
            if _unscrambled_sha256(binp) != plain:
                raise OSError("Vault copy failed verification; original left in place")
        except BaseException:
            binp.unlink(missing_ok=True)
            raise
        meta = {"id": qid, "original": str(path), "sha256": plain, "size": result.get("size"),
                "reasons": result.get("reasons", []), "verdict": result.get("verdict"), "t": time.time()}
        metap.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        try:
            meta["removal"] = _remove_original(path)
        except OSError:
            binp.unlink(missing_ok=True)
            metap.unlink(missing_ok=True)
            raise
        metap.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def list(self):
        out = []
        for p in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(m, dict) and _QID.match(str(m.get("id", ""))):
                out.append(m)
        return out

    def restore(self, qid, to=None):
        binp, metap = self._paths(qid)
        meta = json.loads(metap.read_text(encoding="utf-8"))
        dst = Path(to or meta["original"])
        n = 0
        base = dst
        while dst.exists():
            n += 1
            dst = base.with_name(f"{base.stem}.restored{'' if n == 1 else n}{base.suffix}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".aureon-restore")
        _xor(binp, tmp)
        h = hashlib.sha256()
        with open(tmp, "rb") as f:                             # streamed: no memory spike for large files
            for chunk in iter(lambda: f.read(_CHUNK), b""):
                h.update(chunk)
        got = h.hexdigest()
        if meta.get("sha256") and got != meta["sha256"]:
            tmp.unlink(missing_ok=True)
            raise OSError("Quarantined copy is damaged; restore refused and vault entry kept")
        os.replace(tmp, dst)
        self.delete(qid)
        return str(dst)

    def delete(self, qid):
        for p in self._paths(qid):
            p.unlink(missing_ok=True)

    def purge_older(self, days=30):
        cut = time.time() - days * 86400
        for m in self.list():
            if float(m.get("t") or 0) < cut:
                self.delete(m["id"])

    def export(self, qid, dst):
        shutil.copy(self._paths(qid)[0], dst)
