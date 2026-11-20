"""Autopilot: remove what is found unless the hardware needs it; adapt to any machine. Runs on every OS."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aureon_defender import hwguard  # noqa: E402
from aureon_defender.governor import Governor  # noqa: E402


class Budget(unittest.TestCase):
    def test_small_tablet_gets_lite_budget(self):
        b = hwguard.budget({"cpus": 2, "ram_gb": 4, "battery": {"percent": 80}, "disk": "ssd"})
        self.assertEqual(b["tier"], "lite")
        self.assertEqual(b["interval_scale"], 1.6)
        self.assertEqual(b["scan_workers"], 1)
        self.assertEqual(b["sweep_files"], 1500)            # floor: small machines still sweep a useful amount

    def test_workstation_gets_performance_budget(self):
        b = hwguard.budget({"cpus": 32, "ram_gb": 64, "battery": None, "disk": "ssd"})
        self.assertEqual(b["tier"], "performance")
        self.assertEqual(b["interval_scale"], 0.75)
        self.assertEqual(b["sweep_files"], 6000)
        self.assertEqual(b["scan_workers"], 4)

    def test_laptop_with_spinning_disk_slows_down(self):
        ssd = hwguard.budget({"cpus": 8, "ram_gb": 8, "battery": {"percent": 50}, "disk": "ssd"})
        hdd = hwguard.budget({"cpus": 8, "ram_gb": 8, "battery": {"percent": 50}, "disk": "hdd"})
        self.assertEqual(ssd["tier"], "standard")
        self.assertGreater(hdd["interval_scale"], ssd["interval_scale"])

    def test_unknown_values_assume_small_machine(self):
        b = hwguard.budget({"cpus": None, "ram_gb": None})
        self.assertEqual(b["tier"], "lite")

    def test_budget_is_deterministic(self):
        info = {"cpus": 6, "ram_gb": 12, "battery": None, "disk": "unknown"}
        self.assertEqual(hwguard.budget(info), hwguard.budget(dict(info)))

    def test_profile_runs_on_this_machine(self):
        p = hwguard.profile(refresh=True)
        self.assertIn(p["tier"], ("lite", "standard", "performance"))
        self.assertGreaterEqual(p["cpus"], 1)

    def test_governor_scales_heavy_tasks_but_not_realtime(self):
        g = Governor(scale=1.6)
        self.assertEqual(g.interval("realtime", 2), 2)
        self.assertGreaterEqual(g.interval("radar", 100), 1.6 * 100 * 0.9)
        self.assertEqual(Governor(scale=99).scale, 2.0)      # clamped


class HardwareNeeds(unittest.TestCase):
    def test_registered_driver_anywhere_is_needed(self):
        drv = Path(tempfile.gettempdir()) / "vendor" / "gpu.sys"
        reg = hwguard.registered_drivers(reader=lambda: [str(drv)])
        self.assertIn("registered", hwguard.needed_by_hardware(drv, drivers=reg))

    def test_dropped_driver_in_downloads_is_not_needed(self):
        # a stray .sys nobody registered is the bring-your-own-vulnerable-driver pattern: it stays removable
        self.assertIsNone(hwguard.needed_by_hardware(Path.home() / "Downloads" / "rtcore64.sys", drivers=frozenset()))

    def test_boot_chain_names_are_needed(self):
        self.assertEqual(hwguard.needed_by_hardware("/anywhere/bootx64.efi", drivers=frozenset()), "part of the boot chain")

    @unittest.skipIf(os.name == "nt", "posix layout")
    def test_linux_firmware_and_modules_are_needed(self):
        with mock.patch.object(hwguard.sys, "platform", "linux"):
            self.assertIsNotNone(hwguard.needed_by_hardware("/lib/firmware/iwlwifi-cc-a0-77.ucode", drivers=frozenset()))
            self.assertIsNotNone(hwguard.needed_by_hardware("/lib/modules/6.1/kernel/drivers/net/e1000e.ko", drivers=frozenset()))
            self.assertIsNone(hwguard.needed_by_hardware("/home/u/Downloads/x.ko", drivers=frozenset()))

    def test_image_path_forms(self):
        with mock.patch.dict(os.environ, {"SYSTEMROOT": r"C:\Windows"}):
            self.assertEqual(hwguard._expand_image_path(r"\SystemRoot\System32\drivers\nvlddmkm.sys"), r"C:\Windows\System32\drivers\nvlddmkm.sys")
            self.assertEqual(hwguard._expand_image_path(r"system32\DRIVERS\igdkmd64.sys"), r"C:\Windows\system32\DRIVERS\igdkmd64.sys")
            self.assertEqual(hwguard._expand_image_path(r"\??\C:\Program Files\Vendor\hw.sys"), r"C:\Program Files\Vendor\hw.sys")
            self.assertEqual(hwguard._expand_image_path(r'"C:\Program Files\V\svc.exe" -k run'), r"C:\Program Files\V\svc.exe")


class Decide(unittest.TestCase):
    def d(self, verdict, path="/home/u/Downloads/a.exe", sig=None, engines=None):
        return hwguard.decide({"verdict": verdict, "engines": engines or {}}, path, signature=sig, drivers=frozenset())

    def test_confirmed_malware_is_wiped(self):
        self.assertEqual(self.d("malicious", engines={"reputation": "bad"})["action"], "wipe")

    def test_heuristic_malicious_goes_to_vault(self):
        self.assertEqual(self.d("malicious")["action"], "quarantine")

    def test_suspicious_unsigned_is_removed(self):
        self.assertEqual(self.d("suspicious", sig="NotSigned")["action"], "quarantine")

    def test_suspicious_but_validly_signed_is_kept(self):
        self.assertEqual(self.d("suspicious", sig="Valid")["action"], "keep")

    def test_hardware_need_beats_everything(self):
        r = hwguard.decide({"verdict": "malicious", "engines": {"reputation": "bad"}}, "/x/bootmgr", drivers=frozenset())
        self.assertEqual(r["action"], "keep")

    def test_clean_does_nothing(self):
        self.assertEqual(self.d("clean")["action"], "none")


class EngineReact(unittest.TestCase):
    """The engine removes a suspicious, unsigned download without asking anyone."""

    def setUp(self):
        from aureon_defender.engine import Engine
        from aureon_defender.quarantine import Vault
        self.tmp = Path(tempfile.mkdtemp())
        self.e = object.__new__(Engine)
        self.e.s = {"auto_quarantine": True, "auto_quarantine_suspicious": True, "auto_wipe_confirmed": True, "trash_days": 30}
        self.e.state = {"counts": {"quarantined": 0}}
        self.e.vault = Vault(self.tmp / "vault")
        self.f = self.tmp / "Downloads" / "invoice.pdf.exe"
        self.f.parent.mkdir()
        self.f.write_bytes(b"MZ not really a program")

    def result(self, verdict, **eng):
        import hashlib
        return {"verdict": verdict, "score": 60, "reasons": ["double extension"], "engines": eng,
                "sha256": hashlib.sha256(self.f.read_bytes()).hexdigest(), "size": self.f.stat().st_size}

    def test_suspicious_unsigned_file_is_removed_silently(self):
        with mock.patch("aureon_defender.scanner.authenticode", return_value="NotSigned"), \
             mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            ev = self.e.react(self.f, self.result("suspicious"))
        self.assertFalse(self.f.exists())
        self.assertTrue(ev["blocked"])
        self.assertEqual(len(self.e.vault.list()), 1)

    def test_confirmed_malware_is_wiped_with_no_vault_copy(self):
        with mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            ev = self.e.react(self.f, self.result("malicious", reputation="bad"))
        self.assertFalse(self.f.exists())
        self.assertIn("permanently deleted", ev["detail"])
        self.assertEqual(self.e.vault.list(), [])

    def test_registered_driver_is_never_touched(self):
        with mock.patch.object(hwguard, "registered_drivers", return_value=frozenset({hwguard._norm(self.f).rstrip("\\/")})):
            ev = self.e.react(self.f, self.result("malicious", reputation="bad"))
        self.assertTrue(self.f.exists())
        self.assertNotIn("blocked", ev)

    def test_signed_suspicious_file_is_kept(self):
        with mock.patch("aureon_defender.scanner.authenticode", return_value="Valid"), \
             mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            ev = self.e.react(self.f, self.result("suspicious"))
        self.assertTrue(self.f.exists())
        self.assertIn("signed", ev["detail"])


class EngineReactions(unittest.TestCase):
    """Paths that only fire on Windows, exercised with the OS calls replaced."""

    def setUp(self):
        from aureon_defender.engine import Engine
        from aureon_defender.quarantine import Vault
        from aureon_defender.scanner import Reputation
        self.tmp = Path(tempfile.mkdtemp())
        self.e = object.__new__(Engine)
        self.e.s = {"auto_quarantine": True, "auto_quarantine_suspicious": True, "auto_wipe_confirmed": True,
                    "trash_days": 30, "canary_suspend_writer": True}
        self.e.state = {"counts": {"quarantined": 0}}
        self.e.alerted = {}
        self.e.vault = Vault(self.tmp / "vault")
        self.e.rep = Reputation(self.tmp / "rep.db")
        self.events = []
        self.e.j = mock.Mock()
        self.e.j.add.side_effect = lambda *a, **k: self.events.append((a, k))

    def test_startup_shortcut_entry_is_deleted(self):
        lnk = self.tmp / "evil.lnk"
        lnk.write_text("x")
        self.assertTrue(self.e.remove_autostart(f"startup:{lnk}", str(lnk)))
        self.assertFalse(lnk.exists())

    def test_scheduled_task_entry_is_deleted_with_schtasks(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)) as run:
            self.assertTrue(self.e.remove_autostart("task:\\Updater", "c:/x.exe"))
        self.assertEqual(run.call_args[0][0][:4], ["schtasks", "/delete", "/tn", "\\Updater"])

    def test_services_are_never_deleted(self):
        self.assertFalse(self.e.remove_autostart("service:gpudrv", "c:/x.sys"))

    def test_tripwire_stops_and_removes_unsigned_writer(self):
        exe = self.tmp / "locker.exe"
        exe.write_bytes(b"MZ ransom")
        proc = mock.Mock()
        self.e.scanner = mock.Mock()
        self.e.scanner.scan.return_value = {"verdict": "clean", "score": 0, "reasons": [], "engines": {}, "path": str(exe)}
        with mock.patch("psutil.Process", return_value=proc), \
             mock.patch("aureon_defender.scanner.authenticode", return_value="NotSigned"), \
             mock.patch.object(hwguard, "registered_drivers", return_value=frozenset()):
            self.e.on_canary({"writers": [(4242, "locker.exe", str(exe))]})
        proc.suspend.assert_called_once()
        proc.kill.assert_called_once()
        self.assertFalse(exe.exists())
        self.assertTrue(any("stopped locker.exe" in a[2] for a, _ in self.events))

    def test_tripwire_leaves_signed_programs_alone(self):
        exe = self.tmp / "backup.exe"
        exe.write_bytes(b"MZ signed")
        with mock.patch("psutil.Process") as P, mock.patch("aureon_defender.scanner.authenticode", return_value="Valid"):
            self.e.on_canary({"writers": [(77, "backup.exe", str(exe))]})
        P.assert_not_called()
        self.assertTrue(exe.exists())

    def test_vulnerable_driver_in_use_is_reported_not_removed(self):
        import hashlib
        drv = self.tmp / "RTCore64.sys"
        drv.write_bytes(b"vulnerable but loaded")
        self.e.rep.add_bad([(hashlib.sha256(drv.read_bytes()).hexdigest(), "LOLDrivers", "vulnerable driver rtcore64.sys")])
        self.e.emit = lambda ev: self.events.append(((ev["severity"], ev["kind"], ev["title"]), ev))
        self.e.t_drivers(drivers=[str(drv)])
        self.assertTrue(drv.exists())
        self.assertEqual(self.e.state["drivers_flagged"], 1)
        self.assertTrue(any("vulnerable driver in use" in a[2] for a, _ in self.events))


if __name__ == "__main__":
    unittest.main()
