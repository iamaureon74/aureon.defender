"""Silent mode: confirmed threats wiped at once, only blocks notify, trash emptied by deletion date."""
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AUREON_DATA", tempfile.mkdtemp())

from aureon_defender import quarantine as q, trash  # noqa: E402
from aureon_defender.notify import Notifier  # noqa: E402


class Wipe(unittest.TestCase):
    def test_wipe_overwrites_and_removes(self):
        d = Path(tempfile.mkdtemp())
        f = d / "evil.exe"
        f.write_bytes(b"MZ" + os.urandom(5000))
        r = q.wipe(f)
        self.assertEqual(r["removal"], "removed")
        self.assertEqual(list(d.iterdir()), [])

    def test_wipe_refuses_changed_and_protected(self):
        d = Path(tempfile.mkdtemp())
        f = d / "a.exe"
        f.write_bytes(b"MZ")
        with self.assertRaises(ValueError):
            q.wipe(f, {"sha256": "0" * 64})
        self.assertTrue(f.exists())
        with mock.patch.object(q, "is_protected", return_value=True):
            with self.assertRaises(q.ProtectedPath):
                q.wipe(f)
        self.assertTrue(f.exists())

    def test_engine_wipes_confirmed_but_quarantines_heuristic(self):
        os.environ["AUREON_DATA"] = tempfile.mkdtemp()
        from aureon_defender.engine import Engine
        e = Engine()
        d = Path(tempfile.mkdtemp())
        f = d / "known.exe"
        f.write_bytes(b"MZ known")
        conf = {"verdict": "malicious", "reasons": ["known malware"], "engines": {"reputation": "bad"}, "score": 100}
        with mock.patch.object(e.scanner, "scan", return_value=conf):
            ev = e.on_file(f)
        self.assertIn("deleted", ev["title"])
        self.assertTrue(ev["blocked"])
        self.assertIn("Why:", ev["detail"])
        self.assertFalse(f.exists())
        self.assertEqual(e.vault.list(), [])
        g = d / "odd.pdf.exe"
        g.write_bytes(b"MZ odd")
        heur = {"verdict": "malicious", "reasons": ["double extension"], "engines": {"heuristics": 3}, "score": 95}
        with mock.patch.object(e.scanner, "scan", return_value=heur):
            ev = e.on_file(g)
        self.assertIn("quarantined", ev["title"])
        self.assertEqual(len(e.vault.list()), 1)


class SilentNotify(unittest.TestCase):
    def test_only_blocks_notify(self):
        sent = []
        n = Notifier(send=lambda *a, **k: sent.append(a[0]), silent=lambda: True)
        self.assertIsNone(n.handle({"severity": "high", "kind": "sentry", "title": "camera on"}, now=1))
        self.assertEqual(n.handle({"severity": "high", "kind": "threat", "title": "Blocked x", "blocked": True}, now=2), "shown")
        self.assertEqual(n.handle({"severity": "high", "kind": "ransomware", "title": "tripwire"}, now=3), "shown")
        self.assertEqual(sent, ["Blocked x", "tripwire"])
        loud = Notifier(send=lambda *a, **k: None, silent=lambda: False)
        self.assertEqual(loud.handle({"severity": "high", "kind": "sentry", "title": "c"}, now=1), "shown")


