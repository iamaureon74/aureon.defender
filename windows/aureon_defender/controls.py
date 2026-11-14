"""Controls: who may watch, and what may connect.

  telemetry   company data-collection services and scheduled tasks, closed off in one click (and reopened).
              Only collectors: nothing that drivers, updates, sound, touchpad, charging or keyboard lights need.
  usb         block USB storage (sticks, phones as drives); keyboards, mice, chargers keep working
  wifi        "only networks I approve": Windows refuses every other network, saved ones stay allowed
  bluetooth   a limit on connected devices and a list of allowed kinds; anything else raises an alert
  ports       what a plugged-in device can actually do: read your files, type commands, see your network
              traffic, listen, watch - from the interfaces it announced to Windows
Machine changes run in the elevated `aureon.defender controls ...` process; each records the old value.
"""
import json
import re
import subprocess

from .core import data_dir

NOWIN = 0x08000000

# Collectors only. (service or task, company, what it sends)
TELEMETRY = [
    ("svc:DiagTrack", "Microsoft", "Connected User Experiences and Telemetry: usage and diagnostic data"),
    ("svc:dmwappushservice", "Microsoft", "Routes device-management and telemetry messages"),
    ("svc:WerSvc", "Microsoft", "Error reports with memory contents"),
    ("svc:NvTelemetryContainer", "NVIDIA", "NVIDIA usage telemetry"),
    ("svc:ASUSSystemAnalysis", "ASUS", "System analysis data for ASUS"),
    ("svc:ASUSSystemDiagnosis", "ASUS", "Diagnosis data for ASUS"),
    ("svc:esrv_svc_QueenCreek", "Intel", "Intel energy telemetry"),
    ("svc:DellDataVault", "Dell", "Dell data vault (usage collection)"),
    ("svc:HPAppHelperCap", "HP", "HP analytics helper"),
    ("svc:HPDiagsCap", "HP", "HP diagnostics collection"),
    ("svc:HPSysInfoCap", "HP", "HP system info collection"),
    ("task:\\Microsoft\\Windows\\Application Experience\\Microsoft Compatibility Appraiser", "Microsoft", "Inventories your apps for Microsoft"),
    ("task:\\Microsoft\\Windows\\Application Experience\\ProgramDataUpdater", "Microsoft", "Program usage data"),
    ("task:\\Microsoft\\Windows\\Customer Experience Improvement Program\\Consolidator", "Microsoft", "CEIP usage upload"),
    ("task:\\Microsoft\\Windows\\Customer Experience Improvement Program\\UsbCeip", "Microsoft", "USB usage data"),
    ("task:\\Microsoft\\Windows\\Autochk\\Proxy", "Microsoft", "Sends disk-check data"),
    ("task:\\Microsoft\\Windows\\DiskDiagnostic\\Microsoft-Windows-DiskDiagnosticDataCollector", "Microsoft", "Disk diagnostic upload"),
    ("task:\\Microsoft\\Windows\\Feedback\\Siuf\\DmClient", "Microsoft", "Feedback data upload"),
    ("task:\\Microsoft\\Windows\\Feedback\\Siuf\\DmClientOnScenarioDownload", "Microsoft", "Feedback scenarios"),
    ("task:\\Microsoft\\Office\\OfficeTelemetryAgentLogOn2016", "Microsoft Office", "Office telemetry at sign-in"),
    ("task:\\Microsoft\\Office\\OfficeTelemetryAgentFallBack2016", "Microsoft Office", "Office telemetry fallback"),
    ("task:\\NvTmRep_CrashReport1_{B2FE1952-0186-46C3-BAEC-A80AA35AC5B8}", "NVIDIA", "NVIDIA crash/telemetry report"),
]


def _run(args, timeout=60):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
    return r.returncode, r.stdout + r.stderr


