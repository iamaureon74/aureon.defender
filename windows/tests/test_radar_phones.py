"""Radar, phones, phone link, resilience. Fake data only; one optional live check runs if a phone is plugged in."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

WIN = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(WIN), str(WIN.parent)]
TMP = Path(tempfile.mkdtemp(prefix="aureon-rp-"))
os.environ.setdefault("AUREON_DATA", str(TMP / "data"))
os.environ.setdefault("AUREON_USER", str(TMP / "user"))

from aureon_defender import agent, core, phones, radar, studio  # noqa: E402


def fake_sources(**over):
    s = {"privacy": [], "recall": {"verdict": "blocked"}, "extensions": [], "watchers": [],
         "installed": [{"name": "Proton VPN", "company": "Proton", "version": "5", "installed": "", "hidden": False, "where": "HKLM", "location": ""}],
         "background": [{"kind": "service", "name": "DiagTrack", "target": "svchost", "company": "Microsoft", "telemetry": True, "note": ""}]}
    s.update(over)
    return s


class RadarTest(unittest.TestCase):
    def test_company_normalisation(self):
        self.assertEqual(radar.normalize_company("ASUSTeK COMPUTER INC."), "ASUS")
        self.assertEqual(radar.normalize_company("NVIDIA Corporation"), "NVIDIA")
        self.assertEqual(radar.normalize_company("Acme Widgets, Inc."), "Acme Widgets")
        self.assertEqual(radar.normalize_company(""), "Unknown publisher")

    def test_company_from_real_signed_file(self):
        exe = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "notepad.exe"
        if not exe.exists():
            self.skipTest("no notepad")
        self.assertEqual(radar.company_of(str(exe)), "Microsoft")

    def test_sweep_groups_by_company(self):
        r = radar.sweep(fake_sources())
        self.assertEqual(r["companies"]["Microsoft"]["telemetry"], 1)
        self.assertEqual(r["companies"]["Proton"]["programs"], 1)

    def test_diff_logs_new_hidden_software_extensions_and_screen_capture(self):
        old = radar.sweep(fake_sources())
        new = radar.sweep(fake_sources(
            installed=old["installed"] + [{"name": "Vendor Agent", "company": "OEM", "version": "1", "installed": "", "hidden": True, "where": "HKLM", "location": "C:\\x"}],
            background=old["background"] + [{"kind": "scheduled task", "name": "\\OEM\\Collect", "target": "c:\\oem\\c.exe", "company": "OEM", "telemetry": True, "note": ""}],
            extensions=[{"browser": "Chrome", "id": "abc", "name": "Screen Grabber", "version": "1", "broad": ["desktopCapture", "<all_urls>"], "profile": "Default"}],
            privacy=[{"capability": "graphicsCaptureWithoutBorder", "what": "screen capture (no yellow border)", "app": "C:\\x\\spy.exe",
                      "last_start": time.time() - 60, "last_stop": None, "in_use": True, "user": "you"}],
            watchers=[{"product": "Teramind", "where": "running process", "evidence": "tmagent.exe"}]))
        ev = radar.diff_events(old, new)
        titles = [e["title"] for e in ev]
        self.assertIn("Hidden program from OEM: Vendor Agent", titles)
        self.assertIn("New background scheduled task from OEM: \\OEM\\Collect", titles)
        self.assertIn("New Chrome extension: Screen Grabber", titles)
        self.assertIn("spy.exe used your screen capture (no yellow border)", titles)
        self.assertIn("Monitoring software found: Teramind", titles)
        sev = {e["title"]: e["severity"] for e in ev}
        self.assertEqual(sev["Monitoring software found: Teramind"], "high")
        self.assertEqual(radar.diff_events(new, new), [])

    def test_watchers_match_products(self):
        hits = radar.watchers([{"name": "ActivTrak Agent", "company": "x", "hidden": False}], [])
        self.assertEqual([h["product"] for h in hits], ["ActivTrak"])

    def test_radar_tick_writes_and_baselines(self):
        r = radar.Radar(TMP / "radar.json", sources=fake_sources())
        self.assertEqual(r.tick()[0]["title"], "Hidden-software radar baseline recorded")
        self.assertEqual(r.tick(), [])

    def test_live_privacy_log_shape(self):
        rows = radar.privacy_log()
        for row in rows[:5]:
            self.assertIn(row["capability"], radar.WATCH_CAPS)
            self.assertIsInstance(row["last_start"], float)


ANDROID = {
    "pm list packages -f -i -u": "package:/system/app/A/A.apk=com.google.android.gms  installer=null\n"
                                 "package:/data/app/x/base.apk=com.example.notes  installer=com.android.vending\n"
                                 "package:/data/app/y/base.apk=com.hidden.monitor  installer=null\n"
                                 "package:/system/priv-app/V/V.apk=com.verizon.mips.services  installer=null\n"
                                 "package:/data/app/z/base.apk=com.gone.app  installer=com.android.vending\n",
    "pm list packages -s": "package:com.google.android.gms\npackage:com.verizon.mips.services\n",
    "pm list packages -d": "",
    "pm list packages": "package:com.google.android.gms\npackage:com.example.notes\npackage:com.hidden.monitor\npackage:com.verizon.mips.services\n",
    "cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER": "  com.example.notes/.Main\n",
    "dumpsys device_policy": "Admin: ComponentInfo{com.hidden.monitor/com.hidden.monitor.Admin}\n",
    "settings get secure enabled_accessibility_services": "com.hidden.monitor/com.hidden.monitor.Acc\n",
    "settings get secure enabled_notification_listeners": "null\n",
    "getprop": "[ro.product.brand]: [google]\n[ro.product.model]: [Pixel 9]\n[ro.build.version.release]: [17]\n"
               "[ro.build.version.security_patch]: [2026-10-05]\n[ro.boot.verifiedbootstate]: [green]\n",
    "cmd appops get com.hidden.monitor": "CAMERA: allow; time=+12m3s200ms ago\nRECORD_AUDIO: allow; time=+3h2m1s9ms ago\nPROJECT_MEDIA: allow; time=+40d1h2m3s4ms ago\n",
}


class AndroidTest(unittest.TestCase):
    def scan(self):
        return phones.Android(run=lambda c: ANDROID.get(c, "")).scan()

    def test_hidden_stalkerware_pattern_is_high(self):
        r = self.scan()
        apps = {a["package"]: a for a in r["apps"]}
        mon = apps["com.hidden.monitor"]
        self.assertTrue(mon["hidden_icon"] and mon["sideloaded"] and mon["device_admin"] and mon["accessibility"])
        self.assertEqual(mon["risk"], "high")
        self.assertEqual([o["ago"] for o in mon["recent"]], ["12m3s", "3h2m", "40d"])
        self.assertEqual(r["apps"][0]["package"], "com.hidden.monitor")          # highest risk first

    def test_preloads_leftovers_and_companies(self):
        r = self.scan()
        apps = {a["package"]: a for a in r["apps"]}
        self.assertIn("carrier analytics", apps["com.verizon.mips.services"]["flags"][0])
        self.assertEqual(apps["com.verizon.mips.services"]["company"], "Verizon")
        self.assertTrue(apps["com.gone.app"]["leftover"])
        self.assertFalse(apps["com.example.notes"]["hidden_icon"])
        self.assertEqual(apps["com.example.notes"]["risk"], "none")
        self.assertEqual(r["device"]["model"], "Pixel 9")
        self.assertTrue(r["device"]["bootloader_locked"])
        self.assertEqual(r["summary"]["hidden_icon"], 1)

    def test_company_prefixes(self):
        self.assertEqual(phones.company("com.facebook.appmanager"), "Meta")
        self.assertEqual(phones.company("com.samsung.android.x"), "Samsung")
        self.assertEqual(phones.company("com.acme.thing"), "Acme")

    def test_phone_events_first_and_new(self):
        r = self.scan()
        new = {"android": [dict(r, serial="S1")]}
        ev = agent.phone_events(None, new)
        self.assertIn("Pixel 9: first scan", ev[0]["title"])
        self.assertTrue(any(e["severity"] == "high" and "com.hidden.monitor" in e["title"] for e in ev))
        r2 = json.loads(json.dumps(r))
        r2["apps"].append({**r2["apps"][-1], "package": "com.new.thing", "system": False, "risk": "none", "flags": []})
        ev2 = agent.phone_events(new, {"android": [dict(r2, serial="S1")]})
        self.assertEqual([e["title"] for e in ev2], ["Google Pixel 9: new app com.new.thing (" + r2["apps"][-1]["company"] + ")"])

    def test_live_connected_phone(self):
        devs = phones.Android.devices()["devices"] if phones.find_adb() else []
        ready = [d for d in devs if d["state"] == "device"]
        if not ready:
            self.skipTest("no authorised Android phone connected")
        r = phones.Android(ready[0]["serial"]).scan()
        self.assertGreater(r["summary"]["total"], 50)
        self.assertTrue(r["device"]["model"])


class IPhoneTest(unittest.TestCase):
    def test_missing_tools_explains(self):
        if phones.IPhone.tools()["ideviceinfo"]:
            self.skipTest("libimobiledevice present")
        self.assertIn("libimobiledevice", phones.IPhone().scan()["error"])


class PhoneLinkAndResilience(unittest.TestCase):
    def test_readonly_api_blocks_changes(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        api = agent.Api(studio=studio.Studio(reg=studio.MemReg(), backup=d / "b.json", apply_wallpaper=lambda p: None, live=False),
                        journal=core.Journal(d / "e.jsonl"), ujournal=core.Journal(d / "u.jsonl"), settings=core.Settings(d / "s.json"),
                        readonly=True, elevate=lambda a: False)
        for path in ("/api/settings", "/api/studio/preset", "/api/quarantine/delete", "/api/phone-link", "/api/widget"):
            self.assertEqual(api.post(path, {})[0], 403, path)
        self.assertEqual(api.post("/api/scan", {"path": str(d / "none")})[0], 400)    # allowed endpoint, validated

    def test_lan_server_requires_its_own_token(self):
        import urllib.request
        ip = agent.lan_ip()
        if not ip:
            self.skipTest("no LAN")
        d = Path(tempfile.mkdtemp(dir=TMP))
        api = agent.Api(studio=studio.Studio(reg=studio.MemReg(), backup=d / "b.json", apply_wallpaper=lambda p: None, live=False),
                        journal=core.Journal(d / "e.jsonl"), ujournal=core.Journal(d / "u.jsonl"), readonly=True, elevate=lambda a: False)
        lan = agent.serve_lan(api)
        try:
            base, token = lan["url"].split("/?t=")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + "/api/state", timeout=10)
            req = urllib.request.Request(base + "/api/state", headers={"X-Aureon-Token": token})
            st = json.loads(urllib.request.urlopen(req, timeout=30).read())
            self.assertTrue(st["readonly"])
        finally:
            lan["server"].shutdown()

    def test_atomic_write_survives_open_reader(self):
        p = TMP / "status.json"
        p.write_text("{}")
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                try:
                    with open(p) as f:
                        f.read()
                except OSError:
                    pass
                # Let the writer acquire the file between reader iterations.
                # An uninterrupted Windows reader can exhaust every retry.
                stop.wait(0.002)
        t = threading.Thread(target=reader, daemon=True)
        t.start()
        try:
            for i in range(200):
                core.atomic_write(p, json.dumps({"i": i}))       # must never raise
        finally:
            stop.set()
            t.join()
        self.assertEqual(json.loads(p.read_text())["i"], 199)

    def test_ember_preset_is_users_palette(self):
        e = studio.PRESETS["Ember"]
        self.assertEqual(e["palette"], ["#060608", "#141012", "#c9803f", "#ffd9b0"])
        self.assertEqual(e["widget"]["hours"], 12)
        self.assertEqual(list(studio.PRESETS)[0], "Ember")


if __name__ == "__main__":
    unittest.main()
