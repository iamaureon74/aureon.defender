"""RF watch, analyst (incl. fake LLM servers), mesh helpers."""
import argparse
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aureon import analyst, mesh, rfwatch  # noqa: E402

NETSH = """
SSID 1 : HomeNet
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : aa:bb:cc:00:00:01
         Signal             : 88%
         Radio type         : 802.11ax
         Channel            : 36
SSID 2 : HomeNet
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
    BSSID 1                 : de:ad:be:ef:00:02
         Signal             : 99%
         Channel            : 6
SSID 3 : Cafe
    Authentication          : WPA3-Personal
    BSSID 1                 : 11:22:33:44:55:66
         Signal             : 40%
         Channel            : 1
"""


class WiFi(unittest.TestCase):
    def test_netsh_parse(self):
        n = rfwatch.parse_netsh(NETSH)
        self.assertEqual([x["sec"] for x in n], ["wpa2", "open", "wpa3"])
        self.assertEqual(n[0]["signal"], 88)
        self.assertEqual(n[1]["chan"], 6)

    def test_nmcli_parse_escaped(self):
        n = rfwatch.parse_nmcli("My\\:Net:AA\\:BB\\:CC\\:DD\\:EE\\:FF:11:70:WPA2 WPA3\n")
        self.assertEqual(n[0]["ssid"], "My:Net")
        self.assertEqual(n[0]["bssid"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(n[0]["sec"], "wpa3")

    def test_evil_twin_and_downgrade(self):
        n = rfwatch.parse_netsh(NETSH)
        base = rfwatch.wifi_learn([n[0]], {})
        alerts = rfwatch.wifi_check(n, base)
        kinds = " ".join(a[2] for a in alerts)
        self.assertIn("evil twin", kinds)
        self.assertIn("downgrade", kinds)
        self.assertTrue(all(a[1] == "HomeNet" for a in alerts))   # Cafe not in baseline -> ignored

    def test_new_bssid_same_security(self):
        n = rfwatch.parse_netsh(NETSH)
        base = rfwatch.wifi_learn([n[0]], {})
        rogue = dict(n[0], bssid="00:00:00:00:00:99")
        alerts = rfwatch.wifi_check([n[0], rogue], base)
        self.assertEqual([a[0] for a in alerts], ["MEDIUM"])

    def test_clean_scan_no_alerts(self):
        n = rfwatch.parse_netsh(NETSH)
        base = rfwatch.wifi_learn(n, {})
        self.assertEqual([a for a in rfwatch.wifi_check([n[0], n[2]], base)], [])


class Cell(unittest.TestCase):
    LTE = {"type": "lte", "registered": True, "mcc": 310, "mnc": 260, "tac": 100, "ci": 5, "dbm": -95}

    def test_downgrade_new_cell_new_area(self):
        base = rfwatch.cell_learn([self.LTE], {})
        fake = {"type": "gsm", "registered": True, "mcc": 310, "mnc": 260, "lac": 999, "cid": 7, "dbm": -50}
        sev = [a[0] for a in rfwatch.cell_check([fake], base)]
        self.assertEqual(sev.count("HIGH"), 2)       # 2G downgrade + only-2G visible
        self.assertIn("MEDIUM", sev)
        self.assertIn("LOW", sev)                    # very strong signal

    def test_known_cell_is_quiet(self):
        base = rfwatch.cell_learn([self.LTE], {})
        self.assertEqual(rfwatch.cell_check([self.LTE], base), [])


class GSM(unittest.TestCase):
    KAL = "kal: Scanning for GSM-900 base stations.\n    chan: 37 (942.4MHz - 13.474kHz)\tpower: 191548.31\n    chan: 51 (945.2MHz + 1.1kHz)\tpower: 9000.00\n"

    def test_parse(self):
        self.assertEqual(rfwatch.parse_kal(self.KAL), {37: 191548.31, 51: 9000.0})

    def test_new_strong_carrier(self):
        base = {"37": 180000.0, "51": 9000.0}
        a = rfwatch.gsm_check({37: 190000.0, 51: 9500.0, 60: 150000.0}, base)
        self.assertEqual([(x[0], x[1]) for x in a], [("HIGH", "ARFCN 60")])

    def test_power_jump_and_missing(self):
        a = rfwatch.gsm_check({37: 190000.0, 51: 60000.0}, {"37": 180000.0, "51": 9000.0, "80": 5000.0})
        self.assertEqual(sorted(x[0] for x in a), ["LOW", "MEDIUM"])


# ---------------- analyst ----------------
def _fixtures(d):
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000000+0000", time.gmtime())
    old = "2020-01-01T00:00:00.000000+0000"
    with open(f"{d}/eve.json", "w") as f:
        for _ in range(30):
            f.write(json.dumps({"timestamp": now, "event_type": "alert", "src_ip": "203.0.113.9", "dest_ip": "192.168.1.10",
                                "dest_port": 22, "alert": {"severity": 2, "signature": "ET SCAN SSH Scan", "category": "scan"}}) + "\n")
        f.write(json.dumps({"timestamp": old, "event_type": "alert", "src_ip": "198.51.100.1", "dest_ip": "x", "dest_port": 1,
                            "alert": {"severity": 1, "signature": "OLD", "category": "x"}}) + "\n")
        f.write(json.dumps({"timestamp": now, "event_type": "dns"}) + "\nnot json\n")
    with open(f"{d}/canary.log", "w") as f:
        f.write(json.dumps({"logtype": 1001, "utc_time": "2020-01-01 00:00:00.0"}) + "\n")
        f.write(json.dumps({"logtype": 4002, "utc_time": time.strftime("%Y-%m-%d %H:%M:%S.000000", time.gmtime()),
                            "src_host": "203.0.113.9", "dst_host": "192.168.1.20", "dst_port": 2222,
                            "logdata": {"USERNAME": "root"}}) + "\n")
    with open(f"{d}/cs.json", "w") as f:
        json.dump([{"created_at": now, "decisions": [{"type": "ban", "duration": "4h", "scenario": "crowdsecurity/ssh-bf",
                                                       "value": "203.0.113.9"}]}], f)
    with open(f"{d}/wazuh.json", "w") as f:
        f.write(json.dumps({"timestamp": now, "rule": {"level": 12, "description": "Rootkit detected", "groups": ["rootcheck"]},
                            "agent": {"name": "laptop"}}) + "\n")
        f.write(json.dumps({"timestamp": now, "rule": {"level": 3, "description": "noise"}}) + "\n")


def _args(d, **kw):
    a = dict(suricata=f"{d}/eve.json", canary=f"{d}/canary.log", crowdsec=f"{d}/cs.json", wazuh=f"{d}/wazuh.json",
             since="2h", out=f"{d}/out/report.md", audit=False, rf=False, no_llm=False)
    a.update(kw)
    return argparse.Namespace(**a)


class FakeLLM(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLLM.seen.append((self.path, body))
        if self.path == "/api/generate":
            out = {"response": "VERDICT: real intrusion attempt from 203.0.113.9"}
        else:
            out = {"choices": [{"message": {"content": "VERDICT (openai): intrusion"}}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class Analyst(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        _fixtures(self.d)

    def run_analyst(self, a, env):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env), redirect_stdout(buf):
            rc = analyst.run(a)
        return rc, Path(a.out).read_text(encoding="utf-8")

    def test_rule_based_triage(self):
        rc, rep = self.run_analyst(_args(self.d, no_llm=True), {})
        self.assertEqual(rc, 2)
        self.assertIn("**Severity: HIGH**", rep)
        self.assertIn("`203.0.113.9` -> crowdsec, opencanary, suricata", rep)
        self.assertIn("| HIGH | opencanary | SSH login attempt (user 'root') | 1 |", rep)
        self.assertIn("| MEDIUM | suricata | ET SCAN SSH Scan | 30 |", rep)
        self.assertIn("Rootkit detected", rep)
        self.assertNotIn("OLD", rep)        # outside --since window
        self.assertNotIn("noise", rep)      # wazuh level < 5

    def test_llm_down_falls_back(self):
        rc, rep = self.run_analyst(_args(self.d), {"AUREON_LLM_URL": "http://127.0.0.1:9"})
        self.assertIn("local model unavailable", rep)
        self.assertIn("## Top findings", rep)

    def _serve(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeLLM)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}"

    def test_ollama_summary_inserted(self):
        url = self._serve()
        rc, rep = self.run_analyst(_args(self.d), {"AUREON_LLM_URL": url, "AUREON_LLM_MODEL": "m"})
        self.assertIn("## AI summary\n\nVERDICT: real intrusion attempt", rep)
        path, body = FakeLLM.seen[-1]
        self.assertEqual(path, "/api/generate")
        self.assertIn("203.0.113.9", body["prompt"])
        self.assertFalse(body["stream"])

    def test_openai_compatible_summary(self):
        url = self._serve()
        rc, rep = self.run_analyst(_args(self.d), {"AUREON_LLM_URL": url + "/v1"})
        self.assertIn("VERDICT (openai)", rep)
        self.assertEqual(FakeLLM.seen[-1][0], "/v1/chat/completions")

    def test_empty_inputs(self):
        a = _args(self.d, suricata=None, canary=None, crowdsec=None, wazuh=None)
        rc, rep = self.run_analyst(a, {})
        self.assertEqual(rc, 0)
        self.assertIn("**Severity: NONE**", rep)


class Mesh(unittest.TestCase):
    def test_headline_and_chunks(self):
        h = mesh.headline("# Aureon security report - x\n\n**Severity: HIGH** - 3 events\n## more")
        self.assertEqual(h, "Aureon security report - x | **Severity: HIGH** - 3 events")
        self.assertEqual([len(c) for c in mesh.chunks("a" * 450)], [200, 200, 50])

    def test_send_uses_meshtastic(self):
        sent = []

        class Iface:
            def __init__(self, devPath):
                self.dev = devPath

            def sendText(self, t):
                sent.append(t)

            def close(self):
                sent.append("CLOSED")
        fake_pkg = mock.MagicMock()
        fake_si = mock.MagicMock(SerialInterface=Iface)
        with mock.patch.dict(sys.modules, {"meshtastic": fake_pkg, "meshtastic.serial_interface": fake_si}), \
                mock.patch("time.sleep"):
            fake_pkg.serial_interface = fake_si
            mesh.send("COM7", "x" * 250)
        self.assertEqual([len(s) for s in sent[:2]], [200, 50])
        self.assertEqual(sent[-1], "CLOSED")


if __name__ == "__main__":
    unittest.main()
