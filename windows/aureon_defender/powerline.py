"""Read-only HomePlug inventory. Reachability is not electrical topology."""
import os
import re
import shutil
import subprocess

PI_AUDIT = {
    "what": "Inventory reachable compatible HomePlug adapters on an authorized network.",
    "parts": "Pi, Ethernet and a HomePlug adapter. Circuit mapping needs separate tracing.",
    "software": "Qualcomm open-plc-utils; discovery cannot identify people, raw loads, all outlets or network keys.",
    "link": "https://github.com/qca/open-plc-utils",
}


def _run(args, timeout=15):
    kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", **kw)
        return p.stdout, p.returncode
    except (OSError, subprocess.TimeoutExpired):
        return "", -1


def adapters():
    # Generic Ethernet NIC names cannot establish whether a HomePlug bridge exists.
    return []


def toolkit():
    return shutil.which("amplist")


def nodes(interface=None):
    tool = toolkit()
    if not tool:
        return {"available": False, "status": "tool_missing", "nodes": []}
    out, code = _run([tool] + (["-i", interface] if interface else []))
    macs = sorted(set(re.findall(r"\b(?:[0-9A-F]{2}:){5}[0-9A-F]{2}\b", out.upper())))
    return {"available": True, "status": "observed" if code == 0 else "collection_failed",
            "nodes": [{"mac": m, "identity": "unknown", "circuit": "unknown"} for m in macs] if code == 0 else []}


def audit():
    n = nodes()
    findings = [{"level": "low", "title": "HomePlug visibility is limited",
                 "text": "No discovery result rules out powerline networking elsewhere. Reachable MAC addresses do not establish breaker membership, ownership or wiring routes."}]
    if n["status"] == "collection_failed":
        findings.append({"level": "medium", "title": "HomePlug collection failed",
                         "text": "Check permissions, interface and compatible hardware. This is not a clean result."})
    return {"present": bool(n["nodes"]), "adapters": [], "nodes": n, "findings": findings,
            "attacker_path": ["A shared powerline medium can expose an inadequately isolated network; actual reach depends on wiring, hardware and pairing. No intrusion is established here."],
            "how_to_patch": ["Verify secure pairing and a unique network key using the manufacturer's supported tool; key state is unverified here.",
                             "Update firmware, isolate untrusted segments and remove unused bridges.",
                             "Retain end-to-end encryption."],
            "toolkit": bool(toolkit()), "pi_audit": PI_AUDIT}
