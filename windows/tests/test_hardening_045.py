"""0.4.5 hardening: safe quarantine, governor, engine scheduling, no-AI report."""
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_TMP = tempfile.mkdtemp()
os.environ.setdefault("AUREON_DATA", _TMP)
os.environ.setdefault("AUREON_USER", _TMP)

from aureon_defender import quarantine as q  # noqa: E402
from aureon_defender.governor import Governor  # noqa: E402


class QuarantineSafety(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.v = q.Vault(self.d / "vault")

    def test_fast_xor_matches_reference_and_roundtrips(self):
        data = os.urandom(3 * (1 << 20) + 77)
        ref = bytes(b ^ q.KEY[n % 64] for n, b in enumerate(data[:5000]))
        self.assertEqual(q._xor_bytes(data[:5000]), ref)
        self.assertEqual(q._xor_bytes(q._xor_bytes(data[10:999], 10), 10), data[10:999])
        f = self.d / "evil.exe"
        f.write_bytes(data)
        h = hashlib.sha256(data).hexdigest()
        m = self.v.put(f, {"sha256": h, "reasons": ["test"], "verdict": "malicious"})
        self.assertFalse(f.exists())
        self.assertEqual(m["removal"], "removed")
        out = self.v.restore(m["id"])
        self.assertEqual(hashlib.sha256(Path(out).read_bytes()).hexdigest(), h)

    def test_changed_file_is_not_removed(self):
        f = self.d / "a.exe"
        f.write_bytes(b"MZ new content")
        with self.assertRaises(ValueError):
            self.v.put(f, {"sha256": "0" * 64})
        self.assertTrue(f.exists())
        self.assertEqual(list((self.d / "vault").glob("*")), [])

    def test_failed_copy_keeps_original(self):
        f = self.d / "b.exe"
        f.write_bytes(b"MZ" * 100)
        with mock.patch.object(q, "_unscrambled_sha256", return_value="bad"):
            with self.assertRaises(OSError):
                self.v.put(f, {})
        self.assertTrue(f.exists())

    def test_protected_system_paths_are_never_moved(self):
        with mock.patch.dict(os.environ, {"AUREON_PROTECT_TEST": "1", "SYSTEMROOT": str(self.d / "Windows")}):
            sysf = self.d / "Windows" / "System32" / "evil.dll"
            sysf.parent.mkdir(parents=True)
            sysf.write_bytes(b"MZ")
            self.assertTrue(q.is_protected(sysf))
            with self.assertRaises(q.ProtectedPath):
                self.v.put(sysf, {})
            self.assertTrue(sysf.exists())
        self.assertTrue(q.is_protected("C:/pagefile.sys"))

    def test_locked_file_falls_back_to_rename(self):
        f = self.d / "c.exe"
        f.write_bytes(b"MZ locked")
        real_unlink = Path.unlink
        calls = {"n": 0}

        def flaky(self_, *a, **k):
            if self_ == f and calls["n"] == 0:
                calls["n"] += 1
                raise PermissionError("in use")
            return real_unlink(self_, *a, **k)
        with mock.patch.object(Path, "unlink", flaky):
            m = self.v.put(f, {})
        self.assertIn(m["removal"], ("removed", "renamed-pending-reboot"))
        self.assertFalse(f.exists())

    def test_ids_are_validated(self):
        for bad in ("../../x", "", "abc", None):
            with self.assertRaises(ValueError):
                self.v.delete(bad)

    def test_purge_tolerates_bad_metadata(self):
        (self.d / "vault" / "zzz.json").write_text("{}")
        (self.d / "vault" / "yyy.json").write_text("not json")
        self.v.purge_older(0)

    def test_restore_never_overwrites(self):
        f = self.d / "r.exe"
        for _ in range(3):
            f.write_bytes(b"MZ r")
            m = self.v.put(f, {})
            f.write_bytes(b"other")
            out = self.v.restore(m["id"])
            self.assertTrue(Path(out).exists())
        self.assertEqual(f.read_bytes(), b"other")
        self.assertEqual(len(list(self.d.glob("r.restored*.exe"))), 3)


class GovernorTest(unittest.TestCase):
    def gov(self, plugged=True, pct=None, cpu=0):
        g = Governor(probe=lambda: {"cpu": cpu, "plugged": plugged, "percent": pct})
        g.sample(now=1000)
        return g

    def test_critical_sensors_stay_fast_on_battery(self):
        g = self.gov(plugged=False, pct=50)
        self.assertEqual(g.interval("realtime", 2), 2)
        self.assertGreaterEqual(g.interval("radar", 1800), 1800 * 2 * 0.9)

    def test_saver_mode_stretches_heavy_tasks(self):
        g = self.gov(plugged=False, pct=10)
        self.assertEqual(g.mode(), "saver")
        self.assertLessEqual(g.interval("realtime", 2), 3)
        self.assertGreaterEqual(g.interval("posture", 3600), 3600 * 4 * 0.9)

    def test_busy_defer_is_bounded(self):
        g = self.gov(cpu=95)
        g.max_defer = 100
        self.assertTrue(g.should_defer("radar", now=0))
        self.assertTrue(g.should_defer("radar", now=50))
        self.assertFalse(g.should_defer("radar", now=101))
        self.assertFalse(g.should_defer("realtime", now=0))

    def test_ewma_ignores_single_spike(self):
        vals = iter([10, 100])
        g = Governor(probe=lambda: {"cpu": next(vals), "plugged": True, "percent": None})
        g.sample(now=0)
        g.sample(now=20)
        self.assertLess(g.load, 70)


class EngineBehaviour(unittest.TestCase):
    def setUp(self):
        os.environ["AUREON_DATA"] = tempfile.mkdtemp()
        from aureon_defender.engine import Engine
        self.e = Engine()

    def test_alert_memory_not_in_errors(self):
        self.e.alert_once("k", {"severity": "medium", "kind": "x", "title": "t"})
        self.assertNotIn("k", self.e.errors)
        self.assertIn("k", self.e.alerted)

    def test_inbox_scan_does_not_block_fast_loop(self):
        gate = threading.Event()
        with mock.patch.object(self.e, "scan_path", side_effect=lambda r: gate.wait(5)):
            box = Path(os.environ["AUREON_DATA"]) / "inbox"
            box.mkdir(exist_ok=True)
            (box / "1.json").write_text(json.dumps({"type": "scan", "path": "/tmp"}))
            t0 = time.time()
            self.e.t_inbox()
            self.assertLess(time.time() - t0, 1)
            gate.set()

    def test_report_has_no_ai(self):
        self.e.j.add("high", "threat", "Blocked x")
        with mock.patch.dict(sys.modules, {"aureon.analyst": None}):
            self.e.t_report()
        text = (Path(os.environ["AUREON_DATA"]) / "report.md").read_text()
        self.assertIn("Blocked x", text)

    def test_scan_path_is_lazy_and_bounded(self):
        d = Path(tempfile.mkdtemp())
        for i in range(30):
            (d / f"{i}.txt").write_text("hi")
        seen = []
        with mock.patch.object(self.e, "on_file", side_effect=lambda p: seen.append(p)):
            self.e.scan_path(d, limit=10)
        self.assertEqual(len(seen), 10)

    def test_protected_threat_is_reported_not_moved(self):
        r = {"verdict": "malicious", "reasons": ["t"], "sha256": "x", "score": 100}
        with mock.patch.object(self.e.scanner, "scan", return_value=r), \
             mock.patch.object(self.e.vault, "put", side_effect=q.ProtectedPath("system")):
            ev = self.e.on_file(Path("/x/kernel32.dll"))
        self.assertIn("system file", ev["title"])


if __name__ == "__main__":
    unittest.main()
