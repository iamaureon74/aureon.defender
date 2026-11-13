"""Local AI security analyst: turns raw alerts into a short plain-language report - no cloud.

Sources (any subset):
  --suricata eve.json        Suricata/PiRogue alerts (event_type=alert)
  --canary opencanary.log    OpenCanary tripwire hits (JSON lines)
  --crowdsec decisions.json  `cscli decisions list -o json` output, or "live" to call cscli
  --wazuh alerts.json        Wazuh manager alerts (JSON lines)
  --audit                    include `aureon audit` of this machine
  --rf                       include rf wifi scan vs baseline

Pipeline: parse -> normalise -> dedupe/aggregate -> deterministic triage (always) ->
LLM summary via Ollama or any OpenAI-compatible local server (if reachable) -> markdown report.
If the model is down you still get the rule-based report.

  python -m aureon analyst --suricata eve.json --canary canary.log --since 24h --out report.md
Env: AUREON_LLM_URL (default http://127.0.0.1:11434), AUREON_LLM_MODEL (default qwen2.5:3b)
"""
import json
import os
import subprocess
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

SEV_NAME = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}


def _since_seconds(s):
    if not s:
        return None
    n, unit = int(s[:-1]), s[-1]
    return n * {"m": 60, "h": 3600, "d": 86400}[unit]


def _ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        v = v.replace("Z", "+00:00")
        if len(v) > 5 and v[-5] in "+-" and v[-3] != ":":  # +0000 -> +00:00
            v = v[:-2] + ":" + v[-2:]
        return datetime.fromisoformat(v).timestamp()
    except ValueError:
        return None