def telemetry_state():
    """[{id, company, what, present, active}] - present on this PC only."""
    out = []
    for tid, company, what in TELEMETRY:
        kind, name = tid.split(":", 1)
        if kind == "svc":
            rc, txt = _run(["sc", "qc", name])
            if rc != 0:
                continue
            start = re.search(r"START_TYPE\s*:\s*\d+\s+(\w+)", txt)
            active = bool(start) and start.group(1) != "DISABLED"
        else:
            rc, txt = _run(["schtasks", "/query", "/tn", name, "/fo", "csv", "/nh"])
            if rc != 0:
                continue
            active = "Disabled" not in txt
        out.append({"id": tid, "company": company, "what": what, "active": active})
    return out


def _backup(name, entries):
    p = data_dir() / f"{name}_backup.json"
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        b = {}
    for k, v in entries.items():
        b.setdefault(k, v)
    p.write_text(json.dumps(b, indent=1), encoding="utf-8")
    return b


def close_telemetry():
    """Elevated. Disables every present collector; remembers how each was set."""
    done, prev = [], {}
    for t in telemetry_state():
        if not t["active"]:
            continue
        kind, name = t["id"].split(":", 1)
        if kind == "svc":
            rc, txt = _run(["sc", "qc", name])
            m = re.search(r"START_TYPE\s*:\s*(\d+)", txt)
            prev[t["id"]] = {"2": "auto", "3": "demand", "4": "disabled"}.get(m.group(1) if m else "3", "demand")
            _run(["sc", "stop", name])
            rc, _ = _run(["sc", "config", name, "start=", "disabled"])
        else:
            prev[t["id"]] = "enabled"
            rc, _ = _run(["schtasks", "/change", "/tn", name, "/disable"])
        if rc == 0:
            done.append(t["id"])
    _backup("telemetry", prev)
    return done


def reopen_telemetry():
    p = data_dir() / "telemetry_backup.json"
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    for tid, how in b.items():
        kind, name = tid.split(":", 1)
        if kind == "svc":
            _run(["sc", "config", name, "start=", how])
        else:
            _run(["schtasks", "/change", "/tn", name, "/enable"])
    p.unlink(missing_ok=True)
    return len(b)


# ---------------- USB storage ----------------
USBSTOR = r"SYSTEM\CurrentControlSet\Services\USBSTOR"


def usb_storage_blocked():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USBSTOR) as k:
            return winreg.QueryValueEx(k, "Start")[0] == 4
    except OSError:
        return False


def set_usb_storage(block):
    """Elevated. 4 = driver never loads (blocked), 3 = loads on demand (normal)."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USBSTOR, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Start", 0, winreg.REG_DWORD, 4 if block else 3)
    return True


# ---------------- WiFi allow-list ----------------
def wifi_filters():
    rc, txt = _run(["netsh", "wlan", "show", "filters"])
    return {"denyall": "denyall" in txt.lower() and "infrastructure" in txt.lower(), "raw": txt}


def saved_networks():
    rc, txt = _run(["netsh", "wlan", "show", "profiles"])
    return re.findall(r"All User Profile\s*:\s*(.+)", txt)


def set_wifi_allowlist(on, allowed=None):
    """Elevated. On: allow saved (or given) networks, deny everything else. Off: remove Aureon's filters."""
    nets = allowed or [n.strip() for n in saved_networks()]
    if on:
        for n in nets:
            _run(["netsh", "wlan", "add", "filter", "permission=allow", f"ssid={n}", "networktype=infrastructure"])
        _run(["netsh", "wlan", "add", "filter", "permission=denyall", "networktype=infrastructure"])
    else:
        _run(["netsh", "wlan", "delete", "filter", "permission=denyall", "networktype=infrastructure"])
        for n in nets:
            _run(["netsh", "wlan", "delete", "filter", "permission=allow", f"ssid={n}", "networktype=infrastructure"])
    return {"on": on, "networks": nets}


# ---------------- Bluetooth limit ----------------
BT_KINDS = {"audio": "Headphones and speakers", "input": "Keyboards and mice", "phone": "Phones", "wearable": "Watches and bands",
            "other": "Other"}