class Trash(unittest.TestCase):
    def info(self, path, when):
        ft = int((when + trash.EPOCH_DIFF) * 10_000_000)
        path.write_bytes(struct.pack("<QQQ", 2, 10, ft) + b"\0" * 8)

    def test_recycle_bin_by_deletion_date(self):
        b = Path(tempfile.mkdtemp()) / "S-1-5-21-1"
        b.mkdir()
        now = time.time()
        self.info(b / "$IOLD.txt", now - 40 * 86400)
        (b / "$ROLD.txt").write_text("old")
        self.info(b / "$INEW.txt", now - 86400)
        (b / "$RNEW.txt").write_text("new")
        (b / "$RDIR").mkdir()
        (b / "$RDIR" / "x").write_text("x")
        self.info(b / "$IDIR", now - 90 * 86400)
        self.assertEqual(trash.purge_recycle_bin(30, bins=[b], now=now), 2)
        self.assertEqual(sorted(p.name for p in b.iterdir()), ["$INEW.txt", "$RNEW.txt"])

    def test_freedesktop_trash(self):
        t = Path(tempfile.mkdtemp())
        (t / "info").mkdir()
        (t / "files").mkdir()
        (t / "files" / "a.txt").write_text("a")
        (t / "info" / "a.txt.trashinfo").write_text("[Trash Info]\nPath=/x/a.txt\nDeletionDate=2020-01-01T00:00:00\n")
        (t / "files" / "b.txt").write_text("b")
        (t / "info" / "b.txt.trashinfo").write_text("[Trash Info]\nPath=/x/b.txt\nDeletionDate=" +
                                                   time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
        self.assertEqual(trash.purge_freedesktop_trash(30, dirs=[t]), 1)
        self.assertEqual([p.name for p in (t / "files").iterdir()], ["b.txt"])

    def test_zero_days_means_never(self):
        self.assertEqual(trash.purge_all(0), {"recycle_bin": 0, "trash": 0})



class DeviceTraces(unittest.TestCase):
    def test_only_old_unplugged_usb_records(self):
        from aureon_defender import devwipe
        now = 1_000_000_000
        old, new = now - 40 * 86400, now - 86400
        recs = [{"id": "USB\\VID_1&PID_2\\CHARGER", "removal": old},
                {"id": "USB\\VID_1&PID_2\\PLUGGEDNOW", "removal": old},
                {"id": "USB\\VID_3\\RECENT", "removal": new},
                {"id": "BTHENUM\\HEADPHONES", "removal": old},
                {"id": "USB\\ROOT_HUB30\\X", "removal": old, "builtin": True},
                {"id": "USBSTOR\\Disk&Ven_X\\1", "arrival": old}]
        got = devwipe.candidates(recs, ["usb\\vid_1&pid_2\\pluggednow"], 30, now=now)
        self.assertEqual(got, ["USBSTOR\\Disk&Ven_X\\1", "USB\\VID_1&PID_2\\CHARGER"])
        calls = []

        class R:
            returncode = 0
        res = devwipe.wipe_traces(30, records=recs, present=["USB\\VID_1&PID_2\\PLUGGEDNOW"],
                                  run=lambda cmd, **k: calls.append(cmd) or R(), now=now)
        self.assertEqual(res, {"removed": 2, "failed": 0})
        self.assertTrue(all(c[:2] == ["pnputil", "/remove-device"] for c in calls))


if __name__ == "__main__":
    unittest.main()


class Drain(unittest.TestCase):
    def test_meter_attributes_cpu_and_handles_pid_reuse(self):
        from aureon_defender.drain import DrainMeter
        samples = iter([
            {1: (100, 10.0, 0, "game.exe"), 2: (100, 1.0, 0, "updater.exe")},
            {1: (100, 40.0, 5 << 20, "game.exe"), 2: (100, 2.0, 0, "updater.exe")},
            {1: (100, 50.0, 5 << 20, "game.exe"), 2: (999, 500.0, 0, "other.exe")},   # pid 2 reused
        ])
        m = DrainMeter(sampler=lambda: next(samples))
        for t in (0, 60, 120):
            m.tick(now=t)
        top = m.top(now=120)
        self.assertEqual(top[0]["name"], "game.exe")
        self.assertEqual(top[0]["cpu_seconds"], 40.0)
        self.assertEqual(top[0]["disk_mb"], 5.0)
        self.assertNotIn("other.exe", [r["name"] for r in top])
        self.assertAlmostEqual(sum(r["share"] for r in top), 100, delta=0.2)

    def test_old_buckets_expire(self):
        from aureon_defender.drain import DrainMeter
        m = DrainMeter(sampler=lambda: {}, keep_hours=24)
        m.buckets[0] = {"x": [1, 0]}
        m.tick(now=30 * 3600)
        self.assertNotIn(0, m.buckets)

    def test_silent_grouping_and_listeners(self):
        from aureon_defender.drain import listeners, silent
        procs = [{"pid": 1, "name": "svchost.exe", "session": 0}, {"pid": 2, "name": "chrome.exe", "session": 1},
                 {"pid": 3, "name": "telemetry.exe", "session": 1, "exe": "x"}]
        r = silent(procs, windowed={2}, company=lambda exe: "Acme" if exe else None)
        self.assertEqual(r["system"], ["svchost.exe"])
        self.assertEqual(r["your_account"], {"Acme": ["telemetry.exe"]})
        lis = listeners(names={"Cortana.exe", "x.exe"}, voice={"AgentActivationEnabled": True})
        self.assertEqual(len(lis["running"]), 1)
        self.assertEqual(len(lis["notes"]), 1)
