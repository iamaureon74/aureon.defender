"""User-session agent: dashboard server, toast alerts, screen lock on USB alerts, desktop widget.

The engine may run as SYSTEM (installed) and can't show toasts or lock your session, so this small
process does those for it by following the event journal.

Dashboard security: bound to 127.0.0.1 only, random per-run token required on every API call,
Host header pinned (stops DNS-rebinding), JSON-only POSTs (stops cross-site form posts).
"""
import ctypes
import json
import re
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import VERSION, Journal, Settings, atomic_write, data_dir, user_dir
from aureon.capability_plan import plan as capability_plan
from .integrations import availability
from .quarantine import Vault
from .studio import PRESET_GROUPS, PRESETS, Studio, WIDGET_DEFAULT
from .winmap import WINMAP

HERE = Path(__file__).resolve().parent
NOWIN = 0x08000000


def readable(pal):
    """Wallpaper colours made usable for UI: deep background, lifted surface, clear accent, light text."""
    def rgb(h):
        return [int(h[i:i + 2], 16) for i in (1, 3, 5)]

    def hx(c):
        return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in c)

    def lum(c):
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    bg, sf, ac, tx = (rgb(h) for h in pal)
    k = 22 / max(lum(bg), 1) if lum(bg) > 22 else 1           # keep the background dark
    bg = [v * k for v in bg]
    sf = [b + (s - b) * 0.5 + 10 for b, s in zip(bg, sf)]
    if lum(ac) < 125:                                         # accent must stand out on dark
        m = 150 / max(lum(ac), 1)
        ac = [min(255, v * m) for v in ac]
    if lum(tx) < 200:
        tx = [t + (255 - t) * 0.75 for t in tx]
    return [hx(bg), hx(sf), hx(ac), hx(tx)]


PICK_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{TopMost=$true; ShowInTaskbar=$false; WindowState='Minimized'}
if ($env:AUR_KIND -eq 'folder') {
  $d = New-Object System.Windows.Forms.FolderBrowserDialog -Property @{Description='Choose a folder for aureon.defender'; UseDescriptionForTitle=$true}
  if ($d.ShowDialog($owner) -eq 'OK') { $d.SelectedPath }
} else {
  $d = New-Object System.Windows.Forms.OpenFileDialog -Property @{Multiselect=$true; Title='Choose files for aureon.defender'}
  if ($env:AUR_FILTER) { $d.Filter = $env:AUR_FILTER }
  if ($d.ShowDialog($owner) -eq 'OK') { $d.FileNames }
}
"""


def pick(kind="files", flt=""):
    """The normal Windows file/folder picker, so nobody has to type a path."""
    import subprocess as sp
    env = dict(os.environ, AUR_KIND=kind, AUR_FILTER=flt)
    out = sp.run(["powershell", "-NoProfile", "-STA", "-Command", PICK_PS], capture_output=True, text=True, env=env,
                 timeout=600, creationflags=NOWIN).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


# ---------------- notifications ----------------
TOAST_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $x.GetElementsByTagName('text')
$n.Item(0).AppendChild($x.CreateTextNode($env:AUR_TITLE)) > $null
$n.Item(1).AppendChild($x.CreateTextNode($env:AUR_BODY)) > $null
$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


def toast(title, body):
    """Text goes through environment variables, never into the script, so file names can't inject code."""
    env = dict(os.environ, AUR_TITLE=title[:120], AUR_BODY=body[:240])
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", TOAST_PS], env=env,
                         creationflags=NOWIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def lock_workstation():
    if os.name == "nt":
        ctypes.windll.user32.LockWorkStation()


class Follower:
    """Tails the journal; hands medium/high events to the notifier; locks on USB alerts that ask for it."""
    def __init__(self, journal, notify=None, lock=lock_workstation, notifier=None):
        from .notify import Notifier
        self.j, self.lock = journal, lock
        if notify is not None:                     # simple callback (tests / legacy)
            self.notifier = None
            self.notify = notify
        else:
            from .notify import silent_setting
            self.notifier = notifier or Notifier(silent=silent_setting)
        self.seen = {e["id"] for e in journal.recent(500)}

    def poll(self):
        fresh = [e for e in reversed(self.j.recent(100)) if e["id"] not in self.seen]
        for e in fresh:
            self.seen.add(e["id"])
            if e.get("lock"):
                self.lock()
            if self.notifier:
                self.notifier.handle(e)
            elif e["severity"] in ("medium", "high"):
                self.notify(("⚠ " if e["severity"] == "high" else "") + e["title"], e.get("detail", ""))
        return fresh


