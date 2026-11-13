"""noah.shield integration, device timeline, leak audit, notifications. Temp folders and fakes only."""
import base64
import io
import json
import os
import struct
import sys
import tempfile
import time
import unittest
import xml.dom.minidom
from pathlib import Path

WIN = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(WIN), str(WIN.parent)]
TMP = Path(tempfile.mkdtemp(prefix="aureon-nd-"))
os.environ.setdefault("AUREON_DATA", str(TMP / "data"))
os.environ.setdefault("AUREON_USER", str(TMP / "user"))

from aureon_defender import devices, leaks, noah, notify, studio  # noqa: E402


class NoahImport(unittest.TestCase):
    def test_extension_is_bundled_whole(self):
        m = noah.manifest()
        self.assertEqual(m["name"], "noah shield")
        self.assertTrue((noah.NOAH / "background.js").exists())
        self.assertGreater(len(list((noah.NOAH / "content").glob("*.js"))), 30)

    def test_chromium_id_matches_algorithm(self):
        import hashlib
        key = noah.manifest()["key"]
        expected = "".join(chr(97 + int(c, 16)) for c in hashlib.sha256(base64.b64decode(key)).hexdigest()[:32])
        self.assertEqual(noah.chromium_id(), expected)
        self.assertRegex(expected, r"^[a-p]{32}$")

    def test_tracker_rules_become_domains(self):
        d = noah.rule_domains()
        self.assertGreater(len(d), 2000)
        self.assertTrue(all("." in x and "/" not in x for x in d[:200]))

    def test_secret_rules_all_compile_and_detect(self):
        self.assertEqual(len(noah.secret_rules()), 220)
        tok = "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"
        self.assertEqual(noah.find_secrets(f"token={tok}")[0][0], "github-pat")
        self.assertEqual(noah.find_secrets("4111 1111 1111 1111")[0][0], "payment-card")
        self.assertEqual(noah.find_secrets("abandon " * 11 + "about")[0][0], "seed-phrase")
        self.assertEqual(noah.find_secrets("meeting at 4pm, bring the 1111 report"), [])

    def test_folder_secret_scan_skips_vendor_dirs(self):
        d = TMP / "repo"
        (d / "node_modules").mkdir(parents=True)
        (d / "config.env").write_text("AWS=AKIAIOSFODNN7EXAMPLE\nGH=ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5\n")
        (d / "node_modules" / "x.js").write_text("ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5")
        hits = noah.scan_secrets(d)
        self.assertTrue(hits)
        self.assertTrue(all("node_modules" not in h["path"] for h in hits))

    def test_clipboard_guard_flow(self):
        seq = [1]
        text = ["hello"]
        found = []
        cleared = []
        orig = (noah.clipboard_seq, noah.clipboard_text, noah.clipboard_clear)
        noah.clipboard_seq = lambda: seq[0]
        noah.clipboard_text = lambda: text[0]
        noah.clipboard_clear = lambda: cleared.append(1) or True
        try:
            g = noah.ClipboardGuard(found.append, clear_after=60)
            self.assertIsNone(g.tick(now=0))
            seq[0], text[0] = 2, "ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"
            self.assertEqual(g.tick(now=1), "secret")
            self.assertIsNone(g.tick(now=30))
            self.assertEqual(g.tick(now=62), "cleared")
            self.assertEqual(cleared, [1])
            seq[0], text[0] = 3, "ghp_aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"
            g.tick(now=100)
            seq[0], text[0] = 4, "something else"            # user copied something new -> nothing is cleared
            g.tick(now=101)
            self.assertIsNone(g.tick(now=200))
            self.assertEqual(cleared, [1])
        finally:
            noah.clipboard_seq, noah.clipboard_text, noah.clipboard_clear = orig

    def test_jpeg_metadata_removed_losslessly(self):
        from PIL import Image
        p = TMP / "photo.jpg"
        im = Image.new("RGB", (64, 48), (120, 80, 40))
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"
        exif[0x0110] = "Model X"
        gps = {1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)}
        exif[0x8825] = gps
        im.save(p, exif=exif.tobytes(), quality=90)
        before = noah.describe_metadata(p)
        self.assertEqual(before.get("Model"), "Model X")
        self.assertEqual(before.get("GPS"), "location recorded")
        r = noah.clean_media(p)
        self.assertIn("EXIF/XMP", r["removed"])
        out = Path(r["written"])
        self.assertEqual(noah.describe_metadata(out), {})
        a, b = p.read_bytes(), out.read_bytes()
        self.assertEqual(a[a.index(b"\xff\xda"):], b[b.index(b"\xff\xda"):])      # image data byte-identical

    def test_png_text_chunks_removed(self):
        from PIL import Image, PngImagePlugin
        p = TMP / "shot.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("Author", "someone")
        Image.new("RGB", (8, 8)).save(p, pnginfo=info)
        r = noah.clean_media(p)
        self.assertIn("tEXt", r["removed"])
        self.assertNotIn(b"someone", Path(r["written"]).read_bytes())

    def test_breach_check_sends_only_prefix(self):
        import hashlib
        sent = []
        h = hashlib.sha1(b"hunter2").hexdigest().upper()

        def fetch(prefix):
            sent.append(prefix)
            return f"0000000000000000000000000000000000A:3\n{h[5:]}:17043\n"
        self.assertEqual(noah.breach_count("hunter2", fetch), 17043)
        self.assertEqual(sent, [h[:5]])
        self.assertEqual(noah.breach_count("not-in-list-xyz", lambda p: "ABC:1\n"), 0)

    def test_native_host_protocol(self):
        def frame(o):
            b = json.dumps(o).encode()
            return struct.pack("<I", len(b)) + b
        inp = io.BytesIO(frame({"type": "tor.install"}) + frame({"type": "nope"}) + frame({"type": "opensnitch.status"}))
        out = io.BytesIO()
        noah.native_host_loop(inp, out)
        out.seek(0)
        replies = []
        while True:
            h = out.read(4)
            if not h:
                break
            replies.append(json.loads(out.read(struct.unpack("<I", h)[0])))
        self.assertEqual(len(replies), 3)
        self.assertIn("doesn't download", replies[0]["error"])
        self.assertIn("unknown request", replies[1]["error"])

    def test_noah_yara_rules_are_loaded_by_scanner(self):
        try:
            import yara  # noqa: F401
        except ImportError:
            self.skipTest("yara-python not installed")
        from aureon_defender.scanner import Scanner, Reputation
        sc = Scanner({"use_defender_engine": False}, Reputation(TMP / "r.db"))
        self.assertIsNotNone(sc.yara.rules)

    def test_looks_become_presets(self):
        for n in noah.LOOKS:
            self.assertTrue(noah.look_path(n).exists(), n)
        img = [k for k, v in studio.PRESETS.items() if v["wallpaper"].startswith("image:")]
        self.assertEqual(sorted(v.split(":")[1] for v in (studio.PRESETS[k]["wallpaper"] for k in img)), sorted(noah.LOOKS))
        out = TMP / "meteor.jpg"
        studio.generate_wallpaper("image:meteor", studio.PRESETS["Meteor"]["palette"], 320, 200, out)
        from PIL import Image
        self.assertEqual(Image.open(out).size, (320, 200))

    def test_every_preset_in_a_group_and_readable(self):
        grouped = [n for names in studio.PRESET_GROUPS.values() for n in names]
        self.assertEqual(sorted(grouped), sorted(studio.PRESETS))
        for n, p in studio.PRESETS.items():
            bg, _, accent, text = p["palette"]
            lum = lambda h: sum(int(h[i:i + 2], 16) for i in (1, 3, 5)) / 3
            self.assertGreater(abs(lum(text) - lum(bg)), 120, f"{n}: text must stand out from background")


