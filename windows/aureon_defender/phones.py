"""Phones: find hidden software on any Android phone (Pixel, Samsung, Xiaomi, OnePlus, Motorola, carrier phones...)
and inventory iPhones, from the laptop over USB. Also runs inside Termux on the phone itself.

Android (adb, USB debugging on - or Termux on the phone):
  every package incl. disabled and "uninstalled for this user" leftovers, grouped by company
  apps hidden from the launcher (no icon) - the classic stalkerware trick
  device admins, accessibility services, notification listeners (what spyware needs)
  sideloaded apps (not from an app store)
  recent use of camera, microphone, location, screen capture, SMS, call log, contacts per app (AppOps)
  known pre-installed trackers / adware installers / firmware spyware by package name
iPhone (libimobiledevice: ideviceinfo / ideviceinstaller):
  device + iOS version, every user app, and enterprise/developer-signed apps (provisioning profiles)
  Deep spyware checks on iPhone need an encrypted backup + MVT (see docs/PHONE.md); iOS doesn't expose more over USB.
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

NOWIN = 0x08000000 if os.name == "nt" else 0

VENDORS = [  # package prefix -> company
    ("com.google.", "Google"), ("com.android.", "Android (AOSP/Google)"), ("android", "Android (AOSP/Google)"),
    ("com.samsung.", "Samsung"), ("com.sec.", "Samsung"), ("com.osp.", "Samsung"), ("com.skms.", "Samsung"),
    ("com.facebook.", "Meta"), ("com.instagram.", "Meta"), ("com.whatsapp", "Meta"), ("com.meta.", "Meta"),
    ("com.microsoft.", "Microsoft"), ("com.amazon.", "Amazon"), ("com.netflix.", "Netflix"), ("com.spotify.", "Spotify"),
    ("com.qualcomm.", "Qualcomm"), ("com.qti.", "Qualcomm"), ("vendor.qti.", "Qualcomm"), ("com.mediatek.", "MediaTek"),
    ("com.miui.", "Xiaomi"), ("com.xiaomi.", "Xiaomi"), ("com.mi.", "Xiaomi"), ("com.huawei.", "Huawei"), ("com.hihonor.", "Honor"),
    ("com.oppo.", "OPPO"), ("com.coloros.", "OPPO (ColorOS)"), ("com.heytap.", "OPPO (HeyTap)"), ("com.oplus.", "OPPO/OnePlus"),
    ("com.oneplus.", "OnePlus"), ("com.realme.", "realme"), ("com.vivo.", "vivo"), ("com.bbk.", "vivo (BBK)"),
    ("com.motorola.", "Motorola"), ("com.lenovo.", "Lenovo"), ("com.lge.", "LG"), ("com.sonymobile.", "Sony"), ("com.sony.", "Sony"),
    ("com.nothing.", "Nothing"), ("com.asus.", "ASUS"), ("com.tcl.", "TCL"), ("com.zte.", "ZTE"), ("com.transsion.", "Transsion (Tecno/Infinix)"),
    ("com.verizon.", "Verizon"), ("com.vzw.", "Verizon"), ("com.att.", "AT&T"), ("com.tmobile.", "T-Mobile"), ("com.sprint.", "Sprint/T-Mobile"),
    ("com.dti.", "Digital Turbine"), ("com.digitalturbine.", "Digital Turbine"), ("com.aura.", "ironSource Aura"), ("com.ironsource.", "ironSource/Unity"),
    ("com.shannon.", "Samsung (Shannon modem)"), ("com.tencent.", "Tencent"), ("com.zhiliaoapp.", "ByteDance (TikTok)"), ("com.ss.android.", "ByteDance"), ("com.snapchat.", "Snap"),
    ("org.mozilla.", "Mozilla"), ("com.brave.", "Brave"), ("com.termux", "Termux"), ("org.fdroid.", "F-Droid"),
]

# Known problem packages. Kept to well-documented cases.
CONCERNS = {
    "com.adups.fota": ("high", "Adups FOTA - firmware updater caught sending texts/call logs to China (2016)"),
    "com.adups.fota.sysoper": ("high", "Adups FOTA helper"),
    "com.carrieriq.iqagent": ("high", "Carrier IQ - carrier diagnostics agent that logged keystrokes/usage"),
    "com.dti.folderlauncher": ("medium", "Digital Turbine - silently installs carrier-sponsored apps"),
    "com.dti.att": ("medium", "Digital Turbine Ignite (AT&T) - silent app installer"),
    "com.dti.tracfone": ("medium", "Digital Turbine Ignite - silent app installer"),
    "com.LogiaGroup.LogiaDeck": ("medium", "Digital Turbine / Logia - preloaded app installer"),
    "com.aura.oobe.samsung": ("medium", "ironSource Aura - preloaded app installer"),
    "com.aura.oobe.samsung.gl": ("medium", "ironSource Aura - preloaded app installer"),
    "com.facebook.appmanager": ("medium", "Meta App Manager - preinstalled, updates Facebook apps in the background"),
    "com.facebook.system": ("medium", "Meta App Installer - preinstalled background installer"),
    "com.facebook.services": ("medium", "Meta Services - preinstalled background service"),
    "com.verizon.mips.services": ("medium", "Verizon MIPS services - carrier analytics"),
    "com.verizon.llkagent": ("medium", "Verizon Custom Experience - ad/usage profiling agent"),
    "com.vzw.apnlib": ("low", "Verizon APN library"),
    "com.tmobile.pr.adapt": ("medium", "T-Mobile Adapt - device usage analytics"),
    "com.att.dh": ("low", "AT&T Device Help (diagnostics)"),
    "com.miui.analytics": ("medium", "Xiaomi analytics"),
    "com.miui.msa.global": ("medium", "Xiaomi MSA - system ads"),
    "com.huawei.hwid": ("low", "Huawei ID services"),
    "com.qualcomm.qti.qms.service.telemetry": ("medium", "Qualcomm telemetry"),
    "com.google.android.feedback": ("low", "Google feedback/crash reporter"),
    "com.google.android.safetycore": ("low", "Android System SafetyCore - installed silently by Google in 2025; on-device image classification for sensitive-content warnings. Removable in Settings > Apps"),
    "com.google.android.contactkeys": ("low", "Android System Key Verifier - installed silently by Google; verifies contacts' encryption keys"),
    "com.google.android.apps.gcs": ("low", "Google Connectivity Services - background network/WiFi helper, no icon"),
    "com.google.android.apps.helprtc": ("low", "Google Support Services - remote help sessions, no icon"),
    "com.google.android.adservices.api": ("low", "Android Privacy Sandbox ad services (Topics / ad measurement)"),
    "com.google.android.as.oss": ("low", "Private Compute Services - syncs on-device AI models"),
    "com.android.traceur": ("low", "System tracing (fine unless you didn't enable it)"),
    "com.samsung.android.mobileservice": ("low", "Samsung Mobile Services"),
    "com.sec.android.diagmonagent": ("medium", "Samsung diagnostic monitoring agent"),
    "com.samsung.android.dqagent": ("medium", "Samsung device quality agent (usage analytics)"),
}
STALKER_NAMES = re.compile(r"mspy|flexispy|cocospy|spyic|hoverwatch|spyzie|eyezy|xnspy|thetruthspy|ikeymonitor|"
                           r"spyhuman|cerberus|clevguard|kidsguard|mobistealth|highster|copy9|spymaster|truthspy|"
                           r"fonemonitor|minspy|spyine|qustodio|mmguardian|umobix|cell.?tracker|track.?view", re.I)
SENSITIVE_OPS = {"CAMERA": "camera", "RECORD_AUDIO": "microphone", "FINE_LOCATION": "precise location",
                 "COARSE_LOCATION": "location", "PROJECT_MEDIA": "screen recording", "READ_SMS": "text messages",
                 "READ_CALL_LOG": "call log", "READ_CONTACTS": "contacts", "SYSTEM_ALERT_WINDOW": "draw over other apps",
                 "READ_CLIPBOARD": "clipboard", "ACCESS_NOTIFICATIONS": "notifications"}
ADB_DIRS = ["%LOCALAPPDATA%/Android/Sdk/platform-tools", "C:/platform-tools", "%USERPROFILE%/platform-tools",
            "%LOCALAPPDATA%/Microsoft/WinGet/Packages/Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe/platform-tools"]


def company(pkg):
    for pre, c in VENDORS:
        if pkg == pre.rstrip(".") or pkg.startswith(pre):
            return c
    parts = pkg.split(".")
    return parts[1].capitalize() if len(parts) > 2 and parts[0] in ("com", "org", "net", "io", "app", "co") else "Other"


def find_adb():
    a = shutil.which("adb")
    if a:
        return a
    for d in ADB_DIRS:
        p = Path(os.path.expandvars(d)) / ("adb.exe" if os.name == "nt" else "adb")
        if p.exists():
            return str(p)
    return None


def on_android():
    return "com.termux" in os.environ.get("PREFIX", "") or Path("/system/build.prop").exists()


class Android:
    """run(cmd) executes a shell command on the phone: through adb from the laptop, or locally inside Termux."""
    def __init__(self, serial=None, run=None):
        self.serial = serial
        self._run = run
        if run is None:
            if on_android():
                self._run = lambda c: subprocess.run(["sh", "-c", c], capture_output=True, text=True, timeout=60).stdout
            else:
                adb = find_adb()
                if not adb:
                    raise RuntimeError("adb not found: install Android Platform Tools (winget install Google.PlatformTools)")
                base = [adb] + (["-s", serial] if serial else [])
                self._run = lambda c: subprocess.run(base + ["shell", c], capture_output=True, text=True, timeout=90,
                                                     creationflags=NOWIN, encoding="utf-8", errors="ignore").stdout

    def sh(self, cmd):
        return self._run(cmd) or ""

    @staticmethod
    def devices():
        adb = find_adb()
        if not adb:
            return {"adb": None, "devices": []}
        out = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=30, creationflags=NOWIN).stdout
        devs = []
        for l in out.splitlines()[1:]:
            parts = l.split()
            if len(parts) >= 2:
                info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
                devs.append({"serial": parts[0], "state": parts[1], "model": info.get("model", "").replace("_", " "),
                             "product": info.get("product", "")})
        return {"adb": adb, "devices": devs}

    def info(self):
        props = {}
        for line in self.sh("getprop").splitlines():
            m = re.match(r"\[(.+?)\]: \[(.*)\]", line)
            if m:
                props[m.group(1)] = m.group(2)
        return {"brand": props.get("ro.product.brand", ""), "model": props.get("ro.product.model", ""),
                "android": props.get("ro.build.version.release", ""), "patch": props.get("ro.build.version.security_patch", ""),
                "bootloader_locked": props.get("ro.boot.verifiedbootstate", "") == "green",
                "build": props.get("ro.build.fingerprint", "")}

    @staticmethod
    def _pkgs(text):
        return {l.split(":", 1)[1].split()[0].split("=")[-1] if "=" in l.split()[0] else l.split(":", 1)[1].split()[0]
                for l in text.splitlines() if l.startswith("package:")}

    def scan(self):
        listing = self.sh("pm list packages -f -i -u")
        apps = {}
        for l in listing.splitlines():
            m = re.match(r"package:(.+)=([\w.]+)\s+installer=(\S+)", l)
            if m:
                apps[m.group(2)] = {"package": m.group(2), "path": m.group(1), "installer": m.group(3)}
        system = self._pkgs(self.sh("pm list packages -s"))
        disabled = self._pkgs(self.sh("pm list packages -d"))
        installed_now = self._pkgs(self.sh("pm list packages"))
        launcher = set()
        for l in self.sh("cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER").splitlines():
            l = l.strip()
            if "/" in l and " " not in l:
                launcher.add(l.split("/")[0])
        admins = set(re.findall(r"ComponentInfo\{([\w.]+)/", self.sh("dumpsys device_policy")))
        acc = {s.split("/")[0] for s in self.sh("settings get secure enabled_accessibility_services").strip().split(":") if "/" in s}
        notif = {s.split("/")[0] for s in self.sh("settings get secure enabled_notification_listeners").strip().split(":") if "/" in s}
        out = []
        for pkg, a in apps.items():
            sysapp = pkg in system
            leftover = pkg not in installed_now
            store = a["installer"] in ("com.android.vending", "com.sec.android.app.samsungapps", "com.amazon.venezia",
                                       "com.huawei.appmarket", "com.xiaomi.market", "com.heytap.market", "org.fdroid.fdroid")
            item = {**a, "company": company(pkg), "system": sysapp, "disabled": pkg in disabled, "leftover": leftover,
                    "hidden_icon": not sysapp and not leftover and pkg not in launcher, "device_admin": pkg in admins,
                    "accessibility": pkg in acc, "notification_access": pkg in notif,
                    "sideloaded": not sysapp and not store and a["installer"] in ("null", "com.google.android.packageinstaller",
                                                                                  "com.android.packageinstaller", "com.android.shell"),
                    "flags": []}
            score = 0
            if pkg in CONCERNS:
                sev, why = CONCERNS[pkg]
                item["flags"].append(why)
                score += {"high": 60, "medium": 30, "low": 10}[sev]
            if STALKER_NAMES.search(pkg):
                item["flags"].append("name matches known stalkerware/monitoring app")
                score += 70
            if item["hidden_icon"]:
                item["flags"].append("installed app with no launcher icon (hidden)")
                score += 25
            if item["sideloaded"]:
                item["flags"].append("installed outside an app store")
                score += 15
            for k, label, pts in (("device_admin", "is a device administrator", 20), ("accessibility", "can read and control your screen (accessibility)", 30),
                                  ("notification_access", "reads all your notifications", 15)):
                if item[k] and not (sysapp and item["company"] in ("Google", "Android (AOSP/Google)", "Samsung")):
                    item["flags"].append(label)
                    score += pts
            item["risk"] = "high" if score >= 60 else "medium" if score >= 30 else "low" if score else "none"
            out.append(item)
        flagged = [a for a in out if a["risk"] != "none" or not a["system"]][:120]
        for a in flagged:
            a["recent"] = self.app_ops(a["package"])
        return {"device": self.info(), "apps": sorted(out, key=lambda a: ({"high": 0, "medium": 1, "low": 2, "none": 3}[a["risk"]], a["package"])),
                "summary": self.summary(out), "t": time.time()}

    def app_ops(self, pkg):
        """Recent sensitive accesses from AppOps: [{op, what, ago}]"""
        res = []
        for l in self.sh(f"cmd appops get {pkg}").splitlines():
            m = re.match(r"\s*(\w+):\s*(\w+).*?time=\+?([\dhmsd ]+?)\s*ago", l)
            if m and m.group(1) in SENSITIVE_OPS:
                ago = re.sub(r"\d+ms$", "", m.group(3).replace(" ", "")) or "0s"
                ago = re.sub(r"^(\d+d)\d+h\d+m\d+s$", r"\1", ago)          # 40d10h47m19s -> 40d
                ago = re.sub(r"^(\d+h\d+m)\d+s$", r"\1", ago)                # 2h39m4s -> 2h39m
                res.append({"op": m.group(1), "what": SENSITIVE_OPS[m.group(1)], "mode": m.group(2), "ago": ago,
                            "secs": _secs(ago)})
        return res

    @staticmethod
    def summary(apps):
        comp = {}
        for a in apps:
            c = comp.setdefault(a["company"], {"apps": 0, "system": 0, "hidden": 0, "flagged": 0})
            c["apps"] += 1
            c["system"] += a["system"]
            c["hidden"] += a["hidden_icon"]
            c["flagged"] += a["risk"] in ("medium", "high")
        return {"total": len(apps), "system": sum(a["system"] for a in apps), "user": sum(not a["system"] for a in apps),
                "hidden_icon": sum(a["hidden_icon"] for a in apps), "sideloaded": sum(a["sideloaded"] for a in apps),
                "leftovers": sum(a["leftover"] for a in apps), "high": sum(a["risk"] == "high" for a in apps),
                "medium": sum(a["risk"] == "medium" for a in apps),
                "companies": dict(sorted(comp.items(), key=lambda kv: -kv[1]["apps"]))}


def _secs(ago):
    total = 0
    for n, u in re.findall(r"(\d+)([dhms])", ago):
        total += int(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
    return total


class IPhone:
    @staticmethod
    def tools():
        return {t: shutil.which(t) for t in ("ideviceinfo", "ideviceinstaller", "ideviceprovision", "idevice_id")}

    def __init__(self, run=None):
        self.run = run or (lambda args: subprocess.run(args, capture_output=True, text=True, timeout=60, creationflags=NOWIN).stdout)

    def scan(self):
        t = self.tools()
        if not t["ideviceinfo"]:
            return {"error": "libimobiledevice not installed",
                    "how": "Install libimobiledevice for Windows, trust this PC on the iPhone, then rescan. "
                           "For a deep spyware check make an encrypted backup and run MVT (docs/PHONE.md)."}
        info = dict(l.split(": ", 1) for l in self.run(["ideviceinfo"]).splitlines() if ": " in l)
        apps = []
        if t["ideviceinstaller"]:
            for l in self.run(["ideviceinstaller", "-l", "-o", "list_all"]).splitlines()[1:]:
                parts = [p.strip().strip('"') for p in l.split(",")]
                if parts and "." in parts[0]:
                    bid = parts[0]
                    apps.append({"bundle": bid, "version": parts[1] if len(parts) > 1 else "", "name": parts[2] if len(parts) > 2 else bid,
                                 "company": "Apple" if bid.startswith("com.apple.") else company(bid),
                                 "flags": ["name matches known stalkerware/monitoring app"] if STALKER_NAMES.search(bid) else []})
        profiles = []
        if t["ideviceprovision"]:
            for l in self.run(["ideviceprovision", "list"]).splitlines():
                if " - " in l:
                    profiles.append(l.strip())
        return {"device": {"name": info.get("DeviceName"), "model": info.get("ProductType"), "ios": info.get("ProductVersion")},
                "apps": apps, "provisioning_profiles": profiles,
                "notes": (["Enterprise/developer provisioning profiles are installed: apps outside the App Store can run. "
                           "Remove any you don't recognise in Settings > General > VPN & Device Management."] if profiles else [])}


def scan_all():
    """Every connected phone. Never raises."""
    out = {"t": time.time(), "android": [], "iphone": None}
    try:
        devs = Android.devices()
        out["adb"] = devs["adb"]
        for d in devs["devices"]:
            if d["state"] != "device":
                out["android"].append({"serial": d["serial"], "state": d["state"],
                                       "error": "Unlock the phone and tap Allow on the USB debugging prompt" if d["state"] == "unauthorized" else d["state"]})
                continue
            try:
                res = Android(d["serial"]).scan()
                res["serial"] = d["serial"]
                out["android"].append(res)
            except Exception as e:
                out["android"].append({"serial": d["serial"], "error": f"{e.__class__.__name__}: {e}"})
    except Exception as e:
        out["android_error"] = str(e)
    try:
        out["iphone"] = IPhone().scan()
    except Exception as e:
        out["iphone"] = {"error": str(e)}
    return out
