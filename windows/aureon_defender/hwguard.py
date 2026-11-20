"""Hardware intelligence: adapt to whatever machine this runs on, and never delete what the hardware needs.

Three plain, deterministic algorithms (no AI, no learned model, no network):

1. profile()  measures the machine (logical CPUs, RAM, battery, disk kind, architecture, OS) and turns it into a
   budget with fixed arithmetic. A 2-core 4 GB tablet and a 32-thread workstation both get protection; they just
   get a different cadence and sweep size:

       capacity = min(cpus / 8, 1.5) * 0.5 + min(ram_gb / 16, 1.5) * 0.5        (0.06 .. 1.5)
       tier     = "lite" if capacity < 0.45, "standard" if < 0.95, else "performance"
       interval_scale = {lite: 1.6, standard: 1.0, performance: 0.75} (x1.25 when on battery-only hardware
                        with a spinning disk, because seeks are what cost the most there)
       sweep_files    = round(4000 * capacity) clamped to 1500 .. 12000
       hash_limit_mb  = 256 on lite, 512 otherwise

   Unknown values never invent hardware: a missing reading falls back to the most conservative assumption.

2. needed_by_hardware(path) answers "would removing this file stop a device, the boot chain or a driver from
   working?". It uses facts the OS already publishes, never guesses:
     * boot / firmware / driver locations for Windows, Linux and macOS (System32\\drivers, DriverStore,
       /lib/modules, /lib/firmware, /boot, /Library/Extensions, /System, ...)
     * kernel and file-system driver images the OS has registered as services (Windows registry Services key,
       service Type 1/2/8), wherever on disk they live (vendor folders under Program Files included)
     * driver/firmware file types (.sys .inf .cat .efi .ko .kext .dext .fw ...) when they sit in those locations
   A driver file that nothing registered and no device uses (for example a .sys dropped in Downloads) is NOT
   "needed": a dropped vulnerable driver is a classic attack (BYOVD), so it stays removable.

3. decide(result, path) is the autopilot. Given a scanner verdict it returns one action with a reason:
       malicious + not needed            -> "wipe"        (overwrite + delete, no undo)
       suspicious + not needed + unsigned -> "quarantine"  (encrypted vault copy; the vault is emptied on its own
                                                            after trash_days, so it ends up deleted too)
       anything the hardware needs        -> "keep"        (reported, never touched)
       validly signed + only suspicious   -> "keep"        (a publisher signature outweighs heuristics alone)
"""
import os
import platform
import sys
import time
from pathlib import Path

WIN = os.name == "nt"

# File types that belong to drivers and firmware. Only "needed" when they sit somewhere the OS loads them from
# or are registered with the OS; on their own they are just bytes.
DRIVER_EXT = {".sys", ".inf", ".cat", ".efi", ".mui", ".ko", ".ko.xz", ".ko.zst", ".kext", ".dext", ".fw",
              ".bin", ".ucode", ".dtb", ".rom", ".cap"}


def _env(name, default):
    return os.environ.get(name) or default


def hardware_roots():
    """Folders that hold the boot chain, firmware and device drivers on this OS (normalised, lower-case)."""
    if WIN or os.environ.get("AUREON_HW_WINDOWS"):
        sysroot = _env("SYSTEMROOT", r"C:\Windows")
        drive = _env("SYSTEMDRIVE", "C:")
        pf = _env("PROGRAMFILES", r"C:\Program Files")
        roots = [sysroot + r"\System32\drivers", sysroot + r"\System32\DriverStore", sysroot + r"\SysWOW64\drivers",
                 sysroot + r"\INF", sysroot + r"\Boot", sysroot + r"\System32\Boot", sysroot + r"\System32\CodeIntegrity",
                 drive + r"\EFI", drive + r"\Boot", drive + r"\Recovery",
                 pf + r"\Common Files\microsoft shared\ink", sysroot + r"\System32\spool\drivers"]
        return [_norm(r) for r in roots]
    if sys.platform == "darwin":
        roots = ["/System", "/Library/Extensions", "/Library/DriverExtensions", "/Library/SystemExtensions",
                 "/Library/Apple", "/usr/lib", "/usr/libexec", "/sbin", "/bin", "/private/var/db/KernelExtensionManagement"]
    else:
        roots = ["/boot", "/lib/modules", "/lib/firmware", "/usr/lib/modules", "/usr/lib/firmware", "/efi",
                 "/sys", "/proc", "/dev", "/run/udev", "/etc/udev", "/usr/lib/udev", "/lib/udev", "/usr/lib/systemd",
                 "/lib/systemd", "/usr/sbin", "/sbin", "/usr/bin", "/bin", "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu"]
    return [_norm(r) for r in roots]


