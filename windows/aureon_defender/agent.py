"""User-session agent: dashboard server, toast alerts, screen lock on USB alerts, desktop widget.

The engine may run as SYSTEM (installed) and can't show toasts or lock your session, so this small
process does those for it by following the event journal.

Dashboard security: bound to 127.0.0.1 only, random per-run token required on every API call,
Host header pinned (stops DNS-rebinding), JSON-only POSTs (stops cross-site form posts).
"""
import ctypes
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import VERSION, Journal, Settings, atomic_write, data_dir, user_dir
from .quarantine import Vault
from .studio import PRESETS, Studio, WIDGET_DEFAULT
from .winmap import WINMAP

HERE = Path(__file__).resolve().parent
NOWIN = 0x08000000


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
    """Tails the journal; toasts medium/high events; locks on USB alerts that ask for it."""
    def __init__(self, journal, notify=toast, lock=lock_workstation):
        self.j, self.notify, self.lock = journal, notify, lock
        self.seen = {e["id"] for e in journal.recent(500)}

    def poll(self):
        fresh = [e for e in reversed(self.j.recent(100)) if e["id"] not in self.seen]
        for e in fresh:
            self.seen.add(e["id"])
            if e.get("lock"):
                self.lock()
            if e["severity"] in ("medium", "high"):
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
LAN_ALLOWED = {"/api/scan", "/api/phones/scan", "/api/radar"}


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
        return {"version": VERSION, "engine": {"alive": alive, **st}, "events": events,
                "radar": load_json(data_dir() / "radar.json"), "phones": load_json(user_dir() / "phones.json"),
                "phone_link": self.lan_info(), "readonly": self.readonly,
                "quarantine": self.vault.list(), "studio": self.studio.current(), "presets": {k: {"mode": v["mode"], "accent": v["accent"],
                "palette": v["palette"], "font": v["widget"]["font"]} for k, v in PRESETS.items()},
                "widget": self.widget_cfg(), "settings": self.settings.load(), "winmap": caps}

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
        if path == "/api/phones/scan":
            threading.Thread(target=self.scan_phones, daemon=True).start()
            return 200, {"ok": True, "message": "Scanning connected phones. Results appear in about 20 seconds."}
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
                return 200, {"ok": True, "message": "Scan queued with the engine; results appear in Activity."}
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
            return 200, s.apply_preset(body["name"])
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
                f = out / f"{q['name'][0]}.png"
                if not f.exists():
                    generate_wallpaper(p["wallpaper"], p["palette"], 480, 270, f)
                return self._send(200, f.read_bytes(), "image/png")
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._ok_host() or self.headers.get("X-Aureon-Token") != token \
                    or not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._send(403, {"error": "forbidden"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
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


def run_agent(with_widget=True, open_ui=False):
    api = Api()
    srv, info = serve(api)
    followers = [Follower(api.j), Follower(api.uj)]

    def follow():
        while True:
            for f in followers:
                try:
                    f.poll()
                except Exception:
                    pass
            time.sleep(2)
    threading.Thread(target=follow, daemon=True).start()
    threading.Thread(target=phone_watch, args=(api,), daemon=True).start()
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
