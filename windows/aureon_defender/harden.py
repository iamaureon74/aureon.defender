"""Protect this PC: every protective setting at its safest value, in one go, with undo.

plan()            what would change (current -> target), grouped, read-only
apply_user()      per-user changes (privacy settings, Aureon's own protections) - no admin
apply_machine()   machine-wide changes - run in the elevated `aureon.defender harden --apply` process
undo()            puts every recorded value back
Each previous value is recorded before anything changes (harden_backup.json).
"""
import json
import subprocess

from .core import data_dir, user_dir

NOWIN = 0x08000000
HKLM, HKCU = "HKLM", "HKCU"

# (id, group, title, why, hive, key, value, safe, kind)  kind: reg | defender | firewall | smb
MACHINE = [
    ("autorun", "Devices", "AutoRun off for every drive", "USB sticks and discs can't start programs by themselves.",
     HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoDriveTypeAutoRun", 255, "reg"),
    ("smb1", "Network", "SMBv1 off", "The protocol WannaCry spread through.", None, None, "EnableSMB1Protocol", False, "smb"),
    ("llmnr", "Network", "LLMNR broadcasts off", "Stops attackers on the same WiFi answering name lookups to steal password hashes.",
     HKLM, r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", 0, "reg"),
    ("remote_assistance", "Network", "Remote Assistance off", "No one can be invited to view or control this PC.",
     HKLM, r"SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", 0, "reg"),
    ("rdp", "Network", "Remote Desktop off", "Closes the most attacked remote-login service.",
     HKLM, r"SYSTEM\CurrentControlSet\Control\Terminal Server", "fDenyTSConnections", 1, "reg"),
    ("delivery_optimization", "Network", "Updates not shared with the internet", "Your PC stops uploading Windows updates to strangers.",
     HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config", "DODownloadMode", 0, "reg"),
    ("firewall", "Network", "Firewall on, inbound blocked", "All three profiles: domain, private, public.", None, None, "firewall", True, "firewall"),
    ("recall", "Privacy", "Recall off (policy)", "Windows can't take screen snapshots.",
     HKLM, r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis", 1, "reg"),
    ("activity", "Privacy", "Activity history off", "Apps, files and sites you used aren't logged.",
     HKLM, r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", 0, "reg"),
    ("telemetry", "Privacy", "Diagnostic data: required only", "Optional usage and browsing data stops going to Microsoft.",
     HKLM, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 1, "reg"),
    ("pua", "Defender", "Block potentially unwanted apps", "Adware, bundled toolbars, crypto miners.", None, None, "PUAProtection", 1, "defender"),
    ("netprot", "Defender", "Network protection", "Blocks connections to known malicious sites from any app.", None, None, "EnableNetworkProtection", 1, "defender"),
    ("cfa", "Defender", "Ransomware folder protection", "Only trusted apps can change Documents, Pictures and Desktop. Some apps may need allowing.",
     None, None, "EnableControlledFolderAccess", 1, "defender"),
]
ASR = {
    "d4f940ab-401b-4efc-aadc-ad5f3c50688a": "Office apps can't start other programs",
    "9e6c4e1f-7d60-472f-ba1a-a39ef669e4b2": "Block password theft from LSASS",
    "be9ba2d9-53ea-4cdc-84e5-9b1eeee46550": "Block programs in email attachments",
    "5beb7efe-fd9a-4556-801d-275e5ffc04cc": "Block obfuscated scripts",
    "b2b3f03d-6a65-4f7b-a9c7-1c7ef74a9ba4": "Block untrusted programs from USB drives",
    "56a863a9-875e-4185-98a7-b882c64b5ce5": "Block abused vulnerable drivers",
    "e6db77e5-3df2-4cf1-b95a-636979351e5b": "Block persistence through WMI",
    "d3e037e1-3eb8-44c8-a917-57927947596d": "Block scripts launching downloaded programs",
}
AUREON = {"realtime": True, "auto_quarantine": True, "use_defender_engine": True, "defender_relay": True, "use_yara": True,
          "canary": True, "network_monitor": True, "dns_shield_hosts": True, "block_trackers": True, "wifi_watch": True,
          "hid_guard": True, "hid_lock": True, "device_history": True, "radar": True, "persistence_monitor": True,
          "leak_audit": True, "phone_watch": True, "clipboard_guard": True, "feeds_online": True}


def _ps(script, timeout=60):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                       timeout=timeout, creationflags=NOWIN)
    return r.stdout.strip()


def _reg_get(hive, key, value):
    import winreg
    root = winreg.HKEY_LOCAL_MACHINE if hive == HKLM else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(root, key) as k:
            return winreg.QueryValueEx(k, value)[0]
    except OSError:
        return None


def _defender_prefs():
    out = _ps("Get-MpPreference | Select PUAProtection,EnableNetworkProtection,EnableControlledFolderAccess,"
              "AttackSurfaceReductionRules_Ids,AttackSurfaceReductionRules_Actions | ConvertTo-Json -Compress")
    try:
        return json.loads(out or "{}")
    except ValueError:
        return {}


def current_state():
    st = {}
    d = _defender_prefs()
    for cid, *_rest in MACHINE:
        _, group, title, why, hive, key, value, safe, kind = (cid, *_rest)
        if kind == "reg":
            st[cid] = _reg_get(hive, key, value)
        elif kind == "defender":
            st[cid] = d.get(value)
        elif kind == "smb":
            v = _ps("(Get-SmbServerConfiguration).EnableSMB1Protocol")
            st[cid] = {"True": True, "False": False}.get(v)
        elif kind == "firewall":
            v = _ps("(Get-NetFirewallProfile | ? { -not $_.Enabled }).Count")
            st[cid] = v == "0"
    ids = [i.lower() for i in (d.get("AttackSurfaceReductionRules_Ids") or [])]
    acts = d.get("AttackSurfaceReductionRules_Actions") or []
    st["asr"] = {g: (acts[ids.index(g)] if g in ids and ids.index(g) < len(acts) else 0) for g in ASR}
    return st


def _ok(cid, now, safe):
    if cid == "telemetry":                       # 0 is even stricter than 1
        return now is not None and now <= safe
    return now == safe


def plan(state=None, settings=None, leaks=None):
    """[{id, group, title, why, now, target, needs_admin, done}]"""
    from .core import Settings
    from .leaks import USER_FIXABLE, audit
    state = state if state is not None else current_state()
    settings = settings or Settings().load()
    items = []
    for cid, group, title, why, hive, key, value, safe, kind in MACHINE:
        now = state.get(cid)
        items.append({"id": cid, "group": group, "title": title, "why": why, "now": now, "target": safe, "needs_admin": True,
                      "done": _ok(cid, now, safe)})
    for g, title in ASR.items():
        now = (state.get("asr") or {}).get(g, 0)
        items.append({"id": "asr:" + g, "group": "Defender", "title": title, "why": "Microsoft attack-surface reduction rule.",
                      "now": now, "target": 1, "needs_admin": True, "done": now == 1})
    for r in (leaks if leaks is not None else audit()):
        if r["id"] in USER_FIXABLE:
            items.append({"id": "leak:" + r["id"], "group": "Privacy", "title": r["title"], "why": r["why"], "now": r["value"],
                          "target": "private", "needs_admin": False, "done": r["ok"]})
    for k, v in AUREON.items():
        items.append({"id": "aureon:" + k, "group": "Aureon", "title": k.replace("_", " ").capitalize(), "why": "Aureon protection switch.",
                      "now": settings.get(k), "target": v, "needs_admin": True, "done": settings.get(k) == v})
    return items


def score(items):
    return round(100 * sum(i["done"] for i in items) / len(items)) if items else 100


def _backup_path(machine):
    return (data_dir() if machine else user_dir()) / "harden_backup.json"


def _record(machine, entries):
    p = _backup_path(machine)
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        b = {}
    for k, v in entries.items():
        b.setdefault(k, v)                       # keep the first (original) value
    p.write_text(json.dumps(b, indent=1), encoding="utf-8")


def apply_user():
    from .leaks import USER_FIXABLE, audit, fix
    done = []
    for r in audit():
        if not r["ok"] and r["id"] in USER_FIXABLE:
            fix(r["id"])
            done.append(r["id"])
    return done


def apply_machine():
    """Elevated only. Returns the list of things changed."""
    import winreg
    from .core import Settings
    state = current_state()
    _record(True, {k: v for k, v in state.items()})
    changed = []
    for cid, group, title, why, hive, key, value, safe, kind in MACHINE:
        if _ok(cid, state.get(cid), safe):
            continue
        try:
            if kind == "reg":
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, value, 0, winreg.REG_DWORD, int(safe))
            elif kind == "defender":
                _ps(f"Set-MpPreference -{value} {int(safe)}")
            elif kind == "smb":
                _ps("Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force")
            elif kind == "firewall":
                _ps("Set-NetFirewallProfile -All -Enabled True -DefaultInboundAction Block")
            changed.append(cid)
        except Exception:
            continue
    missing = [g for g, a in (state.get("asr") or {}).items() if a != 1]
    if missing:
        _ps("Add-MpPreference -AttackSurfaceReductionRules_Ids " + ",".join(missing) +
            " -AttackSurfaceReductionRules_Actions " + ",".join(["Enabled"] * len(missing)))
        changed += ["asr:" + g for g in missing]
    s = Settings()
    _record(True, {"aureon_settings": s.load()})
    s.save(dict(AUREON))
    changed.append("aureon settings")
    (data_dir() / "inbox").mkdir(exist_ok=True)
    (data_dir() / "inbox" / f"{__import__('time').time_ns()}.json").write_text(json.dumps({"type": "reload"}))
    return changed


def undo_machine():
    import winreg
    from .core import Settings
    try:
        b = json.loads(_backup_path(True).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    n = 0
    for cid, group, title, why, hive, key, value, safe, kind in MACHINE:
        if cid not in b:
            continue
        old = b[cid]
        try:
            if kind == "reg":
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE) as k:
                    if old is None:
                        try:
                            winreg.DeleteValue(k, value)
                        except OSError:
                            pass
                    else:
                        winreg.SetValueEx(k, value, 0, winreg.REG_DWORD, int(old))
            elif kind == "defender" and old is not None:
                _ps(f"Set-MpPreference -{value} {int(old)}")
            elif kind == "smb" and old is True:
                _ps("Set-SmbServerConfiguration -EnableSMB1Protocol $true -Force")
            n += 1
        except Exception:
            continue
    off = [g for g, a in (b.get("asr") or {}).items() if a != 1]
    if off:
        _ps("Remove-MpPreference -AttackSurfaceReductionRules_Ids " + ",".join(off))
    if "aureon_settings" in b:
        Settings().save(b["aureon_settings"])
    _backup_path(True).unlink(missing_ok=True)
    return n
