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
from .governor import Governor, child_flags, lower_own_priority
from .monitors import NOWIN, Canary, FolderWatch, NetWatch, Persistence, vitals
from .quarantine import ProtectedPath, Vault
from .scanner import Reputation, Scanner, mpcmdrun

ROOT = Path(__file__).resolve().parent.parent.parent      # repo root (dev) - holds the `aureon` package
if (ROOT / "aureon").exists() and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def defender_status():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "Get-MpComputerStatus | Select AMRunningMode,AntivirusEnabled,RealTimeProtectionEnabled,"
                              "AntivirusSignatureAge,AntivirusSignatureVersion,IsTamperProtected,QuickScanAge | ConvertTo-Json"],
                             capture_output=True, text=True, timeout=30, creationflags=child_flags()).stdout
        return json.loads(out) if out.strip() else {}
    except Exception:
        return {}


def summarize(events):
    """Deterministic plain-English digest (no AI): counts by kind, then the most recent high/medium titles."""
    if not events:
        return "Nothing needed your attention."
    from collections import Counter
    sev = Counter(e.get("severity") for e in events)
    kinds = Counter(e.get("kind") for e in events if e.get("severity") in ("high", "medium"))
    lines = []
    if kinds:
        lines.append("Alerts by area: " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()))
    top = [e for e in events if e.get("severity") == "high"][:10] + [e for e in events if e.get("severity") == "medium"][:10]
    seen = set()
    for e in top:
        t = e.get("title", "")
        if t in seen:
            continue
        seen.add(t)
        lines.append(f"- [{e.get('severity')}] {t}")
    if not sev.get("high") and not sev.get("medium"):
        lines.append("Only routine information was recorded.")
    return "\n".join(lines)


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
            ("backups", 6 * 3600, self.purge_clean_backups, None),
            ("trash", 6 * 3600, self.t_trash, None),
            ("device_traces", 12 * 3600, self.t_device_traces, None),
            ("drain", 60, self.t_drain, None),
        ]
        self.next = {name: 0 for name, *_ in self.tasks}
        self.errors = {}                 # module name -> last error text (shown in the dashboard)
        self.alerted = {}                # alert key -> time last raised (dedupe memory, kept separate from errors)
        self.gov = Governor()
        self._removable_lock = threading.Lock()
        self._scan_queue = []
        self._scan_lock = threading.Lock()
        self._scan_thread = None

    # ---------------- reactions ----------------
    def alert_once(self, key, e, cool=0):
        last = self.alerted.get(key, 0)
        if cool and time.time() - last < cool:
            return
        if not cool and key in self.alerted:
            return
        if len(self.alerted) > 5000:                    # bounded memory for a process that runs for months
            for k, _ in sorted(self.alerted.items(), key=lambda kv: kv[1])[:1000]:
                self.alerted.pop(k, None)
        self.alerted[key] = time.time()
        self.emit(e)

    def emit(self, e):
        if not e:
            return
        if e["severity"] in ("medium", "high"):
            self.state["counts"]["alerts"] += 1
        self.j.add(**e)

    def download_cleanup_enabled(self, path):
        from .core import load_json
        # A user preference can only request clean copies of that user's downloads.
        # It grants no machine-wide access and never supplies a command or output path.
        policy = self._cleanup_policy(path)
        if type(policy.get("enabled")) is bool:
            return policy["enabled"]
        return bool(self.s.get("auto_clean_downloads"))

    def _cleanup_policy(self, path):
        from .core import load_json
        for folder in Path(path).parents:
            if folder.name.lower() == "downloads":
                return load_json(folder.parent / "AppData/Roaming/Aureon/cleanup-policy.json", {}) or {}
        return {}

    def on_file(self, path):
        r = self.scanner.scan(path)
        self.state["counts"]["scanned"] += 1
        in_downloads = any(p.name.lower() == "downloads" for p in path.parents)
        if in_downloads and r["verdict"] != "skipped" and self.s.get("scrub_download_source", True):
            from .media_strip import scrub_zone_identifier
            scrub_zone_identifier(path)
        # Only clean after the original's scan. Never auto-clean a flagged file.
        if r["verdict"] == "clean" and in_downloads and self.download_cleanup_enabled(path):
            self.auto_clean(path)

        if r["verdict"] == "malicious":
            eng = r.get("engines", {})
            confirmed = eng.get("reputation") == "bad" or eng.get("defender") == "threat" or eng.get("clamav") == "threat"
            why = "; ".join(r["reasons"])
            if confirmed and self.s.get("auto_wipe_confirmed", True):
                from .quarantine import wipe
                try:
                    w = wipe(path, r)
                    self.state["counts"]["quarantined"] += 1
                    later = w["removal"] != "removed"
                    return {"severity": "high", "kind": "threat", "blocked": True,
                            "title": f"Blocked and deleted {path.name}",
                            "detail": f"Why: {why}." + (" It was in use, so it was disabled now and will be gone after the"
                                                        " next restart." if later else " It was permanently deleted."),
                            "path": str(path), "sha256": w["sha256"]}
                except ProtectedPath as ex:
                    return {"severity": "high", "kind": "threat", "title": f"Threat in a Windows system file: {path.name}",
                            "detail": f"{why}. Not deleted automatically: {ex}", "path": str(path)}
                except (OSError, ValueError):
                    pass                                    # fall back to quarantine below
            if self.s["auto_quarantine"]:
                try:
                    m = self.vault.put(path, r)
                    self.state["counts"]["quarantined"] += 1
                    later = m.get("removal", "removed") != "removed"
                    return {"severity": "high", "kind": "threat", "blocked": True,
                            "title": f"Blocked and quarantined {path.name}",
                            "detail": "; ".join(r["reasons"]) + (" | The file is in use; it was moved aside and will be"
                                      " fully removed at the next restart." if later else ""), "path": str(path), "quarantine_id": m["id"], "sha256": r.get("sha256")}
                except ProtectedPath as ex:
                    return {"severity": "high", "kind": "threat", "title": f"Threat in a Windows system file: {path.name}",
                            "detail": f"{'; '.join(r['reasons'])}. Not moved automatically: {ex}", "path": str(path)}
                except (OSError, ValueError) as ex:
                    return {"severity": "high", "kind": "threat", "title": f"Threat found but could not be moved: {path.name}",
                            "detail": f"{'; '.join(r['reasons'])} ({ex})", "path": str(path)}
            return {"severity": "high", "kind": "threat", "title": f"Threat found: {path.name}", "detail": "; ".join(r["reasons"]),
                    "path": str(path)}
        if r["verdict"] == "suspicious":
            return {"severity": "medium", "kind": "suspicious", "title": f"Suspicious file: {path.name}",
                    "detail": "; ".join(r["reasons"]), "path": str(path), "sha256": r.get("sha256"), "score": r["score"]}
        return None

    def _downloads_root(self, path):
        return next((p for p in path.parents if p.name.lower() == "downloads"), None)

    def auto_clean(self, path):
        from .clean import REENCODE, SUPPORTED, clean_file
        ext = path.suffix.lower()
        if ext not in SUPPORTED or ".clean" in path.stem:
            return
        mode = self._cleanup_policy(path).get("mode")
        if mode not in ("copy", "replace"):
            mode = self.s.get("auto_clean_mode", "copy")
        try:
            if mode == "replace" and ext not in REENCODE:
                backup = self._backup_original(path)
                res = clean_file(path, in_place=True)
                try:                               # the cleaned file is new content: don't rescan/clean it again
                    st = path.stat()
                    self.watch.seen[str(path)] = (st.st_size, st.st_mtime)
                except (OSError, AttributeError):
                    pass
                self.j.add("info", "clean", f"Metadata removed: {path.name}",
                           "Removed: " + (", ".join(res["removed"]) or "no targeted fields found") +
                           f". Untouched original kept privately for {self.s.get('clean_backup_days', 7)} days: {backup}")
            else:
                res = clean_file(path, in_place=False)
                self.j.add("info", "clean", f"Metadata copy created: {path.name}",
                           "Original retained; selected fields only. Output: " + res["written"] + ". Removed: " +
                           (", ".join(res["removed"]) or "no targeted fields found"))
        except Exception as ex:
            self.j.add("low", "clean", f"Metadata cleanup unavailable: {path.name}", str(ex))

    def _backup_original(self, path):
        """Copy the original into the owner's own profile (never machine-wide data), expiring after N days."""
        import shutil
        root = self._downloads_root(path)
        base = (root.parent if root else Path.home()) / "AppData" / "Local" / "Aureon" / "originals"
        base.mkdir(parents=True, exist_ok=True)
        dst = base / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.urandom(3).hex()}-{path.name}"
        shutil.copy2(path, dst)
        os.utime(dst)                       # expiry counts from now, not the server's file date
        return dst

    def purge_clean_backups(self):
        days = self.s.get("clean_backup_days", 7)
        cut = time.time() - days * 86400
        from .core import expand_all
        for base in expand_all("%LOCALAPPDATA%/Aureon/originals"):
            try:
                for f in base.iterdir():
                    try:
                        if f.is_file() and f.stat().st_mtime < cut:
                            f.unlink()
                    except OSError:
                        continue
            except OSError:
                continue

    def t_trash(self):
        """Empty trash items older than trash_days, and Aureon's own quarantine copies past that age."""
        from .trash import purge_all
        days = self.s.get("trash_days", 30)
        if not days:
            return {"_module_status": "off"}
        res = purge_all(days)
        self.vault.purge_older(days)
        n = sum(res.values())
        if n:
            self.j.add("info", "cleanup", f"Emptied {n} old item{'s' if n != 1 else ''} from the trash",
                       f"Deleted more than {days} days ago. Restore points and File History are kept.")
        return None

    def t_drain(self):
        """Per-program CPU/disk use over 24 h (battery proxy). Window and voice checks run in the user's session
        (the dashboard), because this SYSTEM engine can't see the user's windows or settings."""
        from . import drain
        if not hasattr(self, "drain_meter"):
            self.drain_meter = drain.DrainMeter()
        self.drain_meter.tick()
        self.state["drain"] = {"top": self.drain_meter.top()[:15]}

    def t_device_traces(self):
        """Forget USB devices (chargers, cables, drives, phones) unplugged more than N days ago."""
        days = self.s.get("wipe_device_traces_days", 30)
        if not days or os.name != "nt":
            return {"_module_status": "off"}
        from .devices import prune
        from .devwipe import wipe_traces
        res = wipe_traces(days)
        prune(days=min(days, self.s.get("device_history_days", 365)))     # Aureon's own log follows the same rule
        if res["removed"]:
            self.j.add("info", "cleanup", f"Forgot {res['removed']} unplugged USB device{'s' if res['removed'] != 1 else ''}",
                       f"Windows' record of chargers, cables, drives and phones not connected for {days} days was removed.")
        return {"_module_status": "partial"} if res["failed"] else None

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
            self.alert_once(f"wifi:{ssid}:{detail}", {"severity": "high" if sev == "HIGH" else "medium", "kind": "wifi",
                            "title": f"WiFi impersonation risk: {ssid}", "detail": detail}, cool=24 * 3600)

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
        if not self._removable_lock.acquire(blocking=False):
            return                                      # another plug-in event is already scanning
        try:
            self._scan_removable(psutil)
        finally:
            self._removable_lock.release()

    def _scan_removable(self, psutil):
        parts = [p for p in psutil.disk_partitions(all=False) if "removable" in p.opts]
        present = {p.mountpoint for p in parts}
        # Forget drives that were unplugged, so the same letter is scanned again next time something is plugged in.
        seen = [m for m in self.state.get("removable_scanned", []) if m in present]
        self.state["removable_scanned"] = seen
        for part in parts:
            if part.mountpoint in seen:
                continue
            seen.append(part.mountpoint)
            root = Path(part.mountpoint)
            files = []
            for dirpath, dirs, names in os.walk(root):
                dirs[:] = [d for d in dirs if d not in ("System Volume Information", "$RECYCLE.BIN")]
                files += [Path(dirpath) / n for n in names]
                if len(files) >= 5000:
                    break
            found = 0
            for f in files[:5000]:
                if self.stop.is_set():
                    return
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
                             capture_output=True, text=True, timeout=60, creationflags=child_flags()).stdout
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
            def sig_update():
                try:
                    subprocess.run([str(exe), "-SignatureUpdate"], capture_output=True, timeout=600,
                                   creationflags=child_flags())
                except (OSError, subprocess.SubprocessError):
                    pass
            threading.Thread(target=sig_update, name="aureon-sigupdate", daemon=True).start()
        return {"_module_status": "partial" if any(not isinstance(v, int) for v in rep.values()) else "ok"}

    def t_report(self):
        evs = [e for e in self.j.recent(2000) if e["t"] > time.time() - 86400]
        hi = [e for e in evs if e["severity"] == "high"]
        md = [e for e in evs if e["severity"] == "medium"]
        text = (f"Last 24h: {len(hi)} high, {len(md)} medium alerts, {self.state['counts']['scanned']} files scanned, "
                f"{self.state['counts']['quarantined']} quarantined.")
        text += "\n\n" + summarize(evs)
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
            if kind == "scan" and isinstance(req.get("path"), str) and req["path"]:
                self.queue_scan(Path(req["path"]))
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

    def queue_scan(self, root: Path):
        """Requested scans run on their own worker thread so real-time sensors never wait behind them."""
        with self._scan_lock:
            if len(self._scan_queue) >= 10 or root in self._scan_queue:
                return False
            self._scan_queue.append(root)
            if self._scan_thread is None or not self._scan_thread.is_alive():
                self._scan_thread = threading.Thread(target=self._scan_worker, name="aureon-scan", daemon=True)
                self._scan_thread.start()
        return True

    def _scan_worker(self):
        while not self.stop.is_set():
            with self._scan_lock:
                if not self._scan_queue:
                    self._scan_thread = None
                    return
                root = self._scan_queue.pop(0)
            try:
                self.scan_path(root)
            except Exception as ex:
                self.j.add("low", "scan", f"Scan could not finish: {root}", f"{ex.__class__.__name__}: {ex}")

    @staticmethod
    def _iter_files(root: Path, limit):
        n = 0
        for dirpath, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
            for name in names:
                p = Path(dirpath) / name
                try:
                    if not p.is_file() or p.is_symlink():
                        continue
                except OSError:
                    continue
                yield p
                n += 1
                if n >= limit:
                    return

    def scan_path(self, root: Path, emit_clean=True, limit=20000):
        files = [root] if root.is_file() else self._iter_files(root, limit)
        found = n = 0
        for p in files:
            if self.stop.is_set():
                break
            n += 1
            e = self.on_file(p)
            if e:
                found += 1
                self.emit(e)
            if n % 200 == 0 and not self.gov.power["plugged"]:
                time.sleep(0.05)                 # yield on battery: a long scan shouldn't pin a core
        self.j.add("info", "scan", f"Scan finished: {root}", f"{n} files, {found} findings")
        return found

    # ---------------- loop ----------------
    def write_status(self):
        st = dict(self.state, heartbeat=time.time(), settings={**self.s, "abusech_key": "set" if self.s.get("abusech_key") else ""},
                  reputation=self.rep.count(),
                  feeds_age={k: self.feeds.age_hours(k) for k in feedmod.FEEDS}, quarantine=len(self.vault.list()),
                  pid=os.getpid(), errors=dict(self.errors), power=self.gov.snapshot())
        atomic_write(data_dir() / "status.json", json.dumps(st, default=str))

    SLOW = {"wifi", "persistence", "defender", "posture", "feeds", "report", "vitals", "radar", "devices", "defender_relay", "sentry", "assets",
            "leaks", "hosts", "backups", "trash", "device_traces", "drain"}

    def run_once(self, which="all"):
        now = time.time()
        if not hasattr(self, "gov"):
            self.gov = Governor()
        self.gov.sample(now)
        for name, every, fn, setting in self.tasks:
            if which == "fast" and name in self.SLOW or which == "slow" and name not in self.SLOW:
                continue
            if setting and not self.s.get(setting, True):
                self.state["modules"][name] = "off"
                continue
            if now >= self.next[name]:
                if self.next[name] and self.gov.should_defer(name, now):
                    self.next[name] = now + 60           # machine busy: look again in a minute (bounded, see governor)
                    self.state["modules"][name] = "deferred"
                    continue
                self.next[name] = now + self.gov.interval(name, every)
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
        lower_own_priority()
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
