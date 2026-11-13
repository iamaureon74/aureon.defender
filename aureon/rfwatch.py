"""Radio-environment watch: rogue WiFi (evil twin / downgrade) and fake cell tower (IMSI catcher) heuristics.

Passive only: it reads what the OS / radio already reports and never transmits.

  python -m aureon rf wifi --learn            record trusted networks around you (home, office)
  python -m aureon rf wifi                    scan and compare against the baseline
  python -m aureon rf cell --learn            (Android/Termux, needs Termux:API) record normal cells
  python -m aureon rf cell                    compare current cells to the baseline
  python -m aureon rf gsm --kal kal.txt       compare a kalibrate-rtl scan (`kal -s GSM900 > kal.txt`)

Inspired by Kismet (rogue AP detection), AIMSICD/SnoopSnitch-style cell heuristics, gr-gsm and
kalibrate-rtl. These are heuristics: a hit means "look closer", not proof. A real IMSI catcher
check needs an SDR survey (gr-gsm) and comparison with public cell databases.
"""
import json
import platform
import re
import subprocess
from pathlib import Path

HOME = Path.home() / ".aureon"
SEC_RANK = {"open": 0, "wep": 1, "wpa": 2, "wpa2": 3, "wpa3": 4}


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _norm_sec(s):
    s = s.lower()
    for k in ("wpa3", "wpa2", "wpa", "wep"):
        if k in s or (k == "wpa3" and "sae" in s):
            return k
    return "open" if s in ("", "--", "none", "open") or "open" in s else s


# ---------------- WiFi ----------------
def parse_netsh(out):
    nets, ssid, auth = [], None, ""
    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"^SSID \d+ : (.*)$", line)
        if m:
            ssid = m.group(1)
            continue
        m = re.match(r"^Authentication\s*: (.*)$", line)
        if m:
            auth = m.group(1)
            continue
        m = re.match(r"^BSSID \d+\s*: ([0-9a-f:]{17})", line, re.I)
        if m and ssid is not None:
            nets.append({"ssid": ssid, "bssid": m.group(1).lower(), "sec": _norm_sec(auth), "signal": None, "chan": None})
            continue
        m = re.match(r"^Signal\s*: (\d+)%", line)
        if m and nets:
            nets[-1]["signal"] = int(m.group(1))
        m = re.match(r"^Channel\s*: (\d+)", line)
        if m and nets:
            nets[-1]["chan"] = int(m.group(1))
    return nets


def parse_nmcli(out):
    nets = []
    for line in out.splitlines():
        parts = re.split(r"(?<!\\):", line)
        if len(parts) < 5:
            continue
        # nmcli -t escapes ':' inside fields as '\:' so the BSSID stays one field
        ssid, bssid, chan, sig, sec = parts[0], parts[1], parts[2], parts[3], ":".join(parts[4:])
        nets.append({"ssid": ssid.replace("\\:", ":"), "bssid": bssid.replace("\\", "").lower(),
                     "chan": int(chan or 0) if chan.isdigit() else 0,
                     "signal": int(sig or 0) if sig.isdigit() else 0, "sec": _norm_sec(sec)})
    return nets


def scan_wifi():
    s = platform.system()
    if s == "Windows":
        return parse_netsh(_run(["netsh", "wlan", "show", "networks", "mode=bssid"]))
    if s == "Linux":
        return parse_nmcli(_run(["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"]))
    raise SystemExit("WiFi scan supports Windows (netsh) and Linux (nmcli)")


def wifi_check(nets, baseline):
    """baseline: {ssid: {"bssids": [...], "sec": "wpa2"}}"""
    alerts = []
    by_ssid = {}
    for n in nets:
        by_ssid.setdefault(n["ssid"], []).append(n)
    for ssid, aps in by_ssid.items():
        if not ssid:
            continue
        known = baseline.get(ssid)
        secs = {a["sec"] for a in aps}
        if len(secs) > 1:
            alerts.append(("HIGH", ssid, f"same name broadcast with different security {sorted(secs)} - classic evil twin"))
        if not known:
            continue
        for a in aps:
            if SEC_RANK.get(a["sec"], 5) < SEC_RANK.get(known["sec"], 5):
                alerts.append(("HIGH", ssid, f"{a['bssid']} offers {a['sec']} but your network is {known['sec']} - downgrade / rogue AP"))
            elif a["bssid"] not in known["bssids"]:
                alerts.append(("MEDIUM", ssid, f"unknown access point {a['bssid']} (ch {a['chan']}, {a['signal']}%) using a trusted name"))
    return alerts


def wifi_learn(nets, baseline):
    for n in nets:
        if not n["ssid"]:
            continue
        b = baseline.setdefault(n["ssid"], {"bssids": [], "sec": n["sec"]})
        if n["bssid"] not in b["bssids"]:
            b["bssids"].append(n["bssid"])
        if SEC_RANK.get(n["sec"], 0) > SEC_RANK.get(b["sec"], 0):
            b["sec"] = n["sec"]
    return baseline


# ---------------- Cellular (Termux:API) ----------------
def cell_key(c):
    t = c.get("type", "?")
    ident = c.get("ci") or c.get("cid") or c.get("nci") or c.get("pci")
    return f"{t}:{c.get('mcc')}-{c.get('mnc')}:{c.get('tac') or c.get('lac')}:{ident}"


