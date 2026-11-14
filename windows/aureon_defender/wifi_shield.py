"""Wi-Fi capability and disconnect observations, not attack attribution.

PMF resists forged management frames; it cannot override a real AP or jamming.
Profile preference affects this laptop only and does not allocate bandwidth.
A monitor-mode Pi sensor can add radio evidence, not establish a person identity.
"""
import os
import re
import subprocess

NOWIN = 0x08000000

PI_SENSOR = {
    "what": "A Raspberry Pi that watches the air for deauth floods and rogue access points, full time.",
    "parts": "Raspberry Pi 3/4/5, plus a Wi-Fi adapter that supports monitor mode (e.g. Alfa AWUS036ACM).",
    "software": "nzyme (nzyme.org) or Kismet — both free and open source. nzyme baselines normal deauth volume and alerts on floods.",
    "link": "https://www.nzyme.org",
}

# disconnect reason codes Windows logs (event 8003) that mean 'something told me to leave'
KICK_REASONS = {2: "previous authentication no longer valid", 3: "deauthenticated: leaving",
                6: "class-2 frame from non-authenticated station", 7: "class-3 frame from non-associated station",
                4: "disassociated: inactivity", 8: "disassociated: station leaving"}


def _run(args, timeout=12):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN,
                              encoding="utf-8", errors="ignore").stdout
    except Exception:
        return ""


def interface():
    """Current connection: ssid, bssid, band, auth, signal, channel."""
    out = _run(["netsh", "wlan", "show", "interfaces"])
    f = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "ssid":
            f["ssid"] = v
        elif k == "bssid":
            f["bssid"] = v
        elif k == "signal":
            f["signal"] = v
        elif k == "radio type":
            f["radio"] = v
        elif k == "band":
            f["band"] = v
        elif k == "channel":
            f["channel"] = v
        elif k == "authentication":
            f["auth"] = v
        elif k == "state":
            f["state"] = v
    return f


def pmf_supported():
    """Does this Wi-Fi adapter support 802.11w Protected Management Frames (the anti-deauth defence)?"""
    out = _run(["netsh", "wlan", "show", "drivers"])
    m = re.search(r"802\.11w.*?:\s*(.+)", out)
    if m:
        value = m.group(1).strip().lower()
        if value in ("yes", "supported"):
            return True
        if value in ("no", "not supported", "unsupported"):
            return False
    return None


def kick_events(hours=24):
    """Forced-disconnect events from Windows' own Wi-Fi log in the last `hours`."""
    if os.name != "nt":
        return []
    ps = (r"$s=(Get-Date).AddHours(-%d);"
          r"Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-WLAN-AutoConfig/Operational';Id=8003;StartTime=$s} "
          r"-ErrorAction SilentlyContinue | ForEach-Object { $_.TimeCreated.ToString('o')+'|'+($_.Properties[0].Value) }") % hours
    out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=20)
    ev = []
    for line in out.splitlines():
        if "|" in line:
            t, _, reason = line.partition("|")
            ev.append({"t": t, "reason": reason.strip()})
    return ev


def status():
    iface = interface()
    pmf = pmf_supported()
    kicks = kick_events(24)
    # Driver capability and an authentication label do not establish negotiated PMF.
    protected = None
    flood = len(kicks) >= 6
    findings = []
    if pmf is False:
        findings.append({"level": "medium", "text": "This Wi-Fi adapter doesn't support Protected Management Frames, so forged kick-off packets can knock you offline. A newer USB Wi-Fi adapter fixes it."})
    elif pmf and not protected:
        findings.append({"level": "low", "text": "Your adapter supports PMF; negotiated protection is unverified. Check PMF-required on your managed router. WPA2 can also use PMF. The real access point can still disconnect clients."})
    if flood:
        findings.append({"level": "low", "text": f"{len(kicks)} disconnect events in 24 hours. Roaming, signal loss, sleep and AP policy can cause these; they do not establish an attack or sender identity."})
    return {"interface": iface, "pmf_supported": pmf, "protected": protected,
            "kicks_24h": len(kicks), "kicks": kicks[:20], "findings": findings, "pi_sensor": PI_SENSOR}


def favor_my_network():
    """Raise the current network to the top of Windows' auto-connect order so your devices prefer it and stay on it."""
    iface = interface()
    ssid = iface.get("ssid")
    if not ssid:
        raise RuntimeError("not connected to Wi-Fi right now")
    _run(["netsh", "wlan", "set", "profileparameter", f"name={ssid}", "connectionmode=auto"])
    _run(["netsh", "wlan", "set", "profileorder", f"name={ssid}", "interface=Wi-Fi", "priority=1"])
    return {"ok": True, "ssid": ssid, "message": f"Windows will now prefer “{ssid}” and reconnect to it first."}