def bt_kind(name):
    n = (name or "").lower()
    if any(w in n for w in ("buds", "headphone", "earbud", "airpods", "speaker", "soundcore", "jbl", "bose", "sony wh", "clip", "audio")):
        return "audio"
    if any(w in n for w in ("keyboard", "mouse", "trackpad", "pen", "controller", "gamepad")):
        return "input"
    if any(w in n for w in ("pixel", "iphone", "galaxy", "phone", "android", "oneplus", "xiaomi", "moto")):
        return "phone"
    if any(w in n for w in ("watch", "band", "fit", "ring", "hume")):
        return "wearable"
    return "other"


def bt_check(connected, limit=4, allowed=("audio", "input", "phone", "wearable")):
    """connected: device names -> alerts for too many or a disallowed kind."""
    alerts = []
    if len(connected) > limit:
        alerts.append(f"{len(connected)} Bluetooth devices connected (your limit is {limit})")
    for n in connected:
        k = bt_kind(n)
        if k not in allowed:
            alerts.append(f"{n}: {BT_KINDS[k].lower()} aren't on your allowed list")
    return alerts


# ---------------- what a plugged-in device can do ----------------
CAPS = [  # (class or id pattern, capability, plain risk)
    (r"^(DiskDrive|USBSTOR|WPD)$|^USBSTOR\\", "storage", "Can read and write files you put on it, and carry files onto this PC."),
    (r"^Keyboard$|^HIDClass$", "keyboard", "Can type. A fake keyboard can enter commands faster than you can see."),
    (r"^Mouse$", "pointer", "Can move the pointer and click."),
    (r"^Net$", "network", "Is a network adapter: it can see and redirect this PC's internet traffic."),
    (r"^(Camera|Image)$", "camera", "Has a camera."),
    (r"^(MEDIA|AudioEndpoint)$", "audio", "Has a microphone or speakers."),
    (r"^Ports$", "serial", "Opens a serial port that software on this PC can talk to."),
    (r"^SmartCardReader$", "smartcard", "Reads smart cards."),
    (r"^Biometric$", "biometric", "Reads fingerprints or faces."),
    (r"^AndroidUsbDeviceClass$", "debug", "Android debugging link: full access to that phone from this PC."),
]


def device_capabilities(container_devices):
    """[(class, name)] for all interfaces sharing one physical device -> what it can collect or send."""
    found = {}
    for cls, name in container_devices:
        for pat, cap, risk in CAPS:
            if re.search(pat, cls or "", re.I):
                found[cap] = risk
    level = "high" if {"keyboard", "network"} & set(found) and len(found) > 1 else "medium" if {"keyboard", "network", "debug"} & set(found) else "low"
    if not found:
        found["power"] = "Draws power only, or shows no data interface to Windows."
    return {"capabilities": found, "level": level}


def plugged_devices():
    """Physical devices grouped by ContainerID with what each one can do."""
    import winreg
    from .devices import ENUM, present_ids
    groups = {}
    for dev_id in present_ids():
        if not dev_id.upper().startswith(("USB\\", "USBSTOR\\", "HID\\", "SWD\\WPDBUSENUM", "BTHENUM\\", "BTHLE\\")):
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ENUM + "\\" + dev_id) as k:
                def v(n):
                    try:
                        return winreg.QueryValueEx(k, n)[0]
                    except OSError:
                        return None
                cont, cls = v("ContainerID"), v("Class")
                name = str(v("FriendlyName") or v("DeviceDesc") or dev_id).split(";")[-1]
        except OSError:
            continue
        if not cont or cont.lower() == "{00000000-0000-0000-ffff-ffffffffffff}":     # built-in parts share this id
            continue
        g = groups.setdefault(cont, {"names": [], "parts": []})
        g["parts"].append((cls, name))
        if cls in ("USB", "DiskDrive", "WPD", "Bluetooth", "Keyboard", "Mouse", "Camera", "Net", "MEDIA") and name not in g["names"]:
            g["names"].append(name)
    out = []
    for cont, g in groups.items():
        caps = device_capabilities(g["parts"])
        out.append({"name": (g["names"] or [g["parts"][0][1]])[0], "parts": len(g["parts"]), **caps})
    return sorted(out, key=lambda d: {"high": 0, "medium": 1, "low": 2}[d["level"]])