def scan_cells():
    out = _run(["termux-telephony-cellinfo"])
    if not out.strip():
        raise SystemExit("needs Android + Termux + Termux:API app (pkg install termux-api)")
    return json.loads(out)


def cell_check(cells, baseline):
    """baseline: {"cells": {key: count}, "types": {type: count}, "areas": [tac/lac...]}"""
    alerts = []
    reg = [c for c in cells if c.get("registered")]
    for c in reg:
        k = cell_key(c)
        if c.get("type") == "gsm" and baseline.get("types", {}).get("lte", 0) + baseline.get("types", {}).get("nr", 0) > 0:
            alerts.append(("HIGH", k, "registered on 2G (GSM) where you normally have 4G/5G - forced downgrade is the main IMSI-catcher trick"))
        if k not in baseline.get("cells", {}):
            alerts.append(("MEDIUM", k, "serving cell never seen at this location"))
        area = c.get("tac") or c.get("lac")
        if area is not None and baseline.get("areas") and area not in baseline["areas"]:
            alerts.append(("MEDIUM", k, f"location/tracking area {area} is new - fake cells often use an unusual LAC/TAC"))
        dbm = c.get("dbm")
        if isinstance(dbm, int) and dbm > -55:
            alerts.append(("LOW", k, f"unusually strong signal {dbm} dBm - a transmitter may be very close"))
    if cells and not any(c.get("type") != "gsm" for c in cells) and baseline.get("types", {}).get("lte"):
        alerts.append(("HIGH", "all", "only 2G cells visible - possible jamming of 4G/5G"))
    return alerts


def cell_learn(cells, baseline):
    baseline.setdefault("cells", {})
    baseline.setdefault("types", {})
    baseline.setdefault("areas", [])
    for c in cells:
        k = cell_key(c)
        baseline["cells"][k] = baseline["cells"].get(k, 0) + 1
        baseline["types"][c.get("type", "?")] = baseline["types"].get(c.get("type", "?"), 0) + 1
        a = c.get("tac") or c.get("lac")
        if a is not None and a not in baseline["areas"]:
            baseline["areas"].append(a)
    return baseline


# ---------------- GSM survey via kalibrate-rtl ----------------
def parse_kal(text):
    """'chan: 37 (942.4MHz - 13.474kHz)  power: 191548.31' -> {37: 191548.31}"""
    return {int(m.group(1)): float(m.group(2))
            for m in re.finditer(r"chan:\s*(\d+)\s*\([^)]*\)\s*power:\s*([\d.]+)", text)}


def gsm_check(chans, baseline):
    alerts = []
    if not baseline:
        return alerts
    top = max(baseline.values())
    for ch, p in chans.items():
        if str(ch) not in baseline and p > 0.5 * top:
            alerts.append(("HIGH", f"ARFCN {ch}", f"new strong GSM carrier (power {p:.0f}) not in baseline"))
        elif str(ch) in baseline and p > 5 * baseline[str(ch)]:
            alerts.append(("MEDIUM", f"ARFCN {ch}", f"power jumped {p / baseline[str(ch)]:.1f}x vs baseline"))
    for ch in baseline:
        if int(ch) not in chans:
            alerts.append(("LOW", f"ARFCN {ch}", "baseline carrier missing"))
    return alerts


# ---------------- glue ----------------
def _load(name):
    p = HOME / name
    return json.loads(p.read_text()) if p.exists() else {}


def _save(name, data):
    HOME.mkdir(exist_ok=True)
    (HOME / name).write_text(json.dumps(data, indent=1))


def _report(alerts, as_json):
    if as_json:
        print(json.dumps([{"severity": s, "target": t, "detail": d} for s, t, d in alerts], indent=1))
    elif not alerts:
        print("no anomalies against baseline")
    else:
        for s, t, d in alerts:
            print(f"[{s:6}] {t}: {d}")
    return 1 if any(s == "HIGH" for s, _, _ in alerts) else 0


def cli(a):
    if a.mode == "wifi":
        nets = scan_wifi()
        base = _load("wifi_baseline.json")
        if a.learn:
            _save("wifi_baseline.json", wifi_learn(nets, base))
            print(f"learned {len({n['ssid'] for n in nets if n['ssid']})} networks / {len(nets)} access points")
            return 0
        if not base:
            print("no baseline yet: run with --learn on networks you trust")
        print(f"scanned {len(nets)} access points")
        return _report(wifi_check(nets, base), a.json)
    if a.mode == "cell":
        cells = scan_cells()
        base = _load("cell_baseline.json")
        if a.learn:
            _save("cell_baseline.json", cell_learn(cells, base))
            print(f"learned {len(cells)} cells")
            return 0
        return _report(cell_check(cells, base), a.json)
    if a.mode == "gsm":
        chans = parse_kal(Path(a.kal).read_text())
        base = _load("gsm_baseline.json")
        if a.learn:
            _save("gsm_baseline.json", {str(k): v for k, v in chans.items()})
            print(f"learned {len(chans)} GSM carriers")
            return 0
        return _report(gsm_check(chans, base), a.json)
