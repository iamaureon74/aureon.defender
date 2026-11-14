"""Device timeline: everything that has ever connected to this PC, and when.

Two sources, merged into one timeline:
  live      the engine checks what's plugged in every 3 seconds (a 5 ms call) and logs every connect / disconnect
            from the moment Aureon is installed: USB sticks and drives, phones, Bluetooth, headphones, displays,
            keyboards, mice, cameras, network adapters.
  history   Windows' own records from before Aureon: when each USB / Bluetooth / phone / display device was first
            installed, last connected and last removed (needs the SYSTEM engine), Bluetooth pairings, and every
            network joined (WiFi, wired, VPN, phone hotspot) with first and last connection.

Aureon's own log is local, can be switched off, and can be cleared (Settings). Windows' records are only read.
"""
import ctypes
import json
import os
import struct
import subprocess
import time
from pathlib import Path

from .core import atomic_write, data_dir

ENUM = r"SYSTEM\CurrentControlSet\Enum"
ROOTS = ["USB", "USBSTOR", "SCSI", "BTHENUM", "BTHLE", "BTHLEDevice", "BTHHFENUM", "SWD\\WPDBUSENUM", "SWD\\MMDEVAPI",
         "DISPLAY", "HID"]
CLASS_LABEL = {"USB": "USB", "DiskDrive": "Storage", "WPD": "Phone / media device", "Bluetooth": "Bluetooth",
               "Monitor": "Display", "AudioEndpoint": "Audio", "MEDIA": "Audio", "Camera": "Camera", "Image": "Camera",
               "Keyboard": "Keyboard", "Mouse": "Mouse", "HIDClass": "Input device", "Net": "Network adapter",
               "Ports": "Serial port", "Printer": "Printer", "SmartCardReader": "Smart card", "Biometric": "Biometric",
               "AndroidUsbDeviceClass": "Phone (Android)", "USBDevice": "USB", "SoftwareDevice": None, "System": None}
DEVPKEY = "{83da6326-97a6-4088-9453-a1923f573b29}"
PROP_FIRST, PROP_ARRIVAL, PROP_REMOVAL = "0064", "0065", "0066"
NETTYPE = {71: "WiFi", 6: "Wired", 23: "VPN", 243: "Mobile broadband", 53: "Virtual"}
TRACKER_TAGS = ("tile", "airtag", "smarttag", "galaxy smarttag", "chipolo", "pebblebee", "nut find", "cube tracker", "tracker tag")
NOISE_NAMES = ("generic attribute service", "generic access profile", "avrcp transport", "device information service",
               "bluetooth le generic", "bluetooth device (rfcomm protocol tdi)", "microsoft bluetooth le enumerator")
NOISE = ("ROOT_HUB", "\\VID_8087&PID_", "COMPOSITE", "HID\\CONVERTEDDEVICE", "HID\\HID_DEVICE_SYSTEM", "{0.0.1.00000000}")


# ---------------- live ----------------
def present_ids():
    """All present device instance ids (cfgmgr32, ~5 ms)."""
    if os.name != "nt":
        return set()
    from ctypes import wintypes
    cm = ctypes.windll.cfgmgr32
    size = wintypes.ULONG()
    if cm.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), None, 0x100):
        return set()
    buf = ctypes.create_unicode_buffer(size.value)
    if cm.CM_Get_Device_ID_ListW(None, buf, size, 0x100):
        return set()
    return {x for x in buf[:size.value].split("\x00") if x}


def tracked(dev_id):
    up = dev_id.upper()
    return any(up.startswith(r.upper() + "\\") for r in ROOTS) and not any(n.upper() in up for n in NOISE)


def _reg(path, value, root=None):
    import winreg
    try:
        with winreg.OpenKey(root or winreg.HKEY_LOCAL_MACHINE, path) as k:
            return winreg.QueryValueEx(k, value)[0]
    except OSError:
        return None


BUILTIN_CONTAINER = "{00000000-0000-0000-ffff-ffffffffffff}"


def is_builtin(dev_id):
    """Parts inside the laptop share Windows' 'this computer' container id; external devices get their own."""
    c = _reg(ENUM + "\\" + dev_id, "ContainerID")
    return isinstance(c, str) and c.lower() == BUILTIN_CONTAINER


def describe(dev_id):
    base = ENUM + "\\" + dev_id
    name = _reg(base, "FriendlyName") or _reg(base, "DeviceDesc") or dev_id
    name = str(name).split(";")[-1]
    cls = _reg(base, "Class") or ""
    label = CLASS_LABEL.get(cls, cls or "Device")
    if dev_id.upper().startswith(("USBSTOR", "SCSI")):
        label = "Storage"
    elif dev_id.upper().startswith("SWD\\WPDBUSENUM"):
        label = "Phone / media device"
    elif dev_id.upper().startswith(("BTHENUM", "BTHLE")):
        label = label if label not in ("Device", "System") else "Bluetooth"
    return {"id": dev_id, "name": name, "category": label}


