"""Hidden-software radar: what every company has running, installed or watching on this PC, and a log of changes.

Sources (all local, read-only):
  privacy log    Windows' own CapabilityAccessManager records: which app used camera, microphone, location,
                 screen capture, contacts, notifications, radios... and when (and whether it's using them right now)
  Recall         whether Windows Recall is allowed and whether it has stored screen snapshots
  watchers       known employee-monitoring / stalkerware / screen-recording products (processes, services, installs)
  installed      every program in the uninstall registry, including entries hidden from Settings > Apps
  background     services, scheduled tasks and autostarts, each attributed to the company that built the file
  telemetry      known vendor telemetry services and tasks (Microsoft, NVIDIA, Intel, ASUS, Dell, HP, Lenovo...)
  extensions     Chrome / Edge / Brave / Opera / Vivaldi extensions with broad powers
Everything is grouped by company, and differences since the last sweep go to the event journal.
"""
import ctypes
import json
import os
import re
import struct
import time
from pathlib import Path

from .core import atomic_write, data_dir, expand_all, is_system

CAM = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
WATCH_CAPS = {
    "webcam": "camera", "microphone": "microphone", "location": "location",
    "graphicsCaptureProgrammatic": "screen capture", "graphicsCaptureWithoutBorder": "screen capture (no yellow border)",
    "userNotificationListener": "your notifications", "contacts": "contacts", "phoneCallHistory": "call history",
    "chat": "messages", "email": "email", "radios": "radio control (WiFi/Bluetooth on/off)", "bluetoothSync": "Bluetooth sync",
    "userAccountInformation": "your account info", "broadFileSystemAccess": "all your files", "humanPresence": "presence sensor",
}
SENSITIVE = {"webcam", "microphone", "graphicsCaptureProgrammatic", "graphicsCaptureWithoutBorder", "location",
             "userNotificationListener"}

# Known monitoring / stalkerware / covert screen-recording products (matched on process, service, program names).
WATCHERS = {
    "activtrak": "ActivTrak", "teramind": "Teramind", "hubstaff": "Hubstaff", "timedoctor": "Time Doctor", "time doctor": "Time Doctor",
    "veriato": "Veriato", "spector": "Spector (Veriato)", "interguard": "InterGuard", "kickidler": "Kickidler",
    "controlio": "Controlio", "currentware": "CurrentWare", "workexaminer": "Work Examiner", "work examiner": "Work Examiner",
    "insightful": "Insightful", "workpuls": "Workpuls/Insightful", "desktime": "DeskTime", "staffcop": "StaffCop",
    "refog": "Refog", "spyrix": "Spyrix", "flexispy": "FlexiSPY", "mspy": "mSpy", "spyagent": "SpyAgent",
    "kidlogger": "KidLogger", "netnanny": "Net Nanny", "qustodio": "Qustodio", "ekran": "Ekran System", "syteca": "Syteca",
    "sentrypc": "SentryPC", "clevercontrol": "CleverControl", "monitask": "Monitask", "screenshotmonitor": "ScreenshotMonitor",
    "imonitor": "iMonitor", "actual keylogger": "Actual Keylogger", "revealer": "Revealer Keylogger", "elite keylogger": "Elite Keylogger",
    "best free keylogger": "Best Free Keylogger", "ardamax": "Ardamax Keylogger", "pctattletale": "PCTattletale",
    "webwatcher": "WebWatcher", "netvizura": "NetVizura", "soti": "SOTI MobiControl", "absolute": "Absolute (persistence agent)",
}