def _norm(p):
    s = os.path.normcase(os.path.abspath(str(p)))
    if WIN or "\\" in s:
        s = s.replace("/", "\\").rstrip("\\") + "\\"
        return s.lower()
    return s.rstrip("/") + "/"


def _under(path_norm, roots):
    return any(path_norm.startswith(r) for r in roots)


# ---------------- registered drivers (Windows) ----------------
_drivers_cache = (0.0, frozenset())


def _expand_image_path(raw):
    """Turn a service ImagePath (\\SystemRoot\\..., system32\\..., \\??\\C:\\..., quoted with args) into a path."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith('"'):
        s = s[1:].split('"', 1)[0]
    elif ".sys " in s.lower() or ".exe " in s.lower():
        low = s.lower()
        cut = min(i for i in (low.find(".sys "), low.find(".exe ")) if i >= 0)
        s = s[:cut + 4]
    sysroot = _env("SYSTEMROOT", r"C:\Windows")
    if s.startswith("\\??\\"):
        s = s[4:]
    low = s.lower()
    if low.startswith("\\systemroot\\"):
        s = sysroot + s[len("\\SystemRoot"):]
    elif low.startswith("system32\\") or low.startswith("syswow64\\"):
        s = sysroot + "\\" + s
    elif low.startswith("%systemroot%"):
        s = sysroot + s[len("%SystemRoot%"):]
    return os.path.expandvars(s)


def registered_drivers(reader=None, ttl=600):
    """Paths of kernel / file-system drivers the OS has registered (Windows). Cached for `ttl` seconds."""
    global _drivers_cache
    now = time.time()
    if reader is None and now - _drivers_cache[0] < ttl:
        return _drivers_cache[1]
    rows = reader() if reader else _read_driver_services()
    paths = frozenset(_norm(_expand_image_path(p)).rstrip("\\/") for p in rows if p)
    if reader is None:
        _drivers_cache = (now, paths)
    return paths


def _read_driver_services():
    if not WIN:
        return []
    try:
        import winreg
    except ImportError:
        return []
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services") as root:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, name) as k:
                        typ = winreg.QueryValueEx(k, "Type")[0]
                        if typ in (1, 2, 8):                    # kernel, file-system and recognizer drivers
                            out.append(str(winreg.QueryValueEx(k, "ImagePath")[0]))
                except OSError:
                    continue
    except OSError:
        pass
    return out


def needed_by_hardware(path, drivers=None):
    """Reason string when removing `path` could break a device, a driver or booting; None when it is removable."""
    p = Path(str(path))
    n = _norm(p)
    reg = drivers if drivers is not None else registered_drivers()
    if n.rstrip("\\/") in reg:
        return "a driver the operating system has registered for a device"
    name = p.name.lower()
    if name in {"bootmgr", "bootmgr.efi", "bootx64.efi", "bootaa64.efi", "grubx64.efi", "shimx64.efi", "vmlinuz",
                "initrd.img", "pagefile.sys", "hiberfil.sys", "swapfile.sys", "ntldr", "bootnxt", "winload.efi"}:
        return "part of the boot chain"
    if _under(n, hardware_roots()):
        ext = "".join(p.suffixes[-2:]).lower() if name.endswith((".xz", ".zst")) else p.suffix.lower()
        if ext in DRIVER_EXT or not ext:
            return "a driver or firmware file in a location the operating system loads from"
        return "inside a system hardware folder"
    return None


# ---------------- machine profile and budget ----------------
def _probe():
    info = {"cpus": os.cpu_count() or 1, "arch": platform.machine() or "unknown", "os": platform.system() or "unknown",
            "ram_gb": None, "battery": None, "disk": "unknown"}
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
        try:
            b = psutil.sensors_battery()
            info["battery"] = None if b is None else {"percent": b.percent, "plugged": bool(b.power_plugged)}
        except Exception:
            pass
    except Exception:
        pass
    info["disk"] = _disk_kind()
    return info


def _disk_kind():
    """'ssd', 'hdd' or 'unknown' for the system disk, from what the OS reports."""
    try:
        if WIN:
            import subprocess
            from .governor import child_flags
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "(Get-PhysicalDisk | Select -First 1).MediaType"], capture_output=True, text=True,
                                 timeout=20, creationflags=child_flags()).stdout.strip().lower()
            return "ssd" if "ssd" in out else "hdd" if "hdd" in out else "unknown"
        if sys.platform.startswith("linux"):
            vals = []
            for f in Path("/sys/block").glob("*/queue/rotational"):
                if f.parts[3].startswith(("loop", "ram", "zram", "dm-")):
                    continue
                vals.append(f.read_text().strip())
            return "hdd" if vals and all(v == "1" for v in vals) else "ssd" if vals else "unknown"
        if sys.platform == "darwin":
            return "ssd"                                    # every Mac sold since 2020 boots from flash
    except Exception:
        pass
    return "unknown"


def budget(info):
    """Fixed arithmetic from a profile to a work budget. Pure function: same input, same output."""
    cpus = max(1, int(info.get("cpus") or 1))
    ram = info.get("ram_gb")
    ram = 4.0 if ram is None else float(ram)                    # unknown RAM: assume a small machine
    capacity = round(min(cpus / 8, 1.5) * 0.5 + min(ram / 16, 1.5) * 0.5, 3)
    tier = "lite" if capacity < 0.45 else "standard" if capacity < 0.95 else "performance"
    scale = {"lite": 1.6, "standard": 1.0, "performance": 0.75}[tier]
    on_battery_hw = info.get("battery") is not None
    if on_battery_hw and info.get("disk") == "hdd":
        scale *= 1.25
    return {"tier": tier, "capacity": capacity, "interval_scale": round(scale, 3),
            "sweep_files": int(min(12000, max(1500, round(4000 * capacity)))),
            "hash_limit_mb": 256 if tier == "lite" else 512,
            "scan_workers": 1 if tier == "lite" else 2 if tier == "standard" else min(4, cpus // 4 or 1)}


_profile_cache = None


def profile(refresh=False, probe=None):
    global _profile_cache
    if _profile_cache is None or refresh or probe:
        info = (probe or _probe)()
        _profile_cache = {**info, **budget(info), "t": time.time()}
    return _profile_cache


# ---------------- autopilot decision ----------------
def decide(result, path, signature=None, drivers=None):
    """One action for a scan result: wipe | quarantine | keep | none, plus a plain reason."""
    verdict = (result or {}).get("verdict")
    if verdict not in ("malicious", "suspicious"):
        return {"action": "none", "why": ""}
    need = needed_by_hardware(path, drivers)
    if need:
        return {"action": "keep", "why": f"left in place: {need}"}
    if verdict == "malicious":
        eng = result.get("engines", {})
        confirmed = eng.get("reputation") == "bad" or eng.get("defender") == "threat" or eng.get("clamav") == "threat"
        return {"action": "wipe" if confirmed else "quarantine",
                "why": "confirmed malware" if confirmed else "high-confidence detection"}
    sig = signature(path) if callable(signature) else signature
    if sig == "Valid":
        return {"action": "keep", "why": "validly signed by its publisher; heuristics alone are not enough to remove it"}
    return {"action": "quarantine", "why": "suspicious and unsigned"}