class LiveDevices:
    def __init__(self, log=None, present=present_ids, describe_fn=describe):
        self.log = log or (data_dir() / "devices.jsonl")
        self.present = present
        self.describe = describe_fn
        self.known = None

    def tick(self, record=True):
        now = {d for d in self.present() if tracked(d)}
        if self.known is None:
            self.known = now
            return []
        events = []
        for d in sorted(now - self.known):
            info = self.describe(d)
            if info["category"] is None:
                continue
            events.append({"t": time.time(), "kind": "connected", **info, "source": "aureon"})
        for d in sorted(self.known - now):
            info = self.describe(d)
            if info["category"] is None:
                continue
            events.append({"t": time.time(), "kind": "disconnected", **info, "source": "aureon"})
        self.known = now
        if record and events:
            with open(self.log, "a", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
        return events


def live_log(path=None, days=None):
    p = path or (data_dir() / "devices.jsonl")
    if not Path(p).exists():
        return []
    cut = time.time() - days * 86400 if days is not None else 0
    out = []
    with open(p, encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("t", 0) >= cut:
                out.append(e)
    return out


def prune(path=None, days=365):
    p = Path(path or (data_dir() / "devices.jsonl"))
    if days < 0:
        raise ValueError("retention days must be nonnegative")
    keep = [] if days == 0 else live_log(p, days)
    atomic_write(p, "".join(json.dumps(e) + "\n" for e in keep))
    return len(keep)


# ---------------- Windows' own history ----------------
def _filetime_bytes(b):
    if not b or len(b) < 8:
        return None
    v = struct.unpack("<Q", bytes(b[:8]))[0]
    return v / 1e7 - 11644473600 if v else None


def _systemtime(b):
    if not b or len(b) < 16:
        return None
    y, mo, _dow, d, h, mi, s, _ms = struct.unpack("<8H", bytes(b[:16]))
    try:
        return time.mktime((y, mo, d, h, mi, s, 0, 0, -1))
    except (OverflowError, ValueError):
        return None


def _walk_enum():
    """Every instance ever recorded under the tracked Enum roots."""
    import winreg
    for root in ROOTS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ENUM + "\\" + root) as k:
                i = 0
                while True:
                    try:
                        hw = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(k, hw) as h:
                            j = 0
                            while True:
                                try:
                                    inst = winreg.EnumKey(h, j)
                                except OSError:
                                    break
                                j += 1
                                yield f"{root}\\{hw}\\{inst}"
                    except OSError:
                        continue
        except OSError:
            continue


def registry_history():
    """Devices with first-install / last-arrival / last-removal times. Times need SYSTEM; names don't."""
    out = []
    for dev_id in _walk_enum():
        if not tracked(dev_id):
            continue
        info = describe(dev_id)
        if info["category"] is None:
            continue
        props = ENUM + "\\" + dev_id + "\\Properties\\" + DEVPKEY
        times = {k: _filetime_bytes(_reg(props + "\\" + pid, "")) for k, pid in
                 (("first", PROP_FIRST), ("arrival", PROP_ARRIVAL), ("removal", PROP_REMOVAL))}
        out.append({**info, **times})
    return out


def pnp_history_powershell():
    """Fallback without SYSTEM rights: PnP properties via PowerShell (about 12 s)."""
    # one batched property query for all devices (per-device calls take minutes)
    ps = ("$d=@(Get-PnpDevice -Class USB,Bluetooth,WPD,DiskDrive,Monitor,AudioEndpoint,Camera,Image,Keyboard,Mouse -ErrorAction SilentlyContinue);"
          "$p=@($d | Get-PnpDeviceProperty -KeyName 'DEVPKEY_Device_FirstInstallDate','DEVPKEY_Device_LastArrivalDate','DEVPKEY_Device_LastRemovalDate' -ErrorAction SilentlyContinue);"
          "$t=@{}; foreach($x in $p){ if($x.Data){ $k=$x.InstanceId; if(-not $t[$k]){$t[$k]=@{}};"
          "$t[$k][$x.KeyName]=([DateTimeOffset]$x.Data).ToUnixTimeSeconds() } };"
          "$d | ForEach-Object { $r=$t[$_.InstanceId]; [pscustomobject]@{id=$_.InstanceId;name=$_.FriendlyName;cls=$_.Class;"
          "first=$(if($r){$r['DEVPKEY_Device_FirstInstallDate']});arrival=$(if($r){$r['DEVPKEY_Device_LastArrivalDate']});"
          "removal=$(if($r){$r['DEVPKEY_Device_LastRemovalDate']})} } | ConvertTo-Json -Compress")
    try:
        raw = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                             timeout=120, creationflags=0x08000000).stdout
        rows = json.loads(raw or "[]")
    except Exception:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    out = []
    for r in rows:
        if not r.get("id") or not tracked(r["id"]) and r.get("cls") not in ("Camera", "Image", "Keyboard", "Mouse"):
            continue
        out.append({"id": r["id"], "name": r.get("name") or r["id"], "category": CLASS_LABEL.get(r.get("cls"), r.get("cls") or "Device"),
                    "first": r.get("first"), "arrival": r.get("arrival"), "removal": r.get("removal")})
    return out