TELEMETRY_SERVICES = {
    "diagtrack": ("Microsoft", "Connected User Experiences and Telemetry"),
    "dmwappushservice": ("Microsoft", "Device management WAP push (telemetry routing)"),
    "wersvc": ("Microsoft", "Windows Error Reporting"),
    "nvtelemetrycontainer": ("NVIDIA", "NVIDIA telemetry container"),
    "nvdisplay.containerlocalsystem": ("NVIDIA", "NVIDIA display container"),
    "intel(r) computing improvement program": ("Intel", "Intel Computing Improvement Program"),
    "esrv_svc_queencreek": ("Intel", "Intel Energy Server (telemetry)"),
    "asusoptimization": ("ASUS", "ASUS Optimization"), "asussystemanalysis": ("ASUS", "ASUS System Analysis"),
    "asussystemdiagnosis": ("ASUS", "ASUS System Diagnosis"), "asuslinknear": ("ASUS", "ASUS Link Near"),
    "asuslinkremote": ("ASUS", "ASUS Link Remote"), "armourycrateservice": ("ASUS", "Armoury Crate"),
    "supportassistagent": ("Dell", "Dell SupportAssist"), "dell data vault wrapper": ("Dell", "Dell Data Vault"),
    "hpappshelpercap": ("HP", "HP App Helper"), "hpdiagscap": ("HP", "HP Diagnostics"), "hpsysinfocap": ("HP", "HP System Info"),
    "hp insights": ("HP", "HP Insights"), "lenovovantageservice": ("Lenovo", "Lenovo Vantage"),
    "imcontrollerservice": ("Lenovo", "Lenovo System Interface Foundation"), "lenovo.modern.imcontroller": ("Lenovo", "Lenovo IMController"),
    "adobearmservice": ("Adobe", "Adobe updater"), "agsservice": ("Adobe", "Adobe Genuine Software check"),
    "razer synapse service": ("Razer", "Razer Synapse"), "logi_lamparray_service": ("Logitech", "Logitech"),
    "mcafee webadvisor": ("McAfee", "WebAdvisor"), "mfewc": ("McAfee", "McAfee"),
}
TELEMETRY_TASK = re.compile(r"telemetry|ceip|consolidator|usbceip|compatibility appraiser|programdataupdater|"
                            r"proxy$|kernelceiptask|qmsvc|diagtrack|feedback|siuf|dmclient|appraiser|devicecensus|"
                            r"bthsqm|familysafety|edgeupdate|googleupdate|adobe.*(ngl|gc)|nvtmrep|nvprofileupdater|asus.*(update|telemetry)", re.I)

BROAD_EXT = {"<all_urls>", "*://*/*", "http://*/*", "https://*/*", "webRequest", "webRequestBlocking", "debugger",
             "nativeMessaging", "clipboardRead", "history", "cookies", "desktopCapture", "tabCapture", "management",
             "proxy", "privacy", "declarativeNetRequestWithHostAccess", "scripting"}


# ---------------- helpers ----------------
def filetime(v):
    if not v:
        return None
    return v / 1e7 - 11644473600


def company_of(path):
    """CompanyName from the file's version resource (no pywin32 needed)."""
    path = (path or "").strip().strip('"')
    m = re.match(r'^"?([a-zA-Z]:\\[^"]+?\.(exe|dll|sys))', path, re.I)
    if not m:
        return None
    path = os.path.expandvars(m.group(1))
    if os.name != "nt" or not os.path.exists(path):
        return None
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, buf):
        return None
    ptr, ln = ctypes.c_void_p(), ctypes.c_uint()
    langs = []
    if ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(ln)) and ln.value:
        raw = ctypes.string_at(ptr.value, ln.value)
        langs = ["%04x%04x" % struct.unpack("<HH", raw[i:i + 4]) for i in range(0, len(raw), 4)]
    for lang in langs + ["040904b0", "040904e4", "000004b0"]:
        if ver.VerQueryValueW(buf, f"\\StringFileInfo\\{lang}\\CompanyName", ctypes.byref(ptr), ctypes.byref(ln)) and ln.value:
            name = ctypes.wstring_at(ptr.value, ln.value).strip("\x00 ").strip()
            if name:
                return normalize_company(name)
    return None


COMPANY_ALIASES = [
    (r"microsoft", "Microsoft"), (r"nvidia", "NVIDIA"), (r"intel", "Intel"), (r"advanced micro|amd\b", "AMD"),
    (r"asus|asustek", "ASUS"), (r"dell", "Dell"), (r"hewlett|^hp\b|hp inc", "HP"), (r"lenovo", "Lenovo"), (r"acer", "Acer"),
    (r"google", "Google"), (r"adobe", "Adobe"), (r"realtek", "Realtek"), (r"qualcomm", "Qualcomm"), (r"mcafee", "McAfee"),
    (r"norton|gen digital|nortonlifelock|avast|avg", "Gen Digital (Norton/Avast/AVG)"), (r"razer", "Razer"), (r"logitech", "Logitech"),
    (r"apple", "Apple"), (r"mozilla", "Mozilla"), (r"opera", "Opera"), (r"brave", "Brave"), (r"discord", "Discord"),
    (r"valve", "Valve (Steam)"), (r"epic games", "Epic Games"), (r"meta|facebook", "Meta"), (r"amazon", "Amazon"),
    (r"zoom", "Zoom"), (r"dropbox", "Dropbox"), (r"tailscale", "Tailscale"), (r"proton", "Proton"), (r"oracle", "Oracle"),
    (r"waves audio", "Waves Audio"), (r"dolby", "Dolby"), (r"synaptics", "Synaptics"), (r"elan", "ELAN"), (r"mediatek", "MediaTek"),
]


