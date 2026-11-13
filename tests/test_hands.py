"""PiKVM rescue (fake KVM server), Key agent, HID guard, Key firmware simulation, deploy stacks, scripts."""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aureon import hidguard, keyagent, rescue  # noqa: E402


# ---------------- PiKVM ----------------
class FakeKVM(BaseHTTPRequestHandler):
    calls = []
    power = False

    def _reply(self, result=None, raw=None):
        data = raw if raw is not None else json.dumps({"ok": True, "result": result or {}}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if self.headers.get("X-KVMD-User") != "admin" or self.headers.get("X-KVMD-Passwd") != "pw":
            self.send_response(403)
            self.end_headers()
            return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        FakeKVM.calls.append(("GET", u.path, parse_qs(u.query), b""))
        if u.path == "/api/atx":
            self._reply({"enabled": True, "leds": {"power": FakeKVM.power, "hdd": False}})
        elif u.path == "/api/msd":
            self._reply({"drive": {"connected": True, "image": {"name": "rescue.iso"}}})
        elif u.path == "/api/streamer/snapshot":
            self._reply(raw=b"\xff\xd8JPEGDATA")

    def do_POST(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        FakeKVM.calls.append(("POST", u.path, parse_qs(u.query), body))
        self._reply()

    def log_message(self, *a):
        pass


class Rescue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeKVM)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.env = {"AUREON_KVM_URL": f"http://127.0.0.1:{cls.srv.server_port}", "AUREON_KVM_USER": "admin",
                   "AUREON_KVM_PASS": "pw"}

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def kvm(self):
        with mock.patch.dict(os.environ, self.env):
            return rescue.KVM()

    def test_missing_credentials(self):
        with mock.patch.dict(os.environ, {"AUREON_KVM_URL": ""}, clear=False):
            with self.assertRaises(SystemExit):
                rescue.KVM()

    def test_status(self):
        FakeKVM.power = False
        s = self.kvm().status()
        self.assertEqual(s, {"power_led": False, "hdd_led": False, "atx_enabled": True,
                             "msd_connected": True, "msd_image": "rescue.iso"})

    def test_power_logic(self):
        k = self.kvm()
        FakeKVM.power = False
        self.assertEqual(k.power("off"), "already off")
        self.assertEqual(k.power("on"), "pressed power")
        self.assertEqual(FakeKVM.calls[-1][1:3], ("/api/atx/click", {"button": ["power"]}))
        FakeKVM.power = True
        self.assertEqual(k.power("hard-off"), "pressed power_long")
        self.assertEqual(k.power("reset"), "pressed reset")

    def test_type_key_screenshot(self):
        k = self.kvm()
        k.type("RECOVERY-KEY-123")
        self.assertEqual(FakeKVM.calls[-1][1], "/api/hid/print")
        self.assertEqual(FakeKVM.calls[-1][3], b"RECOVERY-KEY-123")
        k.key("Delete")
        self.assertEqual(FakeKVM.calls[-1][2], {"key": ["Delete"]})
        p = Path(tempfile.mkdtemp()) / "s.jpg"
        k.screenshot(str(p))
        self.assertEqual(p.read_bytes(), b"\xff\xd8JPEGDATA")

    def test_iso_streamed_upload_sequence(self):
        iso = Path(tempfile.mkdtemp()) / "rescue.iso"
        iso.write_bytes(b"ISO" * 1000)
        FakeKVM.calls.clear()
        self.kvm().iso(str(iso))
        seq = [(c[1], c[2]) for c in FakeKVM.calls]
        self.assertEqual(seq[0], ("/api/msd/set_connected", {"connected": ["0"]}))
        self.assertEqual(seq[1], ("/api/msd/write", {"image": ["rescue.iso"]}))
        self.assertEqual(FakeKVM.calls[1][3], b"ISO" * 1000)
        self.assertEqual(seq[2], ("/api/msd/set_params", {"image": ["rescue.iso"], "cdrom": ["1"]}))
        self.assertEqual(seq[3], ("/api/msd/set_connected", {"connected": ["1"]}))

    def test_bad_password_rejected(self):
        env = dict(self.env, AUREON_KVM_PASS="wrong")
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(Exception):
                rescue.KVM().status()


# ---------------- Key agent + HID guard ----------------
class FakeSerialPort:
    script = []
    written = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def readline(self):
        if not FakeSerialPort.script:
            raise KeyboardInterrupt
        item = FakeSerialPort.script.pop(0)
        if callable(item):
            item()
            return b""
        return item

    def write(self, b):
        FakeSerialPort.written.append(b)


def fake_serial_module():
    m = types.ModuleType("serial")
    m.Serial = FakeSerialPort
    m.SerialException = OSError
    return m


class KeyAgent(unittest.TestCase):
    def run_agent(self, script, extra=()):
        FakeSerialPort.script = list(script)
        FakeSerialPort.written = []
        buf = io.StringIO()
        with mock.patch.dict(sys.modules, {"serial": fake_serial_module()}), \
                mock.patch.object(sys, "argv", ["keyagent", "--port", "X", "--dry-run", *extra]), \
                redirect_stdout(buf):
            with self.assertRaises(KeyboardInterrupt):
                keyagent.main()
        return buf.getvalue()

    def test_lock_on_panic_and_tamper(self):
        out = self.run_agent([b"HB 1\n", b"LOCK panic\n", b"LOCK tamper\n"])
        self.assertIn("would lock: panic", out)
        self.assertIn("would lock: tamper", out)

    def test_walk_away_lock_on_lost_heartbeat(self):
        clock = [1000.0]
        with mock.patch("time.monotonic", lambda: clock[0]):
            out = self.run_agent([b"HB 1\n", lambda: clock.__setitem__(0, 1010.0), b""], ["--timeout", "4"])
        self.assertIn("would lock: heartbeat lost", out)

    def test_high_report_makes_key_alert(self):
        rep = Path(tempfile.mkdtemp()) / "latest.md"
        rep.write_text("old", encoding="utf-8")
        os.utime(rep, (1, 1))

        def write_high():
            rep.write_text("# r\n\n**Severity: HIGH** - 3 events", encoding="utf-8")
        self.run_agent([b"HB 1\n", write_high, b"HB 2\n"], ["--alert-report", str(rep)])
        self.assertIn(b"ALERT\n", FakeSerialPort.written)


class HidGuard(unittest.TestCase):
    def test_learn_then_alert_lock_and_signal_key(self):
        home = Path(tempfile.mkdtemp())
        trusted = {"HID\\KBD1": "Built-in keyboard"}
        seq = [dict(trusted), dict(trusted, **{"HID\\EVIL": "USB Keyboard"}), dict(trusted, **{"HID\\EVIL": "USB Keyboard"})]
        locks = []
        FakeSerialPort.written = []
        with mock.patch.object(hidguard, "BASE", home / "hid.json"), \
                mock.patch.object(hidguard, "keyboards", lambda: seq.pop(0) if seq else (_ for _ in ()).throw(KeyboardInterrupt)), \
                mock.patch.object(keyagent, "lock_screen", lambda: locks.append(1)), \
                mock.patch.dict(sys.modules, {"serial": fake_serial_module()}), \
                mock.patch("time.sleep"), redirect_stdout(io.StringIO()) as out:
            hidguard.cli(argparse.Namespace(learn=True, key_port=None, lock=False, interval=0))
            with self.assertRaises(KeyboardInterrupt):
                hidguard.cli(argparse.Namespace(learn=False, key_port="X", lock=True, interval=0))
        self.assertEqual(locks, [1])                       # alerted once, not on every poll
        self.assertEqual(FakeSerialPort.written, [b"ALERT\n"])
        self.assertIn("new keyboard device: USB Keyboard", out.getvalue())

    def test_real_enumeration_runs(self):
        if sys.platform.startswith(("win", "linux")):
            self.assertIsInstance(hidguard.keyboards(), dict)


# ---------------- Key firmware (MicroPython) simulated on CPython ----------------
SIM = r'''
import sys, types, io
events = {"t": 0, "sleeps": 0}
class Pin:
    IN = OUT = PULL_UP = 0
    def __init__(self, n, *a):
        self.n = n; self.v = 1 if n in (14, 15) else 0
    def value(self, *a):
        if self.n == 15:   # panic pressed between t=1500..1600 ms
            return 0 if 1500 <= events["t"] < 1600 else 1
        if self.n == 14:   # tamper switch opens at t>=3000
            return 1 if events["t"] >= 3000 else 0
        return self.v
    def toggle(self): self.v ^= 1
machine = types.ModuleType("machine"); machine.Pin = Pin
t = types.ModuleType("time")
def sleep_ms(ms):
    events["t"] += ms; events["sleeps"] += 1
    if events["t"] > 4500: raise SystemExit
t.sleep_ms = sleep_ms
t.ticks_ms = lambda: events["t"]
t.ticks_diff = lambda a, b: a - b
sel = types.ModuleType("select"); sel.POLLIN = 1
class Poll:
    def register(self, *a): pass
    def poll(self, timeout): return [1] if 2000 <= events["t"] < 2200 else []
sel.poll = Poll
sys.modules.update({"machine": machine, "time": t, "select": sel})
sys.stdin = io.StringIO("PING\n")
src = open(sys.argv[1]).read()
try:
    exec(compile(src, "main.py", "exec"), {"__name__": "__main__"})
except SystemExit:
    pass
'''


class Firmware(unittest.TestCase):
    def test_simulated_run(self):
        d = tempfile.mkdtemp()
        sim = Path(d) / "sim.py"
        sim.write_text(SIM)
        r = subprocess.run([sys.executable, "-I", str(sim), str(ROOT / "key/firmware/main.py")],
                           capture_output=True, text=True, timeout=60)
        out = r.stdout.splitlines()
        self.assertIn("LOCK panic", out)
        self.assertIn("PONG", out)
        self.assertIn("LOCK tamper", out)
        self.assertEqual(out.count("LOCK tamper"), 1)      # latched, not repeated
        self.assertGreaterEqual(len([l for l in out if l.startswith("HB ")]), 3)


# ---------------- deploy stacks ----------------
class Deploy(unittest.TestCase):
    STACKS = ["shield", "cloud", "ai", "offgrid"]

    def test_compose_files(self):
        for name in self.STACKS:
            d = ROOT / "deploy" / name
            c = yaml.safe_load((d / "docker-compose.yml").read_text(encoding="utf-8"))
            self.assertTrue(c["services"], name)
            env = (d / ".env.example").read_text() if (d / ".env.example").exists() else ""
            defined = set(re.findall(r"^(\w+)=", env, re.M))
            raw = (d / "docker-compose.yml").read_text(encoding="utf-8")
            for var, default in re.findall(r"\$\{(\w+)(:-[^}]*)?\}", raw):
                self.assertTrue(default or var in defined, f"{name}: ${{{var}}} undefined")
            for svc, s in c["services"].items():
                self.assertIn("image", s, f"{name}/{svc}")
                self.assertNotRegex(s["image"], r":$", f"{name}/{svc}")
                for v in s.get("volumes", []) or []:
                    src = v.split(":")[0]
                    if src.startswith("./") and "." in Path(src).name and "data" not in src:
                        self.assertTrue((d / src).exists(), f"{name}/{svc}: missing {src}")
                for dep in s.get("depends_on", []) or []:
                    self.assertIn(dep, c["services"])

    def test_admin_uis_not_on_all_interfaces(self):
        c = yaml.safe_load((ROOT / "deploy/shield/docker-compose.yml").read_text())
        self.assertIn("127.0.0.1:51821:51821/tcp", c["services"]["wg-easy"]["ports"])
        c = yaml.safe_load((ROOT / "deploy/ai/docker-compose.yml").read_text())
        self.assertIn("127.0.0.1:11434:11434", c["services"]["ollama"]["ports"])

    def test_cross_stack_paths_line_up(self):
        ai = (ROOT / "deploy/ai/docker-compose.yml").read_text()
        self.assertIn("../shield/data:/shield", ai)
        self.assertIn("/shield/suricata/log/eve.json", ai)
        self.assertIn("/shield/opencanary/opencanary.log", ai)
        shield = (ROOT / "deploy/shield/docker-compose.yml").read_text()
        self.assertIn("./data/suricata/log:/var/log/suricata", shield)
        self.assertIn("./data/opencanary:/var/log/opencanary", shield)
        conf = json.loads((ROOT / "deploy/shield/opencanary.conf").read_text())
        self.assertEqual(conf["logger"]["kwargs"]["handlers"]["file"]["filename"], "/var/log/opencanary/opencanary.log")
        off = (ROOT / "deploy/offgrid/docker-compose.yml").read_text()
        self.assertIn("../ai/data/reports:/reports", off)

    def test_caddy_routes_match_services(self):
        caddy = (ROOT / "deploy/cloud/Caddyfile").read_text()
        c = yaml.safe_load((ROOT / "deploy/cloud/docker-compose.yml").read_text())
        for host in re.findall(r"reverse_proxy (\S+):\d+", caddy):
            self.assertIn(host, c["services"])


# ---------------- scripts ----------------
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "bash not available")
class Scripts(unittest.TestCase):
    def test_syntax(self):
        for s in ("scripts/linux/harden.sh", "scripts/linux/perf.sh", "scripts/android-termux/setup.sh"):
            r = subprocess.run([BASH, "-n", s], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_harden_dry_run_with_fake_apt(self):
        fake = Path(tempfile.mkdtemp())
        (fake / "apt-get").write_text("#!/bin/sh\necho SHOULD-NOT-RUN\nexit 1\n")
        os.chmod(fake / "apt-get", 0o755)
        bash_path = f"{fake.as_posix()}:{os.environ.get('PATH', '')}"
        env = dict(os.environ, PATH=bash_path)
        r = subprocess.run([BASH, "-c", f'export PATH="{self._msys(fake)}:$PATH"; ./scripts/linux/harden.sh'],
                           cwd=ROOT, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("would run: ufw default deny incoming", r.stdout)
        self.assertIn("kernel.kptr_restrict=2", r.stdout)
        self.assertIn("(dry run", r.stdout)
        self.assertNotIn("SHOULD-NOT-RUN", r.stdout)

    def test_apply_refuses_without_root(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("running as root")
        fake = Path(tempfile.mkdtemp())
        (fake / "apt-get").write_text("#!/bin/sh\nexit 0\n")
        os.chmod(fake / "apt-get", 0o755)
        fake_id = fake / "id"
        fake_id.write_text("#!/bin/sh\necho 1000\n")
        os.chmod(fake_id, 0o755)
        r = subprocess.run([BASH, "-c", f'export PATH="{self._msys(fake)}:$PATH"; ./scripts/linux/harden.sh --apply all'],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--apply needs root", r.stdout)

    @staticmethod
    def _msys(p):
        s = p.as_posix()
        return "/" + s[0].lower() + s[2:] if re.match(r"^[A-Za-z]:", s) else s


@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell not available")
class WindowsScript(unittest.TestCase):
    def test_parses_without_errors(self):
        ps = ("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
              f"'{ROOT / 'scripts/windows/harden.ps1'}', [ref]$null, [ref]$e) | Out-Null; $e.Count")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "0", r.stderr)


if __name__ == "__main__":
    unittest.main()
