"""Leak audit: what this PC gives away, and how to stop it.

Each check reads one Windows setting and returns pass / leak with the plain fix. Per-user settings can be fixed
from the app in one click (and undone); machine-wide ones go through the administrator prompt.
Also lists every security product registered with Windows (to spot leftover corporate antivirus).
"""
import json
import subprocess

from .core import user_dir

HKCU, HKLM = "HKCU", "HKLM"
NOWIN = 0x08000000

# id: (title, why it leaks, hive, key, value, safe value, compare, fix text)
#   compare: "eq" safe when value == safe; "missing_ok" also safe when absent
CHECKS = {
    "advertising_id": ("Advertising ID", "Apps get a per-user ID to track you across apps for ads.",
                       HKCU, r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, "eq",
                       "Settings > Privacy & security > General > Let apps show me personalized ads: off"),
    "tailored": ("Tailored experiences", "Microsoft uses your diagnostic data to target tips and offers.",
                 HKCU, r"Software\Microsoft\Windows\CurrentVersion\Privacy", "TailoredExperiencesWithDiagnosticDataEnabled", 0, "eq",
                 "Settings > Privacy & security > Diagnostics & feedback > Tailored experiences: off"),
    "app_launch_tracking": ("App launch tracking", "Windows records every app you open to rank Start and search.",
                            HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Start_TrackProgs", 0, "eq",
                            "Settings > Privacy & security > General > Let Windows improve Start and search results: off"),
    "online_speech": ("Online speech recognition", "Voice input is sent to Microsoft's servers.",
                      HKCU, r"Software\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy", "HasAccepted", 0, "missing_ok",
                      "Settings > Privacy & security > Speech > Online speech recognition: off"),
    "inking_typing": ("Inking & typing personalization", "Words you type and write build a personal dictionary that can sync.",
                      HKCU, r"Software\Microsoft\InputPersonalization", "RestrictImplicitTextCollection", 1, "eq",
                      "Settings > Privacy & security > Inking & typing personalization: off"),
    "clipboard_cloud": ("Clipboard sync", "Everything you copy can be uploaded to your Microsoft account.",
                        HKCU, r"Software\Microsoft\Clipboard", "CloudClipboardAutomaticUpload", 0, "missing_ok",
                        "Settings > System > Clipboard > Sync across your devices: off"),
    "clipboard_history": ("Clipboard history", "Passwords and keys you copy stay in a history list (Win+V).",
                          HKCU, r"Software\Microsoft\Clipboard", "EnableClipboardHistory", 0, "missing_ok",
                          "Settings > System > Clipboard > Clipboard history: off"),
    "silent_app_installs": ("Silent app installs", "Windows installs suggested (sponsored) apps without asking.",
                            HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SilentInstalledAppsEnabled", 0, "eq",
                            "Aureon can switch this off for you"),
    "start_suggestions": ("Suggestions and ads in Start / Settings", "Microsoft shows promoted content based on your usage.",
                          HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338388Enabled", 0, "eq",
                          "Settings > Personalization > Start > Show recommendations for tips, shortcuts, new apps: off"),
    "feedback_prompts": ("Feedback prompts", "Windows asks for feedback and sends the answers with diagnostics.",
                         HKCU, r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", 0, "eq",
                         "Settings > Privacy & security > Diagnostics & feedback > Feedback frequency: Never"),
    "telemetry_level": ("Diagnostic data", "Optional diagnostic data sends app usage and browsing data to Microsoft.",
                        HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection", "AllowTelemetry", 1, "max",
                        "Settings > Privacy & security > Diagnostics & feedback > Send optional diagnostic data: off"),
    "activity_history": ("Activity history", "Apps, files and sites you used are logged on the device.",
                         HKLM, r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", 0, "eq",
                         "Settings > Privacy & security > Activity history > Store my activity history: off"),
    "delivery_optimization": ("Updates shared with the internet", "Your PC uploads Windows updates to strangers' PCs.",
                              HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config", "DODownloadMode", 1, "max",
                              "Settings > Windows Update > Advanced > Delivery Optimization: PCs on my local network only, or off"),
    "remote_assistance": ("Remote Assistance", "Someone you invite can view and control this PC.",
                          HKLM, r"SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", 0, "eq",
                          "System Properties > Remote > Allow Remote Assistance connections: off"),
    "llmnr": ("LLMNR name broadcasts", "Your PC shouts name lookups to the whole WiFi; attackers answer and steal hashes.",
              HKLM, r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", 0, "eq",
              "Aureon can switch this off (administrator prompt)"),
    "find_my_device": ("Find my device", "Your PC's location is uploaded to your Microsoft account.",
                       HKLM, r"SOFTWARE\Microsoft\MdmCommon\SettingValues", "LocationSyncEnabled", 0, "missing_ok",
                       "Settings > Privacy & security > Find my device: off (keep it on if theft is your bigger worry)"),
    "recall": ("Recall screen snapshots", "Windows takes pictures of your screen every few seconds and stores them.",
               HKCU, r"Software\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis", 1, "eq_or_hklm",
               "Settings > Privacy & security > Recall & snapshots: off"),
}
USER_FIXABLE = {k for k, v in CHECKS.items() if v[2] == HKCU and k != "recall"}