def bluetooth_history():
    import winreg
    out = []
    base = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0
            while True:
                try:
                    mac = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                name = _reg(base + "\\" + mac, "Name")
                if isinstance(name, bytes):
                    name = name.split(b"\x00")[0].decode("utf-8", errors="ignore")
                lc = _reg(base + "\\" + mac, "LastConnected")
                ls = _reg(base + "\\" + mac, "LastSeen")
                conv = lambda v: (v / 1e7 - 11644473600) if isinstance(v, int) and v else _filetime_bytes(v) if isinstance(v, bytes) else None
                out.append({"id": "BT\\" + ":".join(mac[j:j + 2] for j in range(0, 12, 2)), "name": name or mac, "category": "Bluetooth",
                            "arrival": conv(lc) or conv(ls), "first": None, "removal": None})
    except OSError:
        pass
    return out


def network_history():
    """Every network this PC joined, with first and last connection."""
    import winreg
    out = []
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0
            while True:
                try:
                    g = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                p = base + "\\" + g
                out.append({"id": "NET\\" + g, "name": _reg(p, "ProfileName") or g,
                            "category": NETTYPE.get(_reg(p, "NameType"), "Network") + " network",
                            "first": _systemtime(_reg(p, "DateCreated")), "arrival": _systemtime(_reg(p, "DateLastConnected")),
                            "removal": None})
    except OSError:
        pass
    return out


def history(fallback=True):
    rows = registry_history()
    if fallback and not any(r.get("arrival") or r.get("first") for r in rows):
        ps = pnp_history_powershell()
        if ps:
            rows = ps
    return rows + bluetooth_history() + network_history()


def is_tracker(name):
    low = (name or "").lower()
    return any(low == t or low.startswith(t + " ") or f" {t}" in low for t in TRACKER_TAGS)


def useful(name, category=""):
    """Hide the parts of a device (Bluetooth profile services, GATT services), keep the devices themselves."""
    low = (name or "").lower().strip()
    if any(n in low for n in NOISE_NAMES):
        return False
    if "bluetooth" in (category or "").lower() and (low.endswith(" service") or low.endswith(" services") or low.endswith(" transport")):
        return False
    return bool(low)


def timeline(records, live, limit=600):
    """Merge Windows' records and Aureon's live log into one newest-first list of moments."""
    ev = []
    records = [r for r in records if useful(r["name"], r.get("category"))]
    live = [e for e in live if useful(e.get("name"), e.get("category"))]
    for r in records:
        for key, kind in (("first", "first connected"), ("arrival", "last connected"), ("removal", "last removed")):
            t = r.get(key)
            if t:
                ev.append({"t": t, "kind": kind, "name": r["name"], "category": r["category"], "id": r["id"], "source": "windows",
                           "tracker": is_tracker(r["name"])})
    for e in live:
        ev.append({**e, "tracker": is_tracker(e.get("name"))})
    ev.sort(key=lambda e: e["t"], reverse=True)
    seen, out = set(), []
    for e in ev:                                   # one row per device per moment
        k = (e["name"].lower(), e["kind"], int(e["t"] // 60))
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out[:limit]


def sweep():
    """Snapshot written for the dashboard: device list + merged timeline."""
    rec = history()
    live = live_log()
    rec = [dict(r, tracker=is_tracker(r["name"])) for r in rec if useful(r["name"], r.get("category"))]
    snap = {"t": time.time(), "devices": rec, "timeline": timeline(rec, live), "trackers": [r for r in rec if r["tracker"]],
            "present": sorted(describe(d)["name"] for d in present_ids() if tracked(d))}
    atomic_write(data_dir() / "devices.json", json.dumps(snap, default=str))
    return snap