def _jsonl(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("{"):
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


# ---------------- parsers -> normalised events ----------------
def parse_suricata(path):
    for e in _jsonl(path):
        if e.get("event_type") != "alert":
            continue
        a = e.get("alert", {})
        yield {"src": "suricata", "t": _ts(e.get("timestamp")), "sev": a.get("severity", 3),
               "what": a.get("signature", "?"), "cat": a.get("category", ""),
               "from": e.get("src_ip"), "to": f"{e.get('dest_ip')}:{e.get('dest_port')}"}


CANARY_TYPES = {1001: "canary started", 2000: "FTP login attempt", 3000: "HTTP request", 3001: "HTTP login attempt",
                4000: "SSH connection", 4002: "SSH login attempt", 5001: "port scan", 5005: "SMB file open",
                6001: "Telnet login attempt", 8001: "MySQL login attempt"}


def parse_canary(path):
    for e in _jsonl(path):
        lt = e.get("logtype")
        if lt in (1001, 1002):  # startup/boot messages
            continue
        ld = e.get("logdata", {}) or {}
        user = ld.get("USERNAME")
        yield {"src": "opencanary", "t": _ts(e.get("utc_time") or e.get("local_time")), "sev": 1,
               "what": CANARY_TYPES.get(lt, f"canary event {lt}") + (f" (user '{user}')" if user else ""),
               "cat": "tripwire", "from": e.get("src_host"), "to": f"{e.get('dst_host')}:{e.get('dst_port')}"}


def parse_crowdsec(path):
    if path == "live":
        out = subprocess.run(["cscli", "decisions", "list", "-o", "json"], capture_output=True, text=True).stdout
        data = json.loads(out or "[]") or []
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or []
    for alert in data:
        for d in alert.get("decisions", []) or []:
            yield {"src": "crowdsec", "t": _ts(alert.get("created_at")), "sev": 2,
                   "what": f"{d.get('type')} {d.get('duration')}: {d.get('scenario')}", "cat": "ips",
                   "from": d.get("value"), "to": None}


def parse_wazuh(path):
    for e in _jsonl(path):
        r = e.get("rule", {})
        lvl = r.get("level", 0)
        if lvl < 5:
            continue
        yield {"src": "wazuh", "t": _ts(e.get("timestamp")), "sev": 1 if lvl >= 12 else 2 if lvl >= 8 else 3,
               "what": r.get("description", "?"), "cat": ",".join(r.get("groups", [])[:2]),
               "from": (e.get("data") or {}).get("srcip") or (e.get("agent") or {}).get("name"), "to": None}


def from_audit():
    from .audit import run_audit
    rep = run_audit()
    for r in rep["results"]:
        if r["status"] in ("FAIL", "WARN"):
            yield {"src": "audit", "t": time.time(), "sev": 1 if r["status"] == "FAIL" else 2,
                   "what": f"{r['check']}: {r['detail']}", "cat": "posture", "from": "this host", "to": None}


def from_rf():
    from . import rfwatch
    base = rfwatch._load("wifi_baseline.json")
    for s, t, d in rfwatch.wifi_check(rfwatch.scan_wifi(), base):
        yield {"src": "rf", "t": time.time(), "sev": {"HIGH": 1, "MEDIUM": 2}.get(s, 3),
               "what": f"WiFi '{t}': {d}", "cat": "wireless", "from": None, "to": None}


# ---------------- triage ----------------
def aggregate(events):
    groups = defaultdict(lambda: {"count": 0, "sources": set(), "first": None, "last": None})
    for e in events:
        k = (e["src"], e["sev"], e["what"])
        g = groups[k]
        g["count"] += 1
        if e.get("from"):
            g["sources"].add(str(e["from"]))
        if e.get("t"):
            g["first"] = min(g["first"] or e["t"], e["t"])
            g["last"] = max(g["last"] or e["t"], e["t"])
        g["cat"] = e.get("cat", "")
    rows = [{"src": k[0], "sev": k[1], "what": k[2], **v, "sources": sorted(v["sources"])} for k, v in groups.items()]
    rows.sort(key=lambda r: (r["sev"], -r["count"]))
    return rows


def correlate(rows):
    """Attackers seen by more than one sensor are the most important finding."""
    seen = defaultdict(set)
    for r in rows:
        for ip in r["sources"]:
            seen[ip].add(r["src"])
    return {ip: sorted(s) for ip, s in seen.items() if len(s) > 1 and ip != "this host"}


def overall(rows, multi):
    if any(r["src"] == "opencanary" for r in rows) or multi or any(r["sev"] == 1 and r["src"] != "audit" for r in rows):
        return "HIGH"
    if any(r["sev"] <= 2 for r in rows):
        return "MEDIUM"
    return "LOW" if rows else "NONE"


def rule_report(rows, multi, window):
    sev = overall(rows, multi)
    out = [f"# Aureon security report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
           "", f"**Severity: {sev}** - {sum(r['count'] for r in rows)} events, {len(rows)} distinct, window {window or 'all'}", ""]
    if multi:
        out += ["## Seen by multiple sensors", ""]
        out += [f"- `{ip}` -> {', '.join(s)}" for ip, s in multi.items()] + [""]
    out += ["## Top findings", "", "| Sev | Source | Finding | Count | From |", "|---|---|---|---|---|"]
    for r in rows[:25]:
        frm = ", ".join(r["sources"][:3]) + (" ..." if len(r["sources"]) > 3 else "")
        out.append(f"| {SEV_NAME.get(r['sev'], r['sev'])} | {r['src']} | {r['what']} | {r['count']} | {frm} |")
    return "\n".join(out) + "\n", sev


# ---------------- LLM ----------------
PROMPT = """You are the Aureon home-network security analyst. Below is a pre-triaged digest of alerts
from the user's own devices (Suricata IDS, OpenCanary tripwires, CrowdSec, Wazuh EDR, posture audit, WiFi watch).
Write for a non-expert, max 220 words, in markdown:
1. One-line verdict (is anything actually wrong?).
2. The 3 most important findings and why they matter.
3. Concrete next steps (commands or settings) - defensive only.
Rules: OpenCanary hits are near-certain intrusions on the LAN. Many IDS alerts are noise (e.g. ET POLICY, ET INFO) - say so.
Do not invent events not in the digest.

DIGEST:
"""


def llm(digest):
    url = os.environ.get("AUREON_LLM_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("AUREON_LLM_MODEL", "qwen2.5:3b")
    if "/v1" in url:  # OpenAI-compatible (LocalAI, llama.cpp server, LM Studio)
        body = {"model": model, "messages": [{"role": "user", "content": PROMPT + digest}], "temperature": 0.2}
        path, pick = "/chat/completions", lambda j: j["choices"][0]["message"]["content"]
    else:  # Ollama
        body = {"model": model, "prompt": PROMPT + digest, "stream": False, "options": {"temperature": 0.2}}
        path, pick = "/api/generate", lambda j: j["response"]
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return pick(json.loads(r.read())).strip()


def run(a):
    cutoff = time.time() - _since_seconds(a.since) if a.since else None
    events = []
    for path, fn in ((a.suricata, parse_suricata), (a.canary, parse_canary),
                     (a.crowdsec, parse_crowdsec), (a.wazuh, parse_wazuh)):
        if path and (path == "live" or os.path.exists(path)):
            events += list(fn(path))
        elif path:
            print(f"skip {path}: not found")
    if a.audit:
        events += list(from_audit())
    if a.rf:
        events += list(from_rf())
    if cutoff:
        events = [e for e in events if not e.get("t") or e["t"] >= cutoff]
    rows = aggregate(events)
    multi = correlate(rows)
    report, sev = rule_report(rows, multi, a.since)
    if rows and not a.no_llm:
        try:
            report = report.replace("\n\n## ", "\n\n## AI summary\n\n" + llm(report) + "\n\n## ", 1)
        except Exception as e:
            report += f"\n_(local model unavailable: {e.__class__.__name__}; showing rule-based triage only)_\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)
    return 2 if sev == "HIGH" else 0
