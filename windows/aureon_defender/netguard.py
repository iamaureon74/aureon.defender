"""Network guard: silent, automatic, machine-wide (run by the SYSTEM engine). Plain rules, no AI.

1. Ports that let strangers in, or that broadcast who you are, are closed where they are a risk:
     * on PUBLIC networks (cafes, hotels, airports, any open wi-fi) inbound file sharing, remote desktop, remote
       management, VNC, telnet and FTP are blocked, and the discovery chatter that announces this PC's name,
       shares and devices to everyone nearby (NetBIOS, LLMNR, mDNS, SSDP/UPnP, WS-Discovery) is blocked both ways.
     * on home / work (PRIVATE) networks only telnet, FTP and VNC inbound are blocked; printers, NAS and casting
       keep working, because that hardware needs discovery and SMB.
   Rules live in one firewall group, "aureon.defender guard", so they are easy to find and to remove.
2. Open wi-fi (no password) is always treated as PUBLIC, even if it was once marked private.
3. A fake copy of a network you know: if this PC is connected to a network name it has only ever seen with a
   password, but this access point is open or weaker, it disconnects. Windows then reconnects to the real one.
"""
import json
import os
import subprocess

GROUP = "aureon.defender guard"
NOWIN = 0x08000000

# (name, direction, protocol, ports, profiles, why)
RULES = [
    ("inbound file sharing (SMB)", "Inbound", "TCP", "139,445", "Public", "strangers can't reach your shared files"),
    ("inbound windows rpc", "Inbound", "TCP", "135", "Public", "no remote windows management calls"),
    ("inbound remote desktop", "Inbound", "TCP", "3389", "Public", "no remote desktop logins from the network"),
    ("inbound remote management", "Inbound", "TCP", "5985,5986", "Public", "no powershell remoting"),
    ("inbound vnc", "Inbound", "TCP", "5900-5903", "Any", "no remote screen viewers"),
    ("inbound telnet and ftp", "Inbound", "TCP", "21,23", "Any", "old unencrypted logins closed"),
    ("netbios name and datagram", "Inbound", "UDP", "137,138", "Public", "your pc's name isn't announced"),
    ("netbios name and datagram out", "Outbound", "UDP", "137,138", "Public", "your pc's name isn't announced"),
    ("llmnr", "Inbound", "UDP", "5355", "Public", "no name-poisoning answers (password-hash theft)"),
    ("llmnr out", "Outbound", "UDP", "5355", "Public", "no name-poisoning answers (password-hash theft)"),
    ("mdns", "Inbound", "UDP", "5353", "Public", "devices nearby can't list this pc"),
    ("ssdp upnp", "Inbound", "UDP", "1900", "Public", "no upnp discovery from strangers"),
    ("ssdp upnp out", "Outbound", "UDP", "1900", "Public", "no upnp discovery to strangers"),
    ("ws-discovery", "Inbound", "UDP", "3702", "Public", "no device discovery from strangers"),
]

WEAK_AUTH = ("open", "wep", "none", "")


def _ps(script, timeout=60):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                           text=True, timeout=timeout, creationflags=NOWIN if os.name == "nt" else 0)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError) as ex:
        return 1, str(ex)


def rule_script(existing):
    """PowerShell that adds only the missing rules. `existing` is the set of DisplayNames already in the group."""
    lines = []
    for name, direction, proto, ports, profile, _ in RULES:
        display = f"aureon guard: {name}"
        if display in existing:
            continue
        prof = "Any" if profile == "Any" else profile
        port = "-RemotePort" if direction == "Outbound" else "-LocalPort"
        lines.append(f"New-NetFirewallRule -DisplayName '{display}' -Group '{GROUP}' -Direction {direction} -Action Block "
                     f"-Protocol {proto} {port} {ports} -Profile {prof} | Out-Null")
    return "; ".join(lines)


def ensure_rules(ps=_ps):
    """Add missing guard rules. Returns the names added (empty when everything is in place)."""
    code, out = ps(f"Get-NetFirewallRule -Group '{GROUP}' -ErrorAction SilentlyContinue | Select -Expand DisplayName | ConvertTo-Json -Compress")
    try:
        have = json.loads(out) if out else []
    except ValueError:
        have = []
    have = set([have] if isinstance(have, str) else have)
    script = rule_script(have)
    if not script:
        return []
    code, _ = ps(script, timeout=120)
    if code != 0:
        raise OSError("firewall rules could not be added")
    return [n for n, *_ in RULES if f"aureon guard: {n}" not in have]


def remove_rules(ps=_ps):
    return ps(f"Remove-NetFirewallRule -Group '{GROUP}' -ErrorAction SilentlyContinue")[0] == 0


def weak(auth):
    a = (auth or "").strip().lower()
    return a in WEAK_AUTH or a.startswith("open") or "wep" in a


def decide_wifi(iface, known):
    """iface: {ssid, bssid, auth, state}; known: {ssid: {"secured": bool, "bssids": [...]}}.
    Returns (actions, updated_known). actions: 'public' (treat as public) and/or 'disconnect' (fake copy)."""
    ssid, auth = iface.get("ssid"), iface.get("auth", "")
    if not ssid or (iface.get("state") or "").lower() not in ("connected", ""):
        return [], known
    known = {k: dict(v) for k, v in known.items()}
    seen = known.setdefault(ssid, {"secured": not weak(auth), "bssids": []})
    actions = []
    if weak(auth):
        actions.append("public")
        if seen.get("secured"):
            actions.append("disconnect")                     # we have only ever seen this name with a password
    elif not seen.get("secured"):
        seen["secured"] = True
    b = (iface.get("bssid") or "").lower()
    if b and b not in seen["bssids"] and "disconnect" not in actions:
        seen["bssids"] = (seen["bssids"] + [b])[-20:]
    return actions, known


def set_public(ps=_ps):
    """Mark the current wi-fi connection as Public (firewall's strict profile, no discovery)."""
    code, out = ps("Get-NetConnectionProfile | ? { $_.InterfaceAlias -match 'Wi-?Fi|WLAN|Wireless' -and $_.NetworkCategory -ne 'Public' } | "
                   "Set-NetConnectionProfile -NetworkCategory Public -PassThru | Select -Expand Name")
    return code == 0 and bool(out)


def disconnect():
    try:
        subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, timeout=15, creationflags=NOWIN if os.name == "nt" else 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