# ---------------- elevation helpers ----------------
def exe_cmd():
    """How to re-launch ourselves: the frozen exe, or python -m aureon_defender in dev."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "aureon_defender"]


def run_elevated(args):
    cmd = exe_cmd() + args
    params = subprocess.list2cmdline(cmd[1:])
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", cmd[0], params, str(HERE.parent), 0)
    return r > 32


def engine_alive():
    try:
        st = json.loads((data_dir() / "status.json").read_text(encoding="utf-8"))
        return time.time() - st.get("heartbeat", 0) < 30, st
    except (OSError, ValueError):
        return False, {}


def inbox(req):
    box = data_dir() / "inbox"
    box.mkdir(exist_ok=True)
    (box / f"{time.time_ns()}.json").write_text(json.dumps(req), encoding="utf-8")


def phone_events(old, new):
    out = []
    old_apps = {}
    for d in (old or {}).get("android", []):
        for a in d.get("apps", []):
            old_apps[(d.get("serial"), a["package"])] = a
    for d in new.get("android", []):
        if "apps" not in d:
            if d.get("error"):
                out.append({"severity": "low", "kind": "phone", "title": f"Phone {d.get('serial')}: {d['error']}"})
            continue
        dev = f"{d['device']['brand'].title()} {d['device']['model']}"
        first = not any(k[0] == d["serial"] for k in old_apps)
        if first:
            sm = d["summary"]
            out.append({"severity": "info", "kind": "phone", "title": f"{dev}: first scan",
                        "detail": f"{sm['total']} packages ({sm['system']} preinstalled), {sm['hidden_icon']} without an icon, "
                                  f"{sm['sideloaded']} sideloaded, {sm['high']} high and {sm['medium']} medium risk"})
        for a in d["apps"]:
            prev = old_apps.get((d["serial"], a["package"]))
            if (first and a["risk"] in ("medium", "high")) or (not first and prev is None and (a["risk"] != "none" or not a["system"])):
                sev = {"high": "high", "medium": "medium"}.get(a["risk"], "low")
                out.append({"severity": sev, "kind": "phone",
                            "title": f"{dev}: {'new app ' if not first else ''}{a['package']} ({a['company']})",
                            "detail": "; ".join(a["flags"]) or "installed"})
    return out


# ---------------- HTTP API ----------------
LAN_ALLOWED = {"/api/scan", "/api/phones/scan", "/api/radar", "/api/devices/sweep", "/api/assets/scan"}


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Api:
    def __init__(self, studio=None, journal=None, settings=None, vault=None, elevate=run_elevated, readonly=False, ujournal=None):
        self.studio = studio or Studio()
        self.j = journal or Journal()
        self.uj = ujournal or Journal(user_dir() / "events.jsonl")     # agent-side events (phones); always writable
        self.settings = settings or Settings()
        self.vault = vault or Vault()
        self.elevate = elevate
        self.readonly = readonly                 # phone link: view + scans only
        self.lan = None

    def state(self):
        alive, st = engine_alive()
        caps = {}
        for cid, (status, how, src) in WINMAP.items():
            caps.setdefault(status, []).append({"id": cid, "how": how, "from": src})
        events = sorted(self.j.recent(80) + self.uj.recent(40), key=lambda e: e["t"], reverse=True)[:100]
        local_job = self.scan_jobs().snapshot()
        engine_job = st.get("scan_job") if alive else None
        return {"version": VERSION, "scan_job": local_job if local_job.get("status") in ("running", "cancelling") or not engine_job else engine_job, "integrations": availability(), "capability_plan": capability_plan(), "telemetry": self.telemetry_state(), "engine": {"alive": alive, **st}, "events": events,
                "radar": load_json(data_dir() / "radar.json"), "phones": load_json(user_dir() / "phones.json"),
                "devices": load_json(data_dir() / "devices.json") or load_json(user_dir() / "devices.json"),
                "leaks": self.leaks_state(), "browsers": self.browsers_state(), "theme": self.theme(),
                "hardware": load_json(user_dir() / "hardware.json"), "harden": self.harden_state(),
                "controls": self.controls_state(), "live": self.live_state(), "vault": {"exists": self.pwvault().exists(), "unlocked": self.vault_pin is not None},
                "catalog": self.catalog_state(),
                "sentry": self.sentry_state(), "netpower": self.netpower_state(), "assets": self.assets_state(),
                "phone_link": self.lan_info(), "readonly": self.readonly,
                "ui_appearance": load_json(user_dir() / "interface.json"),
                "quarantine": self.vault.list(), "studio": self.studio.current(), "presets": {k: {"mode": v["mode"], "accent": v["accent"], "palette": v["palette"], "font": v["widget"]["font"],
                "group": next((g for g, names in PRESET_GROUPS.items() if k in names), "")} for k, v in PRESETS.items()},
                "widget": self.widget_cfg(), "memory": self.memory_state(), "settings": {**self.settings.load(), "auto_clean_downloads": self.cleanup_enabled(), "auto_clean_mode": self.cleanup_mode()}, "winmap": caps}

    def memory_state(self):
        k = getattr(self, "keeper", None)
        if k is not None:
            return k.status()
        try:
            from .memory import Keeper
            return Keeper(folders=[], hw={"interval_scale": 1}).status()
        except Exception:
            return {}

    def cleanup_enabled(self):
        from .core import load_json
        policy = load_json(user_dir() / "cleanup-policy.json", {}) or {}
        return policy.get("enabled", self.settings.load().get("auto_clean_downloads", False)) is True

    def cleanup_mode(self):
        from .core import load_json
        policy = load_json(user_dir() / "cleanup-policy.json", {}) or {}
        mode = policy.get("mode")
        return mode if mode in ("copy", "replace") else self.settings.load().get("auto_clean_mode", "copy")

    _scan_jobs = None

    @classmethod
    def scan_jobs(cls):
        from .scan_jobs import ScanJobs
        if cls._scan_jobs is None:
            cls._scan_jobs = ScanJobs()
        return cls._scan_jobs

    def telemetry_state(self):
        try:
            from .telemetry import collect
            from .sensors import collect as sensors
            return {**collect(), "sensors":sensors()}
        except Exception as ex:
            return {"error":str(ex)}

    _netpower_cache = (0, None)
    _assets_cache = (0, None)

    def sentry_state(self):
        from . import sentry
        try:
            return sentry.collect()
        except Exception as ex:
            return {"error": str(ex)}

    def netpower_state(self):
        t, val = Api._netpower_cache
        if time.time() - t > 60 or val is None:
            from . import powerline, wifi_shield
            try:
                val = {"wifi": wifi_shield.status(), "powerline": powerline.audit()}
                from aureon.security_node import load_report as load_node_report
                node_report = core.data_dir() / "security-node.json"
                if node_report.exists():
                    try:
                        val["security_node"] = load_node_report(node_report)
                    except (ValueError, OSError, KeyError, TypeError) as ex:
                        val["security_node"] = {"error": str(ex)}
                from aureon.infrastructure import load_report
                inventory = core.data_dir() / "infrastructure.json"
                if inventory.exists():
                    try:
                        val["infrastructure"] = load_report(inventory, inventory.with_name("infrastructure-telemetry.jsonl"))
                    except (ValueError, OSError, TypeError) as ex:
                        val["infrastructure"] = {"error": str(ex)}
            except Exception as ex:
                val = {"error": str(ex)}
            Api._netpower_cache = (time.time(), val)
        return val

    def assets_state(self):
        t, val = Api._assets_cache
        if time.time() - t > 30 or val is None:
            from . import assets
            try:
                val = {"devices": assets.registry()}
            except Exception as ex:
                val = {"error": str(ex)}
            Api._assets_cache = (time.time(), val)
        return val

    def leaks_state(self):
        from .leaks import audit
        saved = load_json(data_dir() / "leaks.json") or load_json(user_dir() / "leaks.json") or {}
        return {"checks": audit(), "products": saved.get("products", []), "t": time.time()}

    _browsers_cache = (0, None)

    def browsers_state(self):
        t, val = Api._browsers_cache
        if time.time() - t > 60 or val is None:
            from .noah import browsers, manifest
            radar = load_json(data_dir() / "radar.json") or {}
            try:
                val = {"list": browsers(radar.get("extensions")), "version": manifest()["version"]}
            except Exception as ex:
                val = {"list": [], "error": str(ex)}
            Api._browsers_cache = (time.time(), val)
        return val

    _wall_cache = (None, None)

    def theme(self):
        """The app's colours: a chosen look, or (default) sampled from the actual desktop wallpaper's pixels."""
        name = (load_json(user_dir() / "agent_prefs.json", {}) or {}).get("theme", "Wallpaper")
        if name == "Wallpaper":
            from .studio import current_wallpaper
            wp = current_wallpaper()
            try:
                sig = (wp, os.path.getmtime(wp)) if wp else None
            except OSError:
                sig = None
            if sig and Api._wall_cache[0] == sig:
                return Api._wall_cache[1]
            if sig:
                try:
                    from .noah import palette_from_image
                    pal = readable(palette_from_image(wp))
                    t = {"name": "Wallpaper", "palette": pal, "accent": pal[2], "mode": "dark", "source": wp}
                    Api._wall_cache = (sig, t)
                    return t
                except Exception:
                    pass
            name = "Ember"
        p = PRESETS.get(name) or PRESETS["Ember"]
        return {"name": name, "palette": p["palette"], "accent": p["accent"], "mode": p["mode"]}

    vault_pin = None
    vault_until = 0
    _controls_cache = (0, None)
    _catalog_cache = (0, None)
    _live_cache = (0, None)

    def pwvault(self):
        from .vault import Vault
        return Vault()

    def _pin(self):
        if self.vault_pin and time.time() < Api.vault_until:
            Api.vault_until = time.time() + 300              # stays open 5 minutes after last use
            return self.vault_pin
        Api.vault_pin = None
        raise PermissionError("the vault is locked")

    def controls_state(self):
        t, val = Api._controls_cache
        if time.time() - t > 30 or val is None:
            from . import controls as c
            try:
                val = {"telemetry": c.telemetry_state(), "usb_blocked": c.usb_storage_blocked(), "wifi_allowlist": c.wifi_filters()["denyall"],
                       "saved_networks": len(c.saved_networks()), "plugged": c.plugged_devices(), "bt_kinds": c.BT_KINDS}
            except Exception as ex:
                val = {"error": str(ex)}
            Api._controls_cache = (time.time(), val)
        return val

    def catalog_state(self):
        t, val = Api._catalog_cache
        if time.time() - t > 300 or val is None:
            from .browsers import catalog, installed_ids
            from .noah import browsers as present
            try:
                inst = installed_ids()
                names = {b["name"].lower() for b in present()}
                rows = catalog(inst)
                for r in rows:
                    r["installed"] = r["installed"] or r["name"].lower() in names
                val = rows
            except Exception:
                val = []
            Api._catalog_cache = (time.time(), val)
        return val

    def live_state(self):
        """WiFi, Bluetooth and plugged-in devices for the overview (cheap; cached 8 s)."""
        t, val = Api._live_cache
        if time.time() - t < 8 and val is not None:
            return val
        import subprocess as sp
        wifi = {}
        try:
            out = sp.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10, creationflags=NOWIN).stdout
            g = lambda k: (re.search(rf"^\s*{k}\s*:\s*(.+)$", out, re.M) or [None, None])[1]
            wifi = {"ssid": g("SSID"), "signal": g("Signal"), "state": g("State"), "auth": g("Authentication"), "band": g("Band")}
        except Exception:
            pass
        from .devices import describe, present_ids, tracked
        bt, other = [], []
        for i in present_ids():
            if not tracked(i):
                continue
            from .devices import is_builtin
            if is_builtin(i) and not i.upper().startswith(("BTHENUM", "BTHLE")):
                continue
            info = describe(i)
            from .devices import useful
            if not useful(info["name"], info["category"]):
                continue
            if i.upper().startswith(("BTHENUM\\", "BTHLE\\DEV_")):
                if info["name"] not in bt:
                    bt.append(info["name"])
            elif info["category"] in ("Storage", "Phone / media device", "Camera", "Audio", "Display", "Keyboard", "Mouse") and info["name"] not in [o["name"] for o in other]:
                other.append({"name": info["name"], "category": info["category"]})
        val = {"wifi": wifi, "bluetooth": bt, "devices": other[:12]}
        Api._live_cache = (time.time(), val)
        return val

    _harden_cache = (0, None)

    def harden_state(self):
        t, val = Api._harden_cache
        if time.time() - t > 120 or val is None:
            try:
                from .harden import plan, score
                items = plan(settings=self.settings.load())
                val = {"score": score(items), "items": items}
            except Exception as ex:
                val = {"score": None, "items": [], "error": str(ex)}
            Api._harden_cache = (time.time(), val)
        return val

    def lan_info(self):
        prefs = load_json(user_dir() / "agent_prefs.json", {}) or {}
        return {"enabled": bool(prefs.get("phone_link")), "url": self.lan["url"] if self.lan else None}

    def scan_phones(self):
        from .phones import scan_all
        old = load_json(user_dir() / "phones.json")
        new = scan_all()
        atomic_write(user_dir() / "phones.json", json.dumps(new, default=str))
        for e in phone_events(old, new):
            self.uj.add(**e)
        return new

    def widget_cfg(self):
        try:
            return {**WIDGET_DEFAULT, **json.loads((user_dir() / "widget.json").read_text(encoding="utf-8"))}
        except (OSError, ValueError):
            return dict(WIDGET_DEFAULT)

    def post(self, path, body):
        s = self.studio
        if self.readonly and path not in LAN_ALLOWED:
            return 403, {"error": "The phone link is view-only. Change this on the laptop."}
        if path == "/api/interface":
            if not isinstance(body,dict) or not {"palette","reduced"}.issubset(body) or not set(body).issubset({"palette","reduced","dock","cursor"}) or body.get("palette") not in ("signal","frost","studio") or type(body.get("reduced")) is not bool or body.get("dock","left") not in ("left","right","bottom") or body.get("cursor","system") not in ("system","lime","precision"):
                return 400, {"error":"Choose supported app appearance options."}
            value={"palette":body["palette"],"reduced":body["reduced"],**{k:body[k] for k in ("dock","cursor") if k in body}}
            atomic_write(user_dir() / "interface.json",json.dumps(value))
            return 200, {"ui_appearance":value,"message":"Aureon appearance saved"}
        if path == "/api/devices/sweep":
            alive, _ = engine_alive()
            if alive:
                inbox({"type": "devices"})
            else:
                from .devices import sweep
                def run():
                    snap = sweep()
                    atomic_write(user_dir() / "devices.json", json.dumps(snap, default=str))
                threading.Thread(target=run, daemon=True).start()
            return 200, {"ok": True, "message": "Reading this PC's device history. Takes up to a minute."}
        if path == "/api/devices/clear":
            ok = self.elevate(["devices", "clear"])
            return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to clear Aureon's device log."}
        if path == "/api/scan/all":
            alive, st = engine_alive()
            if alive:
                if (st.get("scan_job") or {}).get("status") in ("running", "cancelling"):
                    return 409, {"error": "A full scan is already running"}
                inbox({"type": "full_scan"})
                return 200, {"ok": True, "message": "full scan started in the protection engine. it keeps going if you switch tabs or close this window; anything found is removed automatically unless the hardware needs it."}
            from .scanner import Scanner
            jobs = self.scan_jobs()
            try:
                state = jobs.start(Scanner(self.settings.load()), exclusions=[data_dir(), user_dir()], vault=self.vault, automatic=self.settings.load().get("auto_quarantine", True), journal=self.j)
            except ValueError as ex:
                return 409, {"error":str(ex)}
            return 200, {"ok":True,"message":"Scan started. Confirmed threats in your user folders follow your automatic-quarantine setting; uncertain matches need review. Access limits are listed separately.","scan":state}
        if path == "/api/scan/cancel":
            if engine_alive()[0]:
                inbox({"type": "scan_cancel"})
                return 200, {"ok": True, "message": "stopping the scan after the current file."}
            return 200, {"ok":True,"scan":self.scan_jobs().stop(),"message":"Cancellation requested; the current engine call may take up to two minutes."}
        if path == "/api/scan/quarantine":
            if body.get("confirm") is not True:
                return 400, {"error":"Review findings and confirm quarantine first"}
            results=self.scan_jobs().quarantine(body.get("ids"),self.vault)
            return 200, {"ok":True,"results":results,"message":f"Quarantined {sum('quarantine_id' in r for r in results)} files. Review Quarantine to restore or permanently delete."}
        if path == "/api/leaks/fix-all":
            from .leaks import audit, USER_FIXABLE, fix
            checks=audit();eligible=[c for c in checks if not c["ok"] and c["id"] in USER_FIXABLE]
            unresolved=[c for c in checks if not c["ok"] and c["id"] not in USER_FIXABLE]
            if body.get("confirm") is not True:
                return 200, {"preview":True,"eligible":eligible,"unresolved":unresolved,"message":"These supported per-user fixes are reversible. Machine/admin and manual checks remain separate."}
            results=[]
            for c in eligible:
                try:
                    fix(c["id"]);results.append({"id":c["id"],"ok":True})
                except OSError as ex:results.append({"id":c["id"],"ok":False,"error":str(ex)})
            return 200, {"ok":True,"results":results,"remaining":audit(),"message":f"Applied {sum(r['ok'] for r in results)} per-user fixes. {len(unresolved)} settings need separate admin/manual review. Undo is available."}
        if path == "/api/leaks/fix":
            from .leaks import MACHINE_SAFE, USER_FIXABLE, fix
            cid = body.get("id", "")
            if cid in USER_FIXABLE:
                fix(cid)
                return 200, {"ok": True, "message": "Fixed. Undo any time from Leaks."}
            if cid in MACHINE_SAFE:
                ok = self.elevate(["leaks", "fix", cid])
                return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to apply this machine-wide fix."}
            return 400, {"error": "follow the steps shown for this one"}
        if path == "/api/leaks/undo":
            from .leaks import undo_all
            return 200, {"ok": True, "message": f"Restored {undo_all()} settings"}
        if path == "/api/noah/setup":
            from .noah import open_setup, register_host
            res = open_setup(body.get("browser", ""))
            register_host()
            Api._browsers_cache = (0, None)
            return 200, {"ok": True, "message": f"In {body.get('browser')}: turn on Developer mode, choose Load unpacked, pick the folder that just opened.", **res}
        if path == "/api/tools/clean":
            from .noah import clean_media
            target = Path(body.get("path", "")).expanduser()
            files = [target] if target.is_file() else [f for f in target.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")][:500] if target.is_dir() else []
            if not files:
                return 400, {"error": "pick a .jpg/.png file or a folder with photos"}
            done = []
            for f in files:
                try:
                    done.append(clean_media(f))
                except (ValueError, OSError):
                    continue
            gps = sum(1 for d in done if d["had"].get("GPS"))
            return 200, {"ok": True, "message": f"Cleaned {len(done)} photo(s), {gps} had a location. Clean copies are saved as name.clean.jpg.", "files": done}
        if path == "/api/tools/breach":
            from .noah import breach_count
            pw = body.get("password", "")
            if not pw:
                return 400, {"error": "type a password"}
            try:
                n = breach_count(pw)
            except OSError:
                return 503, {"error": "Offline: the breach check needs the internet (only 5 characters of a hash are sent)."}
            return 200, {"count": n, "message": f"Found in {n:,} breaches. Change it everywhere you use it." if n else "Not found in known breaches."}
        if path == "/api/tools/secrets":
            from .noah import scan_secrets
            target = Path(body.get("path", "")).expanduser()
            if not target.exists():
                return 400, {"error": f"{target} does not exist"}
            hits = scan_secrets(target)
            return 200, {"hits": hits[:200], "message": f"{len(hits)} possible secret(s) found" if hits else "No secrets found."}
        if path == "/api/brightness":
            from .noah import brightness_set
            ok = brightness_set(body.get("level", 50))
            return (200 if ok else 400), {"ok": ok}
        if path == "/api/pick":
            return 200, {"paths": pick(body.get("kind", "files"), body.get("filter", ""))}
        if path == "/api/cleanup-policy":
            if type(body.get("enabled")) is not bool:
                return 400, {"error":"enabled must be true or false"}
            mode = body.get("mode", self.cleanup_mode())
            if mode not in ("copy", "replace"):
                return 400, {"error":"mode must be copy or replace"}
            if not atomic_write(user_dir() / "cleanup-policy.json", json.dumps({"enabled":body["enabled"],"mode":mode})):
                return 500, {"error":"Could not save your cleanup preference"}
            kept = ("Originals are kept as separate files." if mode == "copy" else
                    "Downloads are cleaned in place; each untouched original is kept privately in your profile for a limited time.")
            return 200, {"ok":True,"message":"Download cleanup preference saved for your Windows account. "+kept+" No machine-wide setting was changed."}
        if path == "/api/clean":
            from .clean import clean_batch
            result=clean_batch(body.get("paths", []))
            return 200, {"ok":True,**result,"message":f"Created {len(result['results'])} clean copies; originals retained. {len(result['errors'])} errors, {result['skipped']} unsupported/skipped files. Metadata cleanup does not remove all fingerprints."}
        if path == "/api/secrets/scan":
            from .clean import next_steps
            from .noah import scan_secrets
            hits = []
            for p in body.get("paths", []):
                hits += scan_secrets(p)
            for h in hits:
                h["next"] = next_steps(h["rule"])
            return 200, {"hits": hits[:200], "message": f"{len(hits)} possible secret(s) found" if hits else "No leaked keys found."}
        if path == "/api/secrets/redact":
            from .clean import redact_secret
            n = redact_secret(body.get("path", ""), body.get("rule", ""))
            return 200, {"ok": bool(n), "message": f"Blanked {n} occurrence(s). A .bak copy was kept." if n else "Nothing to blank."}
        if path.startswith("/api/vault/"):
            v = self.pwvault()
            act = path.rsplit("/", 1)[1]
            try:
                if act == "create":
                    v.create(body.get("pin", ""))
                    Api.vault_pin, Api.vault_until = body["pin"], time.time() + 300
                    return 200, {"ok": True, "message": "Vault created and unlocked", "entries": []}
                if act == "unlock":
                    entries = v.list(body.get("pin", ""))
                    Api.vault_pin, Api.vault_until = body["pin"], time.time() + 300
                    return 200, {"ok": True, "entries": entries}
                if act == "lock":
                    Api.vault_pin = None
                    return 200, {"ok": True, "message": "Vault locked"}
                if act == "list":
                    return 200, {"entries": v.list(self._pin())}
                if act == "add":
                    from .vault import generate
                    pw = body.get("password") or generate()
                    v.add(self._pin(), body.get("site", ""), body.get("username", ""), pw)
                    return 200, {"ok": True, "message": "Saved to the vault", "entries": v.list(self._pin())}
                if act == "reveal":
                    return 200, {"password": v.reveal(self._pin(), body.get("id", ""))}
                if act == "delete":
                    v.delete(self._pin(), body.get("id", ""))
                    return 200, {"ok": True, "entries": v.list(self._pin())}
                if act == "import":
                    n = 0
                    for p in body.get("paths", []):
                        n += v.import_csv(self._pin(), Path(p).read_text(encoding="utf-8-sig", errors="ignore"))
                    return 200, {"ok": True, "message": f"Imported {n} passwords. Delete the exported file now: it isn't encrypted.", "entries": v.list(self._pin())}
                if act == "generate":
                    from .vault import generate
                    return 200, {"password": generate(int(body.get("length", 20)))}
            except PermissionError as ex:
                return 403, {"error": str(ex)}
            except ValueError as ex:
                return 400, {"error": str(ex)}
            return 404, {"error": "unknown vault action"}
        if path == "/api/controls":
            act = body.get("action", "")
            if act in ("telemetry-close", "telemetry-open", "usb-block", "usb-allow", "wifi-on", "wifi-off"):
                Api._controls_cache = (0, None)
                ok = self.elevate(["controls", act])
                return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to apply this." if ok else "The administrator prompt was declined."}
            if act == "bt":
                try:
                    self.settings.save({"bt_limit": int(body.get("limit", 4)), "bt_allowed": list(body.get("allowed", []))})
                    inbox({"type": "reload"})
                    return 200, {"ok": True, "message": "Bluetooth limits saved"}
                except PermissionError:
                    tmp = user_dir() / "pending_settings.json"
                    tmp.write_text(json.dumps({"bt_limit": int(body.get("limit", 4)), "bt_allowed": list(body.get("allowed", []))}), encoding="utf-8")
                    ok = self.elevate(["settings", "--apply", str(tmp)])
                    return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to save."}
            return 400, {"error": "unknown control"}
        if path == "/api/logo":
            from . import icon as iconmod
            src = body.get("path", "")
            if not src:
                return 400, {"error": "choose a picture first"}
            try:
                if body.get("reset"):
                    iconmod.reset(); return 200, {"ok": True, "message": "Icon reset to the default."}
                iconmod.set_custom(src)
                return 200, {"ok": True, "message": "That picture is now the app icon — window, taskbar and notifications. Reopen the app to see the title-bar icon update."}
            except Exception as ex:
                return 400, {"error": str(ex)}
        if path == "/api/sentry/protect":
            from . import sentry
            on = bool(body.get("on", True))
            ok = sentry.protect_app_window(on)
            self.settings.save({"hide_from_capture": on})
            return 200, {"ok": ok, "message": ("The window is now hidden from screen recording." if on else "The window can be captured again.") if ok else "Open the app window first, then try again."}
        if path == "/api/wifi/favor":
            from . import wifi_shield
            Api._netpower_cache = (0, None)
            try:
                return 200, wifi_shield.favor_my_network()
            except Exception as ex:
                return 400, {"error": str(ex)}
        if path == "/api/assets/scan":
            from . import assets
            r = assets.scan(); Api._assets_cache = (0, None)
            return 200, {"ok": True, "message": f"{r['present']} devices here now, {r['total']} known.", **r, "new": len(r["new"])}
        if path == "/api/assets/label":
            from . import assets
            assets.label(body.get("id", ""), name=body.get("label"), trusted=body.get("trusted"))
            Api._assets_cache = (0, None)
            return 200, {"ok": True, "devices": assets.registry()}
        if path == "/api/assets/forget":
            from . import assets
            assets.forget(body.get("id", "")); Api._assets_cache = (0, None)
            return 200, {"ok": True, "devices": assets.registry()}
        if path == "/api/browsers/install":
            from .browsers import install
            install(body.get("id", ""))
            Api._catalog_cache = (0, None)
            return 200, {"ok": True, "message": "Installing in the background. It appears in your Start menu when done."}
        if path == "/api/harden/apply":
            from .harden import apply_user
            fixed = apply_user()
            ok = self.elevate(["harden", "--apply"])
            return (200 if ok else 403), {"ok": ok, "user_fixed": fixed, "message": "Approve the administrator prompt to apply the machine-wide protections." if ok else "The administrator prompt was declined; per-user privacy fixes were applied."}
        if path == "/api/harden/undo":
            from .leaks import undo_all
            undo_all()
            ok = self.elevate(["harden", "--undo"])
            return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to restore your previous settings."}
        if path == "/api/hardware/report":
            from .devices import history, live_log, timeline
            from .hardware import write_report
            out, data = write_report(timeline(history(fallback=False), live_log()))
            atomic_write(user_dir() / "hardware.json", json.dumps(data, default=str))
            os.startfile(str(out))
            return 200, {"ok": True, "message": f"Report saved to {out}"}
        if path == "/api/hardware/refresh":
            from .hardware import collect
            from .devices import history, live_log, timeline
            def run():
                atomic_write(user_dir() / "hardware.json", json.dumps(collect(timeline(history(fallback=False), live_log())), default=str))
            threading.Thread(target=run, daemon=True).start()
            return 200, {"ok": True, "message": "Reading hardware, ports and downloads…"}
        if path == "/api/feeds/key":
            key = str(body.get("key", "")).strip()
            if key and not re.fullmatch(r"[A-Za-z0-9]{20,100}", key):
                return 400, {"error": "That doesn't look like an abuse.ch Auth-Key (letters and digits only)."}
            try:
                self.settings.save({"abusech_key": key})
                inbox({"type": "reload"})
                inbox({"type": "update_feeds"})
                return 200, {"ok": True, "message": "Key saved. Feeds are refreshing now."}
            except PermissionError:
                tmp = user_dir() / "pending_settings.json"
                tmp.write_text(json.dumps({"abusech_key": key}), encoding="utf-8")
                ok = self.elevate(["settings", "--apply", str(tmp)])
                return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to save the key."}
        if path == "/api/theme":
            if body.get("name") not in PRESETS and body.get("name") != "Wallpaper":
                return 400, {"error": "unknown theme"}
            prefs = load_json(user_dir() / "agent_prefs.json", {}) or {}
            prefs["theme"] = body["name"]
            (user_dir() / "agent_prefs.json").write_text(json.dumps(prefs), encoding="utf-8")
            return 200, self.theme()
        if path == "/api/phones/scan":
            threading.Thread(target=self.scan_phones, daemon=True).start()
            return 200, {"ok": True, "message": "Scanning connected phones. Results appear in about 20 seconds."}
        if path == "/api/drain":
            from . import drain
            st = load_json(data_dir() / "status.json", {}) or {}
            top = (st.get("drain") or {}).get("top")
            if not top:                                   # engine not running: a short local sample instead
                m = drain.DrainMeter()
                m.tick()
                time.sleep(2)
                m.tick()
                top = m.top()
            return 200, {"ok": True, "drain_24h": top, "silent": drain.silent(), "listening": drain.listeners(),
                         "method": "CPU time per program (battery proxy); screen, radios and GPU are not attributed."}
        if path == "/api/radar":
            alive, _ = engine_alive()
            if alive:
                inbox({"type": "radar"})
            else:
                from .radar import Radar
                threading.Thread(target=lambda: [self.uj.add(**e) for e in Radar().tick()], daemon=True).start()
            return 200, {"ok": True, "message": "Radar sweep started. Results in about 10 seconds."}
        if path == "/api/phone-link":
            prefs = load_json(user_dir() / "agent_prefs.json", {}) or {}
            prefs["phone_link"] = bool(body.get("enabled"))
            (user_dir() / "agent_prefs.json").write_text(json.dumps(prefs), encoding="utf-8")
            if prefs["phone_link"] and not self.lan:
                ro = Api(readonly=True)
                self.lan = ro.lan = serve_lan(ro)
            elif not prefs["phone_link"] and self.lan:
                self.lan["server"].shutdown()
                self.lan = None
            return 200, {"ok": True, "message": "Phone link " + ("on" if prefs["phone_link"] else "off"), **self.lan_info()}
        if path == "/api/scan":
            p = Path(body.get("path", "")).expanduser()
            if not p.exists():
                return 400, {"error": f"{p} does not exist"}
            alive, _ = engine_alive()
            if alive:
                inbox({"type": "scan", "path": str(p)})
                return 200, {"ok": True, "message": "scanning in the protection engine; progress shows above and keeps going if you leave this page."}
            from .engine import Engine
            threading.Thread(target=lambda: Engine(journal=self.j).scan_path(p), daemon=True).start()
            return 200, {"ok": True, "message": "Engine not running: scanning in this window."}
        if path in ("/api/update", "/api/report", "/api/posture"):
            inbox({"type": {"/api/update": "update_feeds", "/api/report": "report", "/api/posture": "posture"}[path]})
            return 200, {"ok": True}
        if path == "/api/settings":
            try:
                cur = self.settings.save(body)
                inbox({"type": "reload"})
                return 200, {"ok": True, "settings": cur}
            except PermissionError:
                tmp = user_dir() / "pending_settings.json"
                tmp.write_text(json.dumps(body), encoding="utf-8")
                ok = self.elevate(["settings", "--apply", str(tmp)])
                return (200 if ok else 403), {"ok": ok, "message": "Protection settings need administrator approval."}
        if path in ("/api/quarantine/restore", "/api/quarantine/delete"):
            qid = body.get("id", "")
            if not qid.isalnum():
                return 400, {"error": "bad id"}
            action = path.rsplit("/", 1)[1]
            try:
                getattr(self.vault, action)(qid)
                return 200, {"ok": True}
            except PermissionError:
                ok = self.elevate(["quarantine", action, qid])
                return (200 if ok else 403), {"ok": ok, "message": "Approve the administrator prompt to finish."}
        if path == "/api/studio/preset":
            if body.get("name") not in PRESETS:
                return 400, {"error": "unknown preset"}
            res = s.apply_preset(body["name"])
            prefs = load_json(user_dir() / "agent_prefs.json", {}) or {}
            prefs["theme"] = body["name"]                       # the app takes on the look too
            (user_dir() / "agent_prefs.json").write_text(json.dumps(prefs), encoding="utf-8")
            Api._wall_cache = (None, None)
            return 200, {**res, "theme": self.theme()}
        if path == "/api/studio/set":
            b = body
            if "theme" in b:
                s.set_theme(b["theme"], b["theme"])
            if "accent" in b:
                s.set_accent(b["accent"], on_taskbar=bool(b.get("accent_taskbar", False)))
            if "transparency" in b:
                s.set_transparency(bool(b["transparency"]))
            if "taskbar" in b or "seconds" in b:
                cur = s.current()
                s.set_taskbar(b.get("taskbar", cur["taskbar"]), bool(b.get("seconds", cur["seconds"])))
            if "hours" in b:
                s.set_time_format(int(b["hours"]), b.get("date", "yyyy-MM-dd"))
            return 200, s.current()
        if path == "/api/studio/wallpaper":
            if body.get("path"):
                s.set_wallpaper(body["path"], body.get("style", "fill"))
            return 200, s.current()
        if path == "/api/studio/font":
            return 200, {"installed": s.install_font(body["path"])}
        if path == "/api/studio/restore":
            return 200, {"restored": s.restore()}
        if path == "/api/widget":
            cfg = {**self.widget_cfg(), **{k: v for k, v in body.items() if k in WIDGET_DEFAULT}}
            (user_dir() / "widget.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
            return 200, cfg
        return 404, {"error": "not found"}


def make_handler(api, token, port_ref, extra_hosts=()):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_host(self):
            ok = {f"127.0.0.1:{port_ref[0]}", f"localhost:{port_ref[0]}"} | {f"{h}:{port_ref[0]}" for h in extra_hosts}
            return self.headers.get("Host", "") in ok

        def _send(self, code, obj, ctype="application/json"):
            data = obj if isinstance(obj, bytes) else json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._ok_host():
                return self._send(403, {"error": "bad host"})
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == "/api/current-wallpaper" and q.get("t", [""])[0] == token:   # <img> carries the token in the URL
                from io import BytesIO
                from PIL import Image
                from .studio import current_wallpaper
                wp = current_wallpaper()
                if not wp or not os.path.exists(wp):
                    return self._send(404, {"error": "no wallpaper"})
                with Image.open(wp) as im:
                    im = im.convert("RGB")
                    im.thumbnail((1280, 800) if q.get("full") else (480, 300))
                    buf = BytesIO()
                    im.save(buf, "JPEG", quality=85)
                return self._send(200, buf.getvalue(), "image/jpeg")
            if u.path == "/icon.png":                       # public asset: <img> can't send the token header
                return self._send(200, (HERE / "ui" / "icon.png").read_bytes(), "image/png")
            if u.path == "/":
                if q.get("t", [""])[0] != token:
                    return self._send(403, {"error": "missing token"})
                html = (HERE / "ui" / "index.html").read_bytes().replace(b"__TOKEN__", token.encode())
                return self._send(200, html, "text/html; charset=utf-8")
            if self.headers.get("X-Aureon-Token") != token:
                return self._send(403, {"error": "bad token"})
            if u.path == "/api/state":
                return self._send(200, api.state())
            if u.path == "/api/wallpaper-preview" and q.get("name", [""])[0] in PRESETS:
                from .studio import generate_wallpaper
                p = PRESETS[q["name"][0]]
                out = user_dir() / "previews"
                out.mkdir(exist_ok=True)
                f = out / f"{q['name'][0].replace(' ', '-')}.png"
                if not f.exists():
                    from .studio import preset_seed
                    generate_wallpaper(p["wallpaper"], p["palette"], 480, 300, f, seed=preset_seed(q["name"][0]))
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"error": "invalid content length"})
            if n < 0 or self.headers.get("Transfer-Encoding"):
                return self._send(400, {"error": "unsupported body framing"})
            if n > 1_000_000:
                return self._send(413, {"error": "body too large"})
            # Consume bounded bodies before rejecting them, avoiding TCP resets
            # from unread POST data on Windows. Never dispatch unauthenticated input.
            self.connection.settimeout(5)
            try:
                raw = self.rfile.read(n)
            except (OSError, TimeoutError):
                return self._send(408, {"error": "body timeout"})
            if len(raw) != n:
                return self._send(400, {"error": "incomplete body"})
            if not self._ok_host() or self.headers.get("X-Aureon-Token") != token \
                    or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                return self._send(403, {"error": "forbidden"})
            try:
                body = json.loads(raw or b"{}")
                if not isinstance(body, dict):
                    return self._send(400, {"error": "body must be an object"})
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "invalid JSON"})
            try:
                code, out = api.post(urllib.parse.urlparse(self.path).path, body)
            except Exception as e:
                code, out = 500, {"error": f"{e.__class__.__name__}: {e}"}
            self._send(code, out)
    return H


def lan_ip():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sk.connect(("10.255.255.255", 1))          # no packet is sent; this just picks the LAN interface
        return sk.getsockname()[0]
    except OSError:
        return None
    finally:
        sk.close()


def serve_lan(api):
    """Read-only phone link on the local network with its own long token."""
    ip = lan_ip()
    if not ip:
        return None
    token = secrets.token_urlsafe(32)
    port_ref = [0]
    srv = ThreadingHTTPServer((ip, 0), make_handler(api, token, port_ref, extra_hosts=(ip,)))
    port_ref[0] = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return {"server": srv, "url": f"http://{ip}:{srv.server_port}/?t={token}"}


def serve(api=None, port=0):
    token = secrets.token_urlsafe(24)
    port_ref = [0]
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(api or Api(), token, port_ref))
    port_ref[0] = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    info = {"port": srv.server_port, "token": token, "pid": os.getpid()}
    (user_dir() / "agent.json").write_text(json.dumps(info), encoding="utf-8")
    return srv, info


def dashboard_url(info=None):
    info = info or json.loads((user_dir() / "agent.json").read_text(encoding="utf-8"))
    return f"http://127.0.0.1:{info['port']}/?t={info['token']}"


def open_dashboard(info=None):
    url = dashboard_url(info)
    edge = [Path(os.environ.get(v, "")) / "Microsoft/Edge/Application/msedge.exe" for v in ("PROGRAMFILES(X86)", "PROGRAMFILES")]
    edge = next((e for e in edge if e.exists()), None)
    if edge:
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1240,820"])
    else:
        os.startfile(url)


def phone_watch(api, interval=20):
    """Scan a phone automatically when it's plugged in and authorised."""
    from .phones import Android
    seen = set()
    while True:
        try:
            if Settings().load().get("phone_watch", True):
                devs = {d["serial"] for d in Android.devices()["devices"] if d["state"] == "device"}
                if devs - seen:
                    api.scan_phones()
                seen = devs
        except Exception:
            pass
        time.sleep(interval)