def _read(hive, key, value):
    import winreg
    root = winreg.HKEY_CURRENT_USER if hive == HKCU else winreg.HKEY_LOCAL_MACHINE
    try:
        with winreg.OpenKey(root, key) as k:
            return winreg.QueryValueEx(k, value)[0]
    except OSError:
        return None


def audit(read=_read):
    out = []
    for cid, (title, why, hive, key, value, safe, cmp, fix) in CHECKS.items():
        v = read(hive, key, value)
        if cmp == "eq":
            ok = v == safe
        elif cmp == "missing_ok":
            ok = v is None or v == safe
        elif cmp == "max":
            ok = v is not None and v <= safe
        elif cmp == "eq_or_hklm":
            ok = v == safe or read(HKLM, key.replace("Software", "SOFTWARE"), value) == safe
        else:
            ok = False
        out.append({"id": cid, "title": title, "why": why, "ok": ok, "value": v, "fix": fix,
                    "one_click": cid in USER_FIXABLE or cid in MACHINE_SAFE, "machine": hive == HKLM})
    out.sort(key=lambda r: (r["ok"], not r["one_click"]))
    return out


def fix(cid, write=None, backup=None):
    """Apply the safe value for a per-user check, remembering the old value for undo."""
    import winreg
    if cid not in USER_FIXABLE:
        raise ValueError("this one is machine-wide and needs the administrator prompt")
    title, why, hive, key, value, safe, cmp, _ = CHECKS[cid]
    backup = backup or (user_dir() / "leaks_backup.json")
    try:
        b = json.loads(backup.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        b = {}
    b.setdefault(cid, _read(hive, key, value))
    backup.write_text(json.dumps(b), encoding="utf-8")
    if write:
        write(hive, key, value, safe)
        return True
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, value, 0, winreg.REG_DWORD, int(safe))
    return True


MACHINE_SAFE = {"remote_assistance": 0, "llmnr": 0, "delivery_optimization": 0, "activity_history": 0, "telemetry_level": 0,
                "find_my_device": 0}


def fix_machine(cid):
    """Machine-wide fix. Runs only in the elevated `aureon.defender leaks fix <id>` process."""
    import winreg
    if cid not in MACHINE_SAFE:
        raise ValueError("no automatic machine fix for this one; follow the steps shown")
    _, _, hive, key, value, _, _, _ = CHECKS[cid]
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, value, 0, winreg.REG_DWORD, MACHINE_SAFE[cid])
    return True


def undo_all(backup=None):
    import winreg
    backup = backup or (user_dir() / "leaks_backup.json")
    try:
        b = json.loads(backup.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    for cid, old in b.items():
        _, _, hive, key, value, _, _, _ = CHECKS[cid]
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
            if old is None:
                try:
                    winreg.DeleteValue(k, value)
                except OSError:
                    pass
            else:
                winreg.SetValueEx(k, value, 0, winreg.REG_DWORD, int(old))
    backup.unlink(missing_ok=True)
    return len(b)


def security_products():
    """Antivirus / firewall / antispyware products registered with Windows Security Center."""
    ps = ("$o=@(); foreach($c in 'AntiVirusProduct','FirewallProduct','AntiSpywareProduct'){"
          "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName $c -ErrorAction SilentlyContinue | "
          "% { $o += [pscustomobject]@{kind=$c -replace 'Product','';name=$_.displayName;state=$_.productState;path=$_.pathToSignedProductExe} } };"
          "$o | ConvertTo-Json -Compress")
    try:
        raw = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                             timeout=30, creationflags=NOWIN).stdout
        rows = json.loads(raw or "[]")
    except Exception:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    for r in rows:
        st = int(r.get("state") or 0)
        r["enabled"] = bool(st & 0x1000)
        r["up_to_date"] = not bool(st & 0x10)
    return rows
