"""0.5.1: engine-side scans, network guard, hidden-capture guard, automatic defaults. Runs on every OS."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aureon_defender import hwguard, netguard, sentry  # noqa: E402


class NetGuard(unittest.TestCase):
    def test_rules_added_once(self):
        calls = []

        def ps(script, timeout=60):
            calls.append(script)
            return (0, json.dumps([f"aureon guard: {n}" for n, *_ in netguard.RULES[:3]])) if "Get-NetFirewallRule" in script else (0, "")
        added = netguard.ensure_rules(ps)
        self.assertEqual(len(added), len(netguard.RULES) - 3)
        self.assertEqual(calls[1].count("New-NetFirewallRule"), len(netguard.RULES) - 3)
        self.assertIn("-Group 'aureon.defender guard'", calls[1])
        self.assertIn("-LocalPort 5985,5986 -Profile Public", calls[1])
        full = lambda script, timeout=60: (0, json.dumps([f"aureon guard: {n}" for n, *_ in netguard.RULES]))  # noqa: E731
        self.assertEqual(netguard.ensure_rules(full), [])

    def test_home_network_keeps_printers_and_nas(self):
        private = [r for r in netguard.RULES if r[4] in ("Any", "Private")]
        self.assertTrue(all(any(p in r[3] for p in ("21", "23", "5900")) for r in private))

    def test_open_wifi_is_public_and_fake_twin_is_left(self):
        actions, known = netguard.decide_wifi({"ssid": "home", "auth": "WPA2-Personal", "bssid": "aa:bb", "state": "connected"}, {})
        self.assertEqual(actions, [])
        actions, known = netguard.decide_wifi({"ssid": "home", "auth": "Open", "bssid": "de:ad", "state": "connected"}, known)
        self.assertEqual(actions, ["public", "disconnect"])
        actions, _ = netguard.decide_wifi({"ssid": "Cafe Free", "auth": "Open", "bssid": "11:22", "state": "connected"}, known)
        self.assertEqual(actions, ["public"])                   # an open network we never saw secured: public, stay
        self.assertEqual(netguard.decide_wifi({"ssid": "", "state": "disconnected"}, known)[0], [])


class CaptureGuard(unittest.TestCase):
    def test_border_and_recall_enforced_once(self):
        store = {}

        def reg(path, name, value, kind):
            if store.get((path, name)) == value:
                return False
            store[(path, name)] = value
            return True
        self.assertEqual(len(sentry.enforce_capture_guards(reg)), 2)
        self.assertEqual(store[(sentry.RECALL_KEY, "DisableAIDataAnalysis")], 1)
        self.assertEqual(store[(sentry.CAM_KEY + "\\graphicsCaptureWithoutBorder", "Value")], "Deny")
        self.assertEqual(sentry.enforce_capture_guards(reg), [])

    def test_hidden_capturers_from_access_log(self):
        log = [{"capability": "graphicsCaptureWithoutBorder", "in_use": True, "app": "C:#Users#me#AppData#spy.exe"},
               {"capability": "graphicsCaptureWithoutBorder", "in_use": False, "app": "C:#tools#old.exe"},
               {"capability": "webcam", "in_use": True, "app": "C:#cam.exe"}]
        self.assertEqual([c["exe"] for c in sentry.hidden_capturers(log)], ["C:\\Users\\me\\AppData\\spy.exe"])

    def test_engine_stops_unsigned_invisible_capturer(self):
        from aureon_defender.engine import Engine
        from aureon_defender.quarantine import Vault
        tmp = Path(tempfile.mkdtemp())
        exe = tmp / "spy.exe"
        exe.write_bytes(b"MZ spy")
        e = object.__new__(Engine)
        e.s = {"auto_quarantine": True, "auto_quarantine_suspicious": True, "trash_days": 30}
        e.state = {"counts": {"quarantined": 0}, "_capture_guard_t": time.time()}
        e.vault = Vault(tmp / "vault")
        e.scanner = mock.Mock()
        e.scanner.scan.return_value = {"verdict": "clean", "score": 0, "reasons": [], "engines": {}}
        events, killed = [], []
        e.emit = events.append
        fake = mock.Mock()
        fake.hidden_capturers.return_value = [{"exe": str(exe)}]
        with mock.patch("aureon_defender.scanner.authenticode", return_value="NotSigned"), \
             mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            e._guard_capture(fake, kill=killed.append)
        self.assertEqual(killed, [str(exe)])
        self.assertFalse(exe.exists())
        self.assertTrue(events[-1]["blocked"])


class EngineScan(unittest.TestCase):
    def test_scan_runs_in_engine_and_removes_findings(self):
        os.environ["AUREON_DATA"] = tempfile.mkdtemp()
        from aureon_defender.engine import Engine
        e = Engine()
        root = Path(tempfile.mkdtemp())
        (root / "notes.txt").write_text("hello")
        bad = root / "invoice.pdf.exe"
        bad.write_bytes(b"MZ not really")
        with mock.patch("aureon_defender.scanner.authenticode", return_value="NotSigned"), \
             mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            self.assertTrue(e.start_scan([root], kind="folder"))
            self.assertFalse(e.start_scan([root], kind="folder"))     # second request waits its turn
            self.assertEqual(len(e._scan_requests), 1)
            for _ in range(200):
                if e.jobs.snapshot()["status"] not in ("running", "cancelling") and not e._scan_requests:
                    break
                time.sleep(0.05)
        snap = e.jobs.snapshot()
        self.assertEqual(snap["status"], "completed")
        self.assertFalse(bad.exists())
        self.assertTrue((root / "notes.txt").exists())
        done = [x for x in e.j.recent(50) if x["kind"] == "scan" and "folder scan completed" in x["title"]]
        self.assertEqual(len(done), 2)                                 # the queued scan ran after the first
        self.assertTrue(any("1 removed automatically" in x["detail"] for x in done))
        self.assertIsNotNone(e._scan_snapshot())

    def test_old_settings_get_automatic_defaults_once(self):
        from aureon_defender.core import Settings
        p = Path(tempfile.mkdtemp()) / "settings.json"
        p.write_text(json.dumps({"auto_clean_downloads": False, "hid_lock": False, "realtime": True}))
        s = Settings(p)
        self.assertTrue(s.load()["auto_clean_downloads"])
        self.assertEqual(s.load()["auto_clean_mode"], "replace")
        s.save({"auto_clean_downloads": False})                       # a choice made now is kept
        self.assertFalse(Settings(p).load()["auto_clean_downloads"])


if __name__ == "__main__":
    unittest.main()