def normalize_company(name):
    if not name:
        return "Unknown publisher"
    low = name.lower()
    for pat, canon in COMPANY_ALIASES:
        if re.search(pat, low):
            return canon
    return re.sub(r"[,.]?\s*(inc|llc|ltd|corp|corporation|co|gmbh|limited|s\.a\.)\.?$", "", name.strip(), flags=re.I).strip()


def _hives():
    import winreg
    if not is_system():
        return [("you", winreg.HKEY_CURRENT_USER, "")]
    from .monitors import _user_hives
    return [(label, root, prefix) for label, root, prefix in _user_hives()]


# ---------------- sources ----------------
def privacy_log():
    """[{capability, what, app, last_start, last_stop, in_use, user}] from Windows' own access records."""
    import winreg
    out = []

    def read_app(root, keypath, cap, app, user):
        try:
            with winreg.OpenKey(root, keypath) as k:
                start = stop = None
                try:
                    start = winreg.QueryValueEx(k, "LastUsedTimeStart")[0]
                    stop = winreg.QueryValueEx(k, "LastUsedTimeStop")[0]
                except OSError:
                    pass
                if start:
                    out.append({"capability": cap, "what": WATCH_CAPS[cap], "app": app, "last_start": filetime(start),
                                "last_stop": filetime(stop) if stop else None, "in_use": bool(start and not stop), "user": user})
        except OSError:
            pass

    for user, root, prefix in _hives():
        for cap in WATCH_CAPS:
            base = prefix + CAM + "\\" + cap
            for sub in ("", "\\NonPackaged"):
                try:
                    with winreg.OpenKey(root, base + sub) as k:
                        i = 0
                        while True:
                            try:
                                name = winreg.EnumKey(k, i)
                            except OSError:
                                break
                            i += 1
                            if name == "NonPackaged":
                                continue
                            app = name.replace("#", "\\") if sub else name.split("_")[0]
                            read_app(root, base + sub + "\\" + name, cap, app, user)
                except OSError:
                    continue
    out.sort(key=lambda r: r["last_start"] or 0, reverse=True)
    return out


def recall_status():
    import winreg
    policy = None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, r"Software\Policies\Microsoft\Windows\WindowsAI") as k:
                policy = winreg.QueryValueEx(k, "DisableAIDataAnalysis")[0]
                break
        except OSError:
            continue
    stores = [p for p in expand_all("%LOCALAPPDATA%/CoreAIPlatform.00/UKP") if p.exists()]
    snapshots = 0
    for s in stores:
        try:
            snapshots += sum(1 for _ in s.rglob("*") if _.is_file())
        except OSError:
            pass
    return {"blocked_by_policy": policy == 1, "snapshot_store": [str(s) for s in stores], "files": snapshots,
            "verdict": "blocked" if policy == 1 else "has snapshots" if snapshots else "not active"}


