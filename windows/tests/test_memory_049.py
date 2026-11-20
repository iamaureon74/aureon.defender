"""Silent memory (fold-memory inside aureon): fold, cap, ransomware rollback. Runs on every OS."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FOLD_MEMORY_NO_FSYNC", "1")
from aureon_defender.memory import Keeper, entropy  # noqa: E402

HW = {"tier": "standard", "interval_scale": 1.0, "scan_workers": 1}
PLUGGED = lambda: {"plugged": True, "percent": None}  # noqa: E731
ROOMY = lambda: {"total": 500 * 2**30, "free": 300 * 2**30}  # noqa: E731


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / "Documents"
        self.docs.mkdir()
        (self.docs / "plan.docx").write_text("quarterly plan\n" * 400)
        (self.docs / "notes.txt").write_text("call the bank on monday\n" * 50)
        (self.docs / "copy-of-notes.txt").write_text("call the bank on monday\n" * 50)
        (self.docs / "budget.csv").write_text("month,amount\n" + "jan,100\n" * 300)
        self.k = Keeper(store=self.tmp / "store", folders=[self.docs], power=PLUGGED, disk=ROOMY, hw=HW)

    def test_folds_once_and_skips_unchanged(self):
        first = self.k.run_once()
        self.assertEqual(first["new"], 4)
        self.assertEqual(first["files_held"], 3)              # two identical notes share one copy
        again = self.k.run_once()
        self.assertEqual(again["unchanged"], 4)
        self.assertEqual(self.k.dupes()["groups"], 1)          # reported, never deleted
        self.assertTrue((self.docs / "copy-of-notes.txt").exists())

    def test_ransomware_rollback_restores_only_encrypted_files(self):
        self.k.run_once()
        original = (self.docs / "plan.docx").read_bytes()
        time.sleep(1.1)                                        # held_since is second-resolution
        since = time.time()
        time.sleep(0.05)
        (self.docs / "plan.docx").write_bytes(os.urandom(20000))                  # encrypted in place
        csv = (self.docs / "budget.csv").read_bytes()
        (self.docs / "budget.csv").unlink()
        (self.docs / "budget.csv.locked").write_bytes(os.urandom(9000))           # renamed and encrypted
        (self.docs / "notes.txt").write_text("call the bank on tuesday\n" * 50)   # a normal edit
        res = self.k.rollback(since)
        self.assertEqual(sorted(Path(p).name for p in res["restored"]), ["budget.csv", "plan.docx"])
        self.assertEqual((self.docs / "plan.docx").read_bytes(), original)
        self.assertEqual((self.docs / "budget.csv").read_bytes(), csv)
        self.assertFalse((self.docs / "budget.csv.locked").exists())
        self.assertIn("tuesday", (self.docs / "notes.txt").read_text())          # left alone
        self.assertGreater(self.k.paused_until, time.time())                       # no folding encrypted junk

    def test_rollback_after_encrypted_version_was_folded(self):
        """the hourly fold may have picked up the encrypted bytes before the alarm; the good version still wins."""
        self.k.run_once()
        good = (self.docs / "plan.docx").read_bytes()
        time.sleep(1.1)
        since = time.time()
        time.sleep(0.05)
        (self.docs / "plan.docx").write_bytes(os.urandom(20000))
        self.k.run_once()
        self.assertEqual(self.k.rollback(since)["restored"], [str(self.docs / "plan.docx")])
        self.assertEqual((self.docs / "plan.docx").read_bytes(), good)

    def test_skips_turn_on_low_battery_and_full_disk(self):
        k = Keeper(store=self.tmp / "s2", folders=[self.docs], power=lambda: {"plugged": False, "percent": 20}, disk=ROOMY, hw=HW)
        self.assertIn("battery", k.why_not())
        k = Keeper(store=self.tmp / "s3", folders=[self.docs], power=PLUGGED, disk=lambda: {"total": 100 * 2**30, "free": 2**30}, hw=HW)
        self.assertIn("disk", k.why_not())
        self.assertIsNone(k.tick())
        self.assertEqual(k.status()["skipped"], "less than 10% of the disk is free")

    def test_cap_trims_old_versions(self):
        self.k.s = {"memory_max_gb": 1e-9}                     # a cap of one byte forces trimming
        trimmed = 0
        for i in range(4):
            (self.docs / "plan.docx").write_text(f"version {i}\n" * 600)
            os.utime(self.docs / "plan.docx", (time.time() + i, time.time() + i))
            out = self.k.run_once()
            trimmed += out["trimmed"]
        self.assertGreater(trimmed, 0)
        self.assertLessEqual(out["old_versions"], 1)            # keep 2 = the current version + one older

    def test_agent_rolls_back_when_the_engine_tripwire_fires(self):
        from unittest import mock
        from aureon_defender.agent import on_ransomware
        self.k.run_once()
        time.sleep(1.1)
        t = time.time()
        time.sleep(0.05)
        (self.docs / "plan.docx").write_bytes(os.urandom(20000))
        api = mock.Mock()
        api.keeper = self.k
        on_ransomware(api, [{"kind": "threat", "t": t}, {"kind": "ransomware", "t": t + 60}])
        self.assertIn("quarterly plan", (self.docs / "plan.docx").read_text())
        args, kw = api.uj.add.call_args
        self.assertIn("put back 1 file", args[2])
        self.assertTrue(kw["blocked"])

    def test_entropy_scale(self):
        self.assertLess(entropy(b"hello world " * 100), 4)
        self.assertGreater(entropy(os.urandom(65536)), 7.9)


if __name__ == "__main__":
    unittest.main()