class DeviceTimeline(unittest.TestCase):
    def test_tracked_and_noise(self):
        self.assertTrue(devices.tracked(r"USBSTOR\Disk&Ven_SanDisk\123"))
        self.assertTrue(devices.tracked(r"BTHENUM\{0000110b}\7&abc"))
        self.assertFalse(devices.tracked(r"USB\ROOT_HUB30\4&37c5bd69&0&0"))
        self.assertFalse(devices.tracked(r"PCI\VEN_8086&DEV_1234"))
        self.assertFalse(devices.useful("Object Push Service", "Bluetooth"))
        self.assertTrue(devices.useful("Pixel 9", "Bluetooth"))
        self.assertTrue(devices.is_tracker("Tile"))
        self.assertFalse(devices.is_tracker("Tilemaster Pro"))

    def test_live_connect_disconnect_logged(self):
        present = [{r"USBSTOR\Disk&Ven_X\1", r"PCI\VEN_1"}]
        log = TMP / "dev.jsonl"
        ld = devices.LiveDevices(log=log, present=lambda: present[0],
                                 describe_fn=lambda d: {"id": d, "name": "SanDisk Ultra" if "USBSTOR" in d else "Phone", "category": "Storage"})
        self.assertEqual(ld.tick(), [])                                   # baseline
        present[0] = present[0] | {r"SWD\WPDBUSENUM\{abc}"}
        ev = ld.tick()
        self.assertEqual([(e["kind"], e["name"]) for e in ev], [("connected", "Phone")])
        present[0] = {r"PCI\VEN_1"}
        ev = ld.tick()
        self.assertEqual(sorted(e["kind"] for e in ev), ["disconnected", "disconnected"])
        self.assertEqual(len(devices.live_log(log)), 3)
        self.assertEqual(devices.prune(log, days=0), 0)

    def test_timeline_merges_dedupes_and_flags_trackers(self):
        t = time.time()
        rec = [{"id": "BT\\aa", "name": "Tile", "category": "Bluetooth", "first": t - 9000, "arrival": t - 100, "removal": None},
               {"id": "BT\\bb", "name": "Object Push Service", "category": "Bluetooth", "first": None, "arrival": t - 50, "removal": None},
               {"id": "NET\\1", "name": "HomeWiFi", "category": "WiFi network", "first": t - 99999, "arrival": t - 10, "removal": None}]
        live = [{"t": t - 5, "kind": "connected", "name": "SanDisk Ultra", "category": "Storage", "id": "x", "source": "aureon"},
                {"t": t - 5, "kind": "connected", "name": "SanDisk Ultra", "category": "Storage", "id": "x2", "source": "aureon"}]
        tl = devices.timeline(rec, live)
        names = [e["name"] for e in tl]
        self.assertEqual(names[0], "SanDisk Ultra")
        self.assertEqual(names.count("SanDisk Ultra"), 1)                 # same device, same minute -> one row
        self.assertNotIn("Object Push Service", names)
        self.assertTrue(next(e for e in tl if e["name"] == "Tile")["tracker"])
        self.assertEqual([e["t"] for e in tl], sorted((e["t"] for e in tl), reverse=True))

    def test_time_decoders(self):
        ft = int((1794500000 + 11644473600) * 1e7)
        self.assertAlmostEqual(devices._filetime_bytes(struct.pack("<Q", ft)), 1794500000, delta=1)
        st = struct.pack("<8H", 2026, 11, 4, 12, 9, 30, 0, 0)
        self.assertEqual(time.localtime(devices._systemtime(st))[:5], (2026, 11, 12, 9, 30))

    def test_present_ids_is_fast_and_real(self):
        t = time.time()
        ids = devices.present_ids()
        self.assertLess(time.time() - t, 0.5)
        self.assertGreater(len(ids), 10)


