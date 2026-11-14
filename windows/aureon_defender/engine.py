"""The 24/7 engine. Runs as SYSTEM via a scheduled task (installed) or as the current user (portable mode).

Everything here works offline. Online-only steps (feed refresh, Defender signature update) are skipped
silently when there is no connection and retried later.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import feeds as feedmod
from .core import VERSION, Journal, Settings, atomic_write, data_dir
from .monitors import NOWIN, Canary, FolderWatch, NetWatch, Persistence, vitals
from .quarantine import Vault
from .scanner import Reputation, Scanner, mpcmdrun

ROOT = Path(__file__).resolve().parent.parent.parent      # repo root (dev) - holds the `aureon` package
if (ROOT / "aureon").exists() and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def defender_status():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "Get-MpComputerStatus | Select AMRunningMode,AntivirusEnabled,RealTimeProtectionEnabled,"
                              "AntivirusSignatureAge,AntivirusSignatureVersion,IsTamperProtected,QuickScanAge | ConvertTo-Json"],
                             capture_output=True, text=True, timeout=30, creationflags=NOWIN).stdout
        return json.loads(out) if out.strip() else {}
    except Exception:
        return {}


class Engine:
    def __init__(self, journal=None, settings=None):
        self.settings_store = settings or Settings()
        self.s = self.settings_store.load()
        self.j = journal or Journal()
        self.rep = Reputation()
        self.scanner = Scanner(self.s, self.rep)
        self.vault = Vault()
        self.feeds = feedmod.Feeds()
        self.stop = threading.Event()
        self.state = {"version": VERSION, "started": time.time(), "online": None, "defender": {},
                      "vitals": {}, "counts": {"scanned": 0, "quarantined": 0, "alerts": 0}, "modules": {}}
        self.watch = FolderWatch(self.s["watch_folders"], self.on_file)
        self.persist = Persistence()
        self.net = NetWatch(bad_ips=self.feeds.bad_ips)
        self.canary = Canary(on_hit=self.on_canary)
        self.hid_trusted = None
        self.tasks = [  # (name, seconds, fn, setting)
            ("realtime", 2, self.t_realtime, "realtime"),
            ("canary", 5, self.t_canary, "canary"),
            ("hid", 2, self.t_hid, "hid_guard"),
            ("network", 15, self.t_network, "network_monitor"),
            ("vitals", 10, self.t_vitals, None),
            ("wifi", 60, self.t_wifi, "wifi_watch"),
            ("persistence", 300, self.t_persistence, "persistence_monitor"),
            ("defender", 600, self.t_defender, None),
            ("inbox", 2, self.t_inbox, None),
            ("posture", 3600, self.t_posture, None),
            ("feeds", 6 * 3600, self.t_feeds, "feeds_online"),
            ("report", 24 * 3600, self.t_report, "daily_report"),
            ("radar", 1800, self.t_radar, "radar"),
            ("devices_live", 3, self.t_devices_live, "device_history"),
            ("devices", 6 * 3600, self.t_devices, None),
            ("defender_relay", 60, self.t_defender_relay, "defender_relay"),
            ("leaks", 6 * 3600, self.t_leaks, "leak_audit"),
            ("hosts", 600, self.t_hosts, None),
            ("sentry", 45, self.t_sentry, "sentry"),
            ("assets", 600, self.t_assets, "asset_registry"),
            ("integrity", 300, self.t_integrity, None),
        ]
        self.next = {name: 0 for name, *_ in self.tasks}
        self.errors = {}

    # ---------------- reactions ----------------
    def alert_once(self, key, e, cool=0):
        last = self.errors.get(key, 0)
        if cool and time.time() - last < cool:
            return
        if not cool and key in self.errors:
            return
        self.errors[key] = time.time()
        self.emit(e)

    def emit(self, e):
        if not e:
            return
        if e["severity"] in ("medium", "high"):
            self.state["counts"]["alerts"] += 1
        self.j.add(**e)

    def on_file(self, path):
        if self.s.get("auto_clean_downloads") and path.parent.name.lower() == "downloads":
            from .clean import SUPPORTED, clean_file
            if path.suffix.lower() in SUPPORTED:
                try:
                    res = clean_file(path, in_place=True)
                    if res["removed"]:
                        self.j.add("info", "clean", f"Cleaned {path.name}", "Removed: " + ", ".join(res["removed"]))
                except Exception:
                    pass
        r = self.scanner.scan(path)
        self.state["counts"]["scanned"] += 1
        if r["verdict"] == "malicious":
            if self.s["auto_quarantine"]:
                try:
                    m = self.vault.put(path, r)
                    self.state["counts"]["quarantined"] += 1
                    return {"severity": "high", "kind": "threat", "title": f"Blocked and quarantined {path.name}",
                            "detail": "; ".join(r["reasons"]), "path": str(path), "quarantine_id": m["id"], "sha256": r.get("sha256")}
                except OSError as ex:
                    return {"severity": "high", "kind": "threat", "title": f"Threat found but could not be moved: {path.name}",
                            "detail": f"{'; '.join(r['reasons'])} ({ex})", "path": str(path)}
            return {"severity": "high", "kind": "threat", "title": f"Threat found: {path.name}", "detail": "; ".join(r["reasons"]),
                    "path": str(path)}
        if r["verdict"] == "suspicious":
            return {"severity": "medium", "kind": "suspicious", "title": f"Suspicious file: {path.name}",
                    "detail": "; ".join(r["reasons"]), "path": str(path), "sha256": r.get("sha256"), "score": r["score"]}
        return None

    def on_canary(self, e):
        if not self.s["canary_suspend_writer"]:
            return
        import psutil
        from .scanner import authenticode
        for pid, name, exe in e.get("writers", []):
            try:
                if exe and authenticode(Path(exe)) != "Valid" and pid != os.getpid():
                    psutil.Process(pid).suspend()
                    self.j.add("high", "ransomware", f"Suspended {name} (pid {pid})",
                               "Unsigned program writing heavily while the tripwire fired. Resume or kill it from Task Manager.")
                    return
            except Exception:
                continue

    # ---------------- tasks ----------------
    def t_realtime(self):
        for e in self.watch.tick():
            self.emit(e)

    def t_canary(self):
        for e in self.canary.tick():
            self.emit(e)

    def t_hid(self):
        from .monitors import keyboards_fast
        now = keyboards_fast()
        if self.hid_trusted is None:
            self.hid_trusted = dict(now)
            return
        for ident, name in now.items():
            if ident not in self.hid_trusted:
                self.hid_trusted[ident] = name
                self.emit({"severity": "high" if self.s["hid_lock"] else "medium", "kind": "usb",
                           "title": f"New keyboard device connected: {name}",
                           "detail": "If you didn't just plug in a keyboard, unplug it: USB sticks can pretend to be keyboards and type commands.",
                           "lock": self.s["hid_lock"]})

    def t_network(self):
        for e in self.net.tick():
            self.emit(e)

    def t_vitals(self):
        self.state["vitals"] = vitals()

    def t_wifi(self):
        try:
            from aureon import rfwatch
        except ImportError:
            return
        base = rfwatch._load("wifi_baseline.json")
        nets = rfwatch.scan_wifi()
        if not base:
            rfwatch._save("wifi_baseline.json", rfwatch.wifi_learn(nets, {}))
            return
        for sev, ssid, detail in rfwatch.wifi_check(nets, base):
            key = f"wifi:{ssid}:{detail}"
            if key not in self.errors:
                self.errors[key] = time.time()
                self.emit({"severity": "high" if sev == "HIGH" else "medium", "kind": "wifi",
                           "title": f"WiFi impersonation risk: {ssid}", "detail": detail})

    def t_persistence(self):
        for e in self.persist.tick():
            t = e.get("target")
            if t:
                exe = t.strip('"').split('"')[0].split(" -")[0].split(" /")[0]
                if exe.lower().endswith(".exe") and Path(exe).exists():
                    r = self.scanner.scan(exe)
                    if r["verdict"] != "clean":
                        e["severity"] = "high"
                        e["detail"] += f" | scanner: {r['verdict']} ({'; '.join(r['reasons'])})"
            self.emit(e)

    def t_devices_live(self):
        from .devices import LiveDevices, is_tracker
        if not hasattr(self, "live_devices"):
            self.live_devices = LiveDevices()
        for e in self.live_devices.tick():
            loud = e["category"] in ("Storage", "Phone / media device", "Phone (Android)") or is_tracker(e["name"])
            sev = "medium" if is_tracker(e["name"]) else "low" if loud else "info"
            verb = "connected" if e["kind"] == "connected" else "disconnected"
            self.emit({"severity": sev, "kind": "device", "title": f"{e['name']} {verb}", "detail": f"{e['category']} · {e['id']}"})
            if e["kind"] == "connected":
                self.check_plugged(e)
            if e["kind"] == "connected" and e["category"] in ("Storage", "Phone / media device") and self.s.get("scan_removable", True):
                threading.Thread(target=self.scan_removable, daemon=True).start()

    def check_plugged(self, e):
        """A device was plugged in: say what it can do, loudly if it can type or see network traffic."""
        from .controls import bt_check, plugged_devices
        try:
            for dev in plugged_devices():
                if dev["level"] == "high" and dev["name"] not in self.state.setdefault("plugged_warned", []):
                    self.state["plugged_warned"].append(dev["name"])
                    self.emit({"severity": "high", "kind": "device", "title": f"{dev['name']} can do more than it looks like",
                               "detail": " ".join(dev["capabilities"].values())})
            if "Bluetooth" in e["category"]:
                from .devices import describe, present_ids
                names = sorted({describe(i)["name"] for i in present_ids() if i.upper().startswith(("BTHENUM\\", "BTHLE\\DEV_"))})
                for msg in bt_check(names, self.s.get("bt_limit", 4), self.s.get("bt_allowed", [])):
                    self.emit({"severity": "medium", "kind": "device", "title": "Bluetooth limit", "detail": msg})
        except Exception:
            pass

    def scan_removable(self):
        """A USB drive or SD card was plugged in: scan what's on it before anything gets opened (CIRCLean idea)."""
        import psutil
        time.sleep(3)                                   # let Windows mount it
        seen = self.state.setdefault("removable_scanned", [])
        for part in psutil.disk_partitions(all=False):
            if "removable" not in part.opts or part.mountpoint in seen:
                continue
            seen.append(part.mountpoint)
            root = Path(part.mountpoint)
            files = []
            for dirpath, _dirs, names in os.walk(root):
                files += [Path(dirpath) / n for n in names]
                if len(files) > 5000:
                    break
            found = 0
            for f in files[:5000]:
                ev = self.on_file(f)
                if ev:
                    found += 1
                    self.emit(ev)
            self.emit({"severity": "medium" if found else "info", "kind": "device",
                       "title": f"Scanned the drive in {part.mountpoint}: {len(files[:5000])} files, {found} finding{'s' if found != 1 else ''}",
                       "detail": "Autorun is ignored; nothing on the drive was opened."})

    def t_devices(self):
        from .devices import prune, sweep
        before = {r["id"] for r in (self.state.get("trackers_seen") or [])}
        snap = sweep()
        prune(days=self.s["device_history_days"])
        self.state["devices"] = {"known": len(snap["devices"]), "present": len(snap["present"])}
        for r in snap["trackers"]:
            if r["id"] not in before:
                self.emit({"severity": "medium", "kind": "device", "title": f"Tracking tag in this PC's Bluetooth history: {r['name']}",
                           "detail": "Tile/AirTag-style tags can follow a person. If you don't own it, check who does."})
        self.state["trackers_seen"] = snap["trackers"]

    def t_defender_relay(self):
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "Get-MpThreatDetection | Select DetectionID,ThreatID,InitialDetectionTime,ActionSuccess,"
                              "@{n='R';e={$_.Resources -join '; '}},@{n='N';e={(Get-MpThreat -ThreatID $_.ThreatID).ThreatName}} | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=60, creationflags=NOWIN).stdout
        rows = json.loads(out) if out.strip() else []
        rows = rows if isinstance(rows, list) else [rows]
        seen = set(self.state.get("defender_seen") or [])
        first = not seen and not self.state.get("defender_relay_primed")
        for r in rows:
            did = r.get("DetectionID")
            if not did or did in seen:
                continue
            seen.add(did)
            if first:
                continue                     # don't replay old detections on the first run
            name = r.get("N") or f"threat {r.get('ThreatID')}"
            self.emit({"severity": "high", "kind": "defender",
                       "title": f"{'Blocked' if r.get('ActionSuccess') else 'Found'} {name}",
                       "detail": f"Microsoft Defender engine · {(r.get('R') or '').replace('file:_', '')[:300]}"})
        self.state["defender_seen"] = sorted(seen)
        self.state["defender_relay_primed"] = True

    def t_leaks(self):
        from .leaks import audit, security_products
        res = audit()
        prods = security_products()
        atomic_write(data_dir() / "leaks.json", json.dumps({"t": time.time(), "checks": res, "products": prods}))
        self.state["leaks"] = sum(not r["ok"] for r in res)

    def t_hosts(self):
        """DNS shield: URLhaus malware domains and, if chosen, noah.shield's tracker list - one hosts block."""
        want = []
        if self.s["dns_shield_hosts"]:
            want += self.feeds.bad_hosts()
        if self.s["block_trackers"]:
            from .noah import rule_domains
            want += rule_domains()
        want = sorted(set(want))
        sig = hash(tuple(want))
        if sig == self.state.get("hosts_sig"):
            return
        try:
            feedmod.apply_hosts(want)
            self.state["hosts_sig"] = sig
            if want:
                self.j.add("info", "update", f"DNS shield: {len(want)} domains blocked system-wide")
        except OSError as ex:
            self.errors["hosts"] = f"needs the installed engine: {ex}"

    def t_sentry(self):
        """Microphone / camera / hidden-capture watch. Reminds you while the mic stays on."""
        from . import sentry
        snap = sentry.collect()
        self.state["sentry"] = snap
        mic = snap["mic"]
        if mic.get("listening_while_off"):
            self.alert_once("sentry:mic-off", {"severity": "high", "kind": "sentry",
                "title": "Something is using the microphone while it's turned off",
                "detail": "Using it now: " + ", ".join(u["app"] for u in mic["using"]) + ". This shouldn't be possible with mic access off."})
        elif mic.get("on"):
            # a fresh reminder every ~5 minutes while the mic stays live
            last = self.state.setdefault("_mic_reminded", 0)
            if time.time() - last > 300:
                self.state["_mic_reminded"] = time.time()
                names = ", ".join(u["app"] for u in mic["using"]) or "an app"
                self.emit({"severity": "medium", "kind": "sentry", "title": "Your microphone is on",
                           "detail": f"{names} is listening right now. If you didn't start it, close it or turn the mic off."})
        else:
            self.state["_mic_reminded"] = 0
        cam = snap["camera"]
        if cam.get("on"):
            self.alert_once("sentry:cam", {"severity": "medium", "kind": "sentry", "title": "Your camera is on",
                "detail": ", ".join(u["app"] for u in cam["using"]) + " is using the camera."}, cool=300)
        scr = snap["screen"]
        for c in scr.get("capturers", []):
            self.alert_once("sentry:cap:" + c["process"], {"severity": "high", "kind": "sentry",
                "title": "Your screen is being captured",
                "detail": c["what"] + " is recording or streaming your screen right now."}, cool=600)
        if scr.get("recall_on"):
            self.alert_once("sentry:recall", {"severity": "high", "kind": "sentry",
                "title": "Windows Recall is taking snapshots of your screen",
                "detail": "Recall saves a picture of everything you do every few seconds. Turn it off in Protect your PC."}, cool=3600)

    def t_assets(self):
        """Roll-call of devices on your network and paired to this PC; alerts on a stranger."""
        from . import assets
        try:
            r = assets.scan()
        except Exception:
            return
        self.state["assets"] = {"present": r["present"], "total": r["total"]}
        for rec in r["new"]:
            if rec.get("trusted"):
                continue
            self.emit({"severity": "medium", "kind": "asset",
                       "title": f"New {rec['kind']} on your network: {rec.get('name') or rec.get('mac') or 'unknown device'}",
                       "detail": "First time this device has been seen. If it's yours, mark it trusted in Devices; if not, it's sharing your network."})

    def t_radar(self):
        from .radar import Radar
        for e in Radar().tick():
            self.emit(e)

    def t_defender(self):
        self.state["defender"] = defender_status()

    def t_integrity(self):
        from .integrity import check
        result = check()
        self.state['integrity'] = result
        if result['status'] in ('changed', 'collection_failed'):
            self.alert_once('integrity:' + json.dumps(result, sort_keys=True),
                {'severity':'medium', 'kind':'integrity', 'title':'Aureon resource integrity needs review',
                 'detail':json.dumps(result)[:1200]}, cool=3600)

    def t_posture(self):
        try:
            from aureon.audit import run_audit
            rep = run_audit()
            self.state["posture"] = rep
            for r in rep["results"]:
                if r["status"] == "FAIL":
                    self.emit({"severity": "medium", "kind": "posture", "title": f"Weak setting: {r['check']}", "detail": r["detail"]})
        except Exception as ex:
            self.state["posture"] = {"error": str(ex)}

    def t_feeds(self):
        on = feedmod.online()
        self.state["online"] = on
        if not on:
            return {"_module_status": "offline_cached"}
        rep = self.feeds.update(self.rep, key=self.s.get("abusech_key", ""))
        self.state["feeds"] = rep
        self.j.add("info", "update", "Threat feeds updated", ", ".join(f"{k}: {v}" for k, v in rep.items()))
        self.next["hosts"] = 0                    # fresh lists -> refresh the DNS shield
        exe = mpcmdrun()
        if exe:
            subprocess.run([str(exe), "-SignatureUpdate"], capture_output=True, timeout=600, creationflags=NOWIN)
        return {"_module_status": "partial" if any(not isinstance(v, int) for v in rep.values()) else "ok"}

    def t_report(self):
        evs = [e for e in self.j.recent(2000) if e["t"] > time.time() - 86400]
        hi = [e for e in evs if e["severity"] == "high"]
        md = [e for e in evs if e["severity"] == "medium"]
        text = (f"Last 24h: {len(hi)} high, {len(md)} medium alerts, {self.state['counts']['scanned']} files scanned, "
                f"{self.state['counts']['quarantined']} quarantined.")
        try:
            from aureon.analyst import llm
            digest = "\n".join(f"- [{e['severity']}] {e['title']}: {e['detail']}" for e in (hi + md)[:40]) or "no alerts"
            if hi or md:
                text += "\n\n" + llm(digest)
        except Exception:
            pass
        (data_dir() / "report.md").write_text(f"# Aureon daily report\n\n{text}\n", encoding="utf-8")
        self.j.add("info", "report", "Daily security report ready", text[:400])

    def t_inbox(self):
        box = data_dir() / "inbox"
        box.mkdir(exist_ok=True)
        for p in sorted(box.glob("*.json"))[:20]:
            try:
                req = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                req = {}
            p.unlink(missing_ok=True)
            kind = req.get("type")
            if kind == "scan" and req.get("path"):
                self.scan_path(Path(req["path"]))
            elif kind == "update_feeds":
                self.next["feeds"] = 0
            elif kind == "posture":
                self.next["posture"] = 0
            elif kind == "report":
                self.next["report"] = 0
            elif kind == "radar":
                self.next["radar"] = 0
            elif kind == "devices":
                self.next["devices"] = 0
            elif kind == "leaks":
                self.next["leaks"] = 0
            elif kind == "reload":
                self.s = self.settings_store.load()
                self.scanner = Scanner(self.s, self.rep)
                self.next["hosts"] = 0
            # anything else is ignored: the inbox is writable by normal users, so it only takes harmless requests

    def scan_path(self, root: Path, emit_clean=True):
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()][:20000]
        found = 0
        for p in files:
            e = self.on_file(p)
            if e:
                found += 1
                self.emit(e)
        self.j.add("info", "scan", f"Scan finished: {root}", f"{len(files)} files, {found} findings")
        return found

    # ---------------- loop ----------------
    def write_status(self):
        st = dict(self.state, heartbeat=time.time(), settings={**self.s, "abusech_key": "set" if self.s.get("abusech_key") else ""},
                  reputation=self.rep.count(),
                  feeds_age={k: self.feeds.age_hours(k) for k in feedmod.FEEDS}, quarantine=len(self.vault.list()),
                  pid=os.getpid(), errors={k: v for k, v in self.errors.items() if not k.startswith("wifi:")})
        atomic_write(data_dir() / "status.json", json.dumps(st, default=str))

    SLOW = {"wifi", "persistence", "defender", "posture", "feeds", "report", "vitals", "radar", "devices", "defender_relay", "sentry", "assets",
            "leaks", "hosts"}

    def run_once(self, which="all"):
        now = time.time()
        for name, every, fn, setting in self.tasks:
            if which == "fast" and name in self.SLOW or which == "slow" and name not in self.SLOW:
                continue
            if setting and not self.s.get(setting, True):
                self.state["modules"][name] = "off"
                continue
            if now >= self.next[name]:
                self.next[name] = now + every
                try:
                    result = fn()
                    self.state["modules"][name] = result.get("_module_status", "ok") if isinstance(result, dict) else "ok"
                    self.errors.pop(name, None)
                except Exception as ex:
                    self.state["modules"][name] = "error"
                    if name not in self.errors:
                        self.j.add("low", "engine", f"{name} module error", f"{ex.__class__.__name__}: {ex}")
                    self.errors[name] = f"{ex.__class__.__name__}: {ex}"
        if which != "slow":
            self.write_status()

    def run(self):
        """Fast sensors (real-time, canary, USB, network) never wait behind slow checks."""
        self.j.add("info", "engine", f"Aureon engine {VERSION} started", f"pid {os.getpid()}, data {data_dir()}")

        def slow():
            while not self.stop.is_set():
                try:
                    self.run_once("slow")
                except Exception as ex:          # never let one bad cycle stop protection
                    self.errors["slow-loop"] = repr(ex)
                self.stop.wait(5.0)
        threading.Thread(target=slow, name="aureon-slow", daemon=True).start()
        while not self.stop.is_set():
            try:
                self.run_once("fast")
            except Exception as ex:
                self.errors["fast-loop"] = repr(ex)
            self.stop.wait(1.0)