def installed_programs():
    import winreg
    roots = [("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
             ("HKLM32", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")]
    roots += [(label, root, prefix + r"Software\Microsoft\Windows\CurrentVersion\Uninstall") for label, root, prefix in _hives()]
    progs = {}
    for label, root, path in roots:
        try:
            with winreg.OpenKey(root, path) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(k, sub) as s:
                            def v(n, d=None):
                                try:
                                    return winreg.QueryValueEx(s, n)[0]
                                except OSError:
                                    return d
                            name = v("DisplayName")
                            if not name:
                                continue
                            hidden = v("SystemComponent", 0) == 1 or bool(v("ParentKeyName")) or v("NoRemove", 0) == 1
                            key = name.lower()
                            if key in progs and not progs[key]["hidden"]:
                                continue
                            progs[key] = {"name": name, "company": normalize_company(v("Publisher", "")), "version": v("DisplayVersion", ""),
                                          "installed": v("InstallDate", ""), "hidden": hidden, "where": label,
                                          "location": v("InstallLocation", "") or ""}
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(progs.values(), key=lambda p: (p["company"].lower(), p["name"].lower()))


def background_software(services=None, tasks=None, autoruns=None):
    from .monitors import read_run_keys, read_services, read_startup_folders, read_tasks
    services = read_services() if services is None else services
    tasks = read_tasks() if tasks is None else tasks
    autoruns = {**read_run_keys(), **read_startup_folders()} if autoruns is None else autoruns
    out = []
    cache = {}

    def comp(p):
        if p not in cache:
            cache[p] = company_of(p) or "Unknown publisher"
        return cache[p]
    for k, path in services.items():
        name = k.split(":", 1)[1]
        tele = TELEMETRY_SERVICES.get(name.lower())
        out.append({"kind": "service", "name": name, "target": path, "company": tele[0] if tele else comp(path),
                    "telemetry": bool(tele), "note": tele[1] if tele else ""})
    for k, path in tasks.items():
        name = k.split(":", 1)[1]
        out.append({"kind": "scheduled task", "name": name, "target": path, "company": comp(path),
                    "telemetry": bool(TELEMETRY_TASK.search(name)), "note": ""})
    for k, path in autoruns.items():
        out.append({"kind": "autostart", "name": k.rsplit("\\", 1)[-1].replace("startup:", ""), "target": path,
                    "company": comp(path), "telemetry": bool(TELEMETRY_TASK.search(k)), "note": ""})
    return out


def browser_extensions():
    roots = {"Chrome": "%LOCALAPPDATA%/Google/Chrome/User Data", "Edge": "%LOCALAPPDATA%/Microsoft/Edge/User Data",
             "Brave": "%LOCALAPPDATA%/BraveSoftware/Brave-Browser/User Data", "Vivaldi": "%LOCALAPPDATA%/Vivaldi/User Data",
             "Opera": "%APPDATA%/Opera Software/Opera Stable", "Opera GX": "%APPDATA%/Opera Software/Opera GX Stable"}
    out = []
    for browser, r in roots.items():
        for base in expand_all(r):
            if not base.exists():
                continue
            ext_dirs = [base / "Extensions"] + [p / "Extensions" for p in base.glob("Profile *")] + [base / "Default" / "Extensions"]
            for ed in ext_dirs:
                if not ed.exists():
                    continue
                for ext in ed.iterdir():
                    vers = sorted([v for v in ext.iterdir() if v.is_dir()], reverse=True) if ext.is_dir() else []
                    if not vers:
                        continue
                    try:
                        man = json.loads((vers[0] / "manifest.json").read_text(encoding="utf-8-sig"))
                    except (OSError, ValueError):
                        continue
                    name = man.get("name", ext.name)
                    if name.startswith("__MSG_"):
                        name = _msg(vers[0], name[6:-2], man.get("default_locale", "en")) or ext.name
                    perms = set(map(str, man.get("permissions", []) + man.get("host_permissions", []) + man.get("optional_permissions", [])))
                    broad = sorted(perms & BROAD_EXT)
                    out.append({"browser": browser, "id": ext.name, "name": name, "version": man.get("version", ""),
                                "broad": broad, "profile": ed.parent.name})
    uniq = {(e["browser"], e["id"]): e for e in out}
    return sorted(uniq.values(), key=lambda e: (-len(e["broad"]), e["name"].lower()))


def _msg(vdir, key, loc):
    for l in (loc, "en", "en_US"):
        try:
            m = json.loads((vdir / "_locales" / l / "messages.json").read_text(encoding="utf-8-sig"))
            for k, v in m.items():
                if k.lower() == key.lower():
                    return v.get("message")
        except (OSError, ValueError):
            continue
    return None


def watchers(programs, background):
    import psutil
    hits = []
    names = [(p["name"], "installed program") for p in programs] + [(b["name"] + " " + (b["target"] or ""), b["kind"]) for b in background]
    try:
        names += [(p.info["name"] or "", "running process") for p in psutil.process_iter(["name"])]
    except Exception:
        pass
    for text, where in names:
        low = text.lower()
        for needle, product in WATCHERS.items():
            if needle in low and not (needle == "absolute" and "absolute" not in low.split()[0:1] and "rpcnet" not in low):
                hits.append({"product": product, "where": where, "evidence": text[:160]})
    seen, out = set(), []
    for h in hits:
        k = (h["product"], h["where"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


# ---------------- sweep + diff ----------------
def sweep(sources=None):
    s = sources or {}
    programs = s.get("installed") if "installed" in s else installed_programs()
    background = s.get("background") if "background" in s else background_software()
    report = {
        "t": time.time(),
        "privacy": s.get("privacy") if "privacy" in s else privacy_log(),
        "recall": s.get("recall") if "recall" in s else recall_status(),
        "installed": programs,
        "background": background,
        "extensions": s.get("extensions") if "extensions" in s else browser_extensions(),
    }
    report["watchers"] = s.get("watchers") if "watchers" in s else watchers(programs, background)
    companies = {}
    for p in programs:
        c = companies.setdefault(p["company"], {"programs": 0, "hidden": 0, "background": 0, "telemetry": 0})
        c["programs"] += 1
        c["hidden"] += p["hidden"]
    for b in background:
        c = companies.setdefault(b["company"], {"programs": 0, "hidden": 0, "background": 0, "telemetry": 0})
        c["background"] += 1
        c["telemetry"] += b["telemetry"]
    report["companies"] = dict(sorted(companies.items(), key=lambda kv: -(kv[1]["background"] + kv[1]["programs"])))
    return report


def diff_events(old, new):
    """Journal events for what changed since the previous sweep."""
    ev = []
    if not old:
        return [{"severity": "info", "kind": "radar", "title": "Hidden-software radar baseline recorded",
                 "detail": f"{len(new['installed'])} programs ({sum(p['hidden'] for p in new['installed'])} hidden), "
                           f"{len(new['background'])} background items, {len(new['companies'])} companies, "
                           f"{len(new['extensions'])} browser extensions"}]
    before = {(p["name"], p["company"]) for p in old["installed"]}
    for p in new["installed"]:
        if (p["name"], p["company"]) not in before:
            ev.append({"severity": "medium" if p["hidden"] else "low", "kind": "radar",
                       "title": f"{'Hidden program' if p['hidden'] else 'New program'} from {p['company']}: {p['name']}",
                       "detail": f"version {p['version']} {p['location']}".strip()})
    before = {(b["kind"], b["name"]) for b in old["background"]}
    for b in new["background"]:
        if (b["kind"], b["name"]) not in before:
            ev.append({"severity": "medium", "kind": "radar", "title": f"New background {b['kind']} from {b['company']}: {b['name']}",
                       "detail": b["target"]})
    before = {(e["browser"], e["id"]) for e in old["extensions"]}
    for e in new["extensions"]:
        if (e["browser"], e["id"]) not in before:
            ev.append({"severity": "medium" if e["broad"] else "low", "kind": "radar",
                       "title": f"New {e['browser']} extension: {e['name']}",
                       "detail": ("Broad powers: " + ", ".join(e["broad"])) if e["broad"] else ""})
    seen = {(r["capability"], r["app"], r["last_start"]) for r in old["privacy"]}
    for r in new["privacy"]:
        if r["capability"] in SENSITIVE and (r["capability"], r["app"], r["last_start"]) not in seen:
            when = time.strftime("%H:%M %d %b", time.localtime(r["last_start"]))
            ev.append({"severity": "medium" if "screen" in r["what"] else "low", "kind": "privacy",
                       "title": f"{Path(r['app']).name or r['app']} used your {r['what']}", "detail": f"at {when}" + (" (still in use)" if r["in_use"] else "")})
    old_w = {w["product"] for w in old.get("watchers", [])}
    for w in new["watchers"]:
        if w["product"] not in old_w:
            ev.append({"severity": "high", "kind": "radar", "title": f"Monitoring software found: {w['product']}",
                       "detail": f"{w['where']}: {w['evidence']}"})
    if new["recall"]["verdict"] == "has snapshots" and old["recall"]["verdict"] != "has snapshots":
        ev.append({"severity": "medium", "kind": "privacy", "title": "Windows Recall is storing screen snapshots",
                   "detail": "Turn it off in Settings > Privacy & security > Recall & snapshots."})
    return ev


class Radar:
    def __init__(self, path=None, sources=None):
        self.path = path or (data_dir() / "radar.json")
        self.sources = sources

    def last(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def tick(self):
        old = self.last()
        new = sweep(self.sources)
        ev = diff_events(old, new)
        if old is None and new["watchers"]:
            ev += [{"severity": "high", "kind": "radar", "title": f"Monitoring software found: {w['product']}",
                    "detail": f"{w['where']}: {w['evidence']}"} for w in new["watchers"]]
        atomic_write(self.path, json.dumps(new, default=str))
        return ev