def memory_watch(api, keeper=None, interval=60):
    """Silent memory: fold Documents, Desktop and Pictures on the hardware budget; runs in the user's session."""
    from .memory import Keeper
    keeper = keeper or Keeper(settings=Settings().load())
    api.keeper = keeper
    while True:
        try:
            keeper.s = Settings().load()
            keeper.tick()
        except Exception as ex:                      # never let one bad pass stop the agent
            keeper._save({**keeper.status(), "error": f"{type(ex).__name__}: {ex}"})
        time.sleep(interval)


def on_ransomware(api, events):
    """The engine's tripwire fired: put back what was encrypted since just before it, then say what came back."""
    keeper = getattr(api, "keeper", None)
    for e in events:
        if e.get("kind") != "ransomware" or keeper is None:
            continue
        try:
            res = keeper.rollback(e["t"] - 1800, before=e["t"] + 1)
        except Exception as ex:
            api.uj.add("high", "ransomware", "couldn't roll files back", f"{type(ex).__name__}: {ex}")
            continue
        n = len(res["restored"])
        if n:
            api.uj.add("high", "ransomware", f"put back {n} file{'s' if n != 1 else ''} from memory",
                       "the versions from before the attack were restored, checked against their fingerprints. "
                       "encrypted copies were deleted. " + ", ".join(Path(p).name for p in res["restored"][:8]),
                       blocked=True)