class LeakAudit(unittest.TestCase):
    def test_audit_logic_with_fake_registry(self):
        vals = {("HKCU", "AdvertisingInfo", "Enabled"): 1, ("HKLM", "Remote Assistance", "fAllowToGetHelp"): 0}

        def read(hive, key, value):
            return vals.get((hive, key.split("\\")[-1], value))
        res = {r["id"]: r for r in leaks.audit(read)}
        self.assertFalse(res["advertising_id"]["ok"])
        self.assertTrue(res["advertising_id"]["one_click"])
        self.assertTrue(res["remote_assistance"]["ok"])
        self.assertTrue(res["clipboard_history"]["ok"])           # absent = off by default
        self.assertFalse(res["llmnr"]["ok"])                       # absent = on by default
        self.assertEqual(sum(not r["ok"] for r in leaks.audit(read)), sum(not r["ok"] for r in res.values()))

    def test_fix_records_old_value(self):
        wrote = []
        b = TMP / "lb.json"
        leaks.fix("advertising_id", write=lambda *a: wrote.append(a), backup=b)
        self.assertEqual(wrote[0][3], 0)
        self.assertIn("advertising_id", json.loads(b.read_text()))
        with self.assertRaises(ValueError):
            leaks.fix("llmnr", write=lambda *a: None, backup=b)    # machine-wide -> admin path only

    def test_live_audit_runs(self):
        self.assertEqual(len(leaks.audit()), len(leaks.CHECKS))


class Notifications(unittest.TestCase):
    def test_toast_xml_is_valid_and_escaped(self):
        x = notify.toast_xml('Blocked <evil> & "x"', "path C:\\a&b", "high", "threat")
        doc = xml.dom.minidom.parseString(x)
        self.assertEqual(doc.documentElement.getAttribute("scenario"), "reminder")
        self.assertEqual(doc.documentElement.getAttribute("launch"), "aureon://activity")
        texts = [t.firstChild.data for t in doc.getElementsByTagName("text")]
        self.assertEqual(texts[0], 'Blocked <evil> & "x"')
        self.assertEqual([a.getAttribute("content") for a in doc.getElementsByTagName("action")], ["Open", "Dismiss"])

    def test_notifier_filters_bursts_and_quiet_hours(self):
        sent = []
        n = notify.Notifier(send=lambda *a, **k: sent.append(a[0]), window=8, burst=3)
        self.assertIsNone(n.handle({"severity": "info", "title": "x"}, now=0))
        for i in range(6):
            n.handle({"severity": "medium", "title": f"a{i}", "kind": "device"}, now=1 + i * 0.1)
        self.assertEqual(sent, ["a0", "a1", "a2", "Several things need a look"])
        q = notify.Notifier(send=lambda *a, **k: sent.append("q:" + a[0]), quiet=(22, 7))
        night = time.mktime((2026, 11, 13, 23, 30, 0, 0, 0, -1))
        self.assertIsNone(q.handle({"severity": "medium", "title": "m"}, now=night))
        self.assertEqual(q.handle({"severity": "high", "title": "h"}, now=night), "shown")   # high still gets through


if __name__ == "__main__":
    unittest.main()