def clipboard_watch(api):
    from .noah import ClipboardGuard
    def found(hits):
        what = hits[0][1].split(",")[0]
        secs = Settings().load().get("clipboard_clear_seconds", 60)
        api.uj.add("medium", "clipboard", "Your clipboard is holding something private",
                   f"{what[:140]}" + (f". It will be cleared in {secs} seconds unless you copy something else." if secs else ""))
    guard = ClipboardGuard(found, clear_after=Settings().load().get("clipboard_clear_seconds", 60))
    while True:
        try:
            if Settings().load().get("clipboard_guard", True):
                guard.tick()
        except Exception:
            pass
        time.sleep(1.5)


def run_agent(with_widget=True, open_ui=False):
    api = Api()
    srv, info = serve(api)
    try:
        from .noah import register_host
        from .notify import register
        register()
        register_host()
    except Exception:
        pass
    threading.Thread(target=clipboard_watch, args=(api,), daemon=True).start()
    followers = [Follower(api.j), Follower(api.uj)]

    def follow():
        while True:
            for f in followers:
                try:
                    on_ransomware(api, f.poll())
                except Exception:
                    pass
            time.sleep(2)
    threading.Thread(target=follow, daemon=True).start()
    threading.Thread(target=phone_watch, args=(api,), daemon=True).start()
    threading.Thread(target=memory_watch, args=(api,), name="aureon-memory", daemon=True).start()
    if api.lan_info()["enabled"]:
        ro = Api(readonly=True)
        api.lan = ro.lan = serve_lan(ro)
    if open_ui:
        open_dashboard(info)
    from .widget import main as widget_main
    if with_widget:
        widget_main()             # Tk in the main thread; rebuilds itself on config change
    else:
        while True:
            time.sleep(3600)
