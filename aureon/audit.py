"""Read-only security & performance posture check for Windows, Linux and macOS.

Never changes anything. Each check returns (status, detail) where status is
PASS / WARN / FAIL / INFO / SKIP.
"""
import os
import platform
import re
import shutil
import subprocess

SYSTEM = platform.system()


def _run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def _ps(script):
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])


# ---------------- Windows ----------------
def win_firewall():
    rc, out = _run(["netsh", "advfirewall", "show", "allprofiles", "state"])
    if rc != 0:
        return "SKIP", "netsh unavailable"
    states = re.findall(r"State\s+(ON|OFF)", out, re.I)
    if states and all(s.upper() == "ON" for s in states):
        return "PASS", f"all {len(states)} profiles ON"
    return "FAIL", f"profile states: {states or 'unknown'}"


def win_defender():
    rc, out = _ps("$s=Get-MpComputerStatus; \"$($s.AntivirusEnabled)|$($s.RealTimeProtectionEnabled)|$($s.AntivirusSignatureAge)|$($s.IsTamperProtected)\"")
    if rc != 0 or "|" not in out:
        return "SKIP", "Get-MpComputerStatus unavailable (third-party AV?)"
    av, rtp, age, tamper = out.strip().split("|")[:4]
    detail = f"AV={av} realtime={rtp} signature_age_days={age} tamper={tamper}"
    if av == "True" and rtp == "True" and age.isdigit() and int(age) <= 3:
        return ("PASS" if tamper == "True" else "WARN"), detail
    return "FAIL", detail


def win_secureboot():
    rc, out = _ps("try { Confirm-SecureBootUEFI } catch { 'ERR' }")
    v = out.strip()
    if v == "True":
        return "PASS", "Secure Boot on"
    if v == "False":
        return "FAIL", "Secure Boot off"
    return "SKIP", "needs admin or legacy BIOS"


def win_bitlocker():
    rc, out = _ps("try { (Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop).ProtectionStatus } catch { 'ERR' }")
    v = out.strip()
    if v == "On":
        return "PASS", "system drive encrypted"
    if v == "Off":
        return "FAIL", "system drive NOT encrypted (BitLocker/Device Encryption off)"
    return "SKIP", "needs admin (run elevated) or Home edition w/o Device Encryption"


def win_smb1():
    rc, out = _ps("(Get-SmbServerConfiguration).EnableSMB1Protocol")
    v = out.strip()
    if v == "False":
        return "PASS", "SMBv1 disabled"
    if v == "True":
        return "FAIL", "SMBv1 enabled (WannaCry-era protocol)"
    return "SKIP", "unknown"


def win_rdp():
    rc, out = _ps("(Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server').fDenyTSConnections")
    v = out.strip()
    if v == "1":
        return "PASS", "Remote Desktop disabled"
    if v == "0":
        return "WARN", "Remote Desktop enabled - make sure it is only reachable over VPN"
    return "SKIP", "unknown"


# ---------------- Linux ----------------
def lin_firewall():
    for cmd, ok in ((["ufw", "status"], r"Status: active"),
                    (["firewall-cmd", "--state"], r"running"),
                    (["nft", "list", "ruleset"], r"chain input")):
        if shutil.which(cmd[0]):
            rc, out = _run(cmd)
            if re.search(ok, out):
                return "PASS", f"{cmd[0]} active"
    return "FAIL", "no active ufw/firewalld/nftables input chain found (may need sudo)"


def lin_secureboot():
    if shutil.which("mokutil"):
        rc, out = _run(["mokutil", "--sb-state"])
        return ("PASS" if "enabled" in out else "WARN"), out.strip()
    return "SKIP", "mokutil not installed"


def lin_encryption():
    rc, out = _run(["lsblk", "-o", "TYPE"])
    if rc != 0:
        return "SKIP", "lsblk unavailable"
    return ("PASS", "LUKS/dm-crypt volume present") if "crypt" in out else ("FAIL", "no encrypted block device")


def lin_sysctl():
    want = {"kernel.kptr_restrict": "1", "kernel.dmesg_restrict": "1", "net.ipv4.conf.all.rp_filter": "1",
            "kernel.unprivileged_bpf_disabled": "1", "net.ipv4.tcp_syncookies": "1"}
    bad = []
    for k, v in want.items():
        p = "/proc/sys/" + k.replace(".", "/")
        try:
            cur = open(p).read().strip()
            if int(cur) < int(v):
                bad.append(f"{k}={cur}")
        except OSError:
            pass
    return ("PASS", "kernel hardening sysctls set") if not bad else ("WARN", "weak: " + ", ".join(bad))


def lin_zram():
    try:
        swaps = open("/proc/swaps").read()
    except OSError:
        return "SKIP", "no /proc/swaps"
    return ("PASS", "zram swap active") if "zram" in swaps else ("INFO", "no zram - scripts/linux/perf.sh enables it")


def lin_governor():
    p = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    try:
        return "INFO", "cpu governor: " + open(p).read().strip()
    except OSError:
        return "SKIP", "no cpufreq"


# ---------------- macOS ----------------
def mac_firewall():
    rc, out = _run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
    return ("PASS", out.strip()) if "enabled" in out else ("FAIL", out.strip() or "unknown")


def mac_filevault():
    rc, out = _run(["fdesetup", "status"])
    return ("PASS", out.strip()) if "On" in out else ("FAIL", out.strip() or "unknown")


def mac_sip():
    rc, out = _run(["csrutil", "status"])
    return ("PASS", out.strip()) if "enabled" in out else ("FAIL", out.strip() or "unknown")


# ---------------- common ----------------
def listening_ports():
    if SYSTEM == "Windows":
        rc, out = _run(["netstat", "-ano", "-p", "TCP"])
        ports = re.findall(r"TCP\s+(0\.0\.0\.0|\[::\]):(\d+)\s+\S+\s+LISTENING", out)
    elif shutil.which("ss"):
        rc, out = _run(["ss", "-tlnH"])
        ports = re.findall(r"(0\.0\.0\.0|\*|\[::\]):(\d+)", out)
    else:
        rc, out = _run(["netstat", "-an"])
        ports = re.findall(r"(\*)\.(\d+)\s.*LISTEN", out)
    exposed = sorted({int(p) for _, p in ports})
    risky = [p for p in exposed if p in (21, 23, 135, 139, 445, 3389, 5900, 5985, 6379, 27017)]
    if risky:
        return "WARN", f"risky ports on all interfaces: {risky} (all: {exposed[:25]})"
    return "INFO", f"listening on all interfaces: {exposed[:25] or 'none'}"


def dns_resolver():
    if SYSTEM == "Windows":
        rc, out = _ps("(Get-DnsClientServerAddress -AddressFamily IPv4 | ? ServerAddresses).ServerAddresses -join ','")
        servers = out.strip()
    else:
        try:
            servers = ",".join(re.findall(r"^nameserver\s+(\S+)", open("/etc/resolv.conf").read(), re.M))
        except OSError:
            servers = ""
    return "INFO", f"DNS servers: {servers or 'unknown'} (point at your Aureon Node for filtering)"


def vpn_present():
    names = ("wg", "wireguard", "tailscale", "zerotier", "tun", "utun")
    if SYSTEM == "Windows":
        rc, out = _ps("(Get-NetAdapter | ? Status -eq 'Up').InterfaceDescription -join ';'")
    else:
        rc, out = _run(["ip", "-o", "link"]) if shutil.which("ip") else _run(["ifconfig"])
    hit = [n for n in names if n in out.lower()]
    return ("PASS", f"VPN interface up: {hit}") if hit else ("INFO", "no VPN interface up")


def tool_inventory():
    tools = ["git", "wg", "tailscale", "syncthing", "nmap", "clamscan", "yara", "lynis", "ollama",
             "llama-cli", "mvt-android", "mvt-ios", "docker", "podman", "gitleaks"]
    have = [t for t in tools if shutil.which(t)]
    return "INFO", f"Aureon tools found: {have or 'none'}"


CHECKS = {
    "Windows": [("Firewall", win_firewall), ("Defender", win_defender), ("Secure Boot", win_secureboot),
                ("Disk encryption", win_bitlocker), ("SMBv1", win_smb1), ("Remote Desktop", win_rdp)],
    "Linux": [("Firewall", lin_firewall), ("Secure Boot", lin_secureboot), ("Disk encryption", lin_encryption),
              ("Kernel hardening", lin_sysctl), ("zram", lin_zram), ("CPU governor", lin_governor)],
    "Darwin": [("Firewall", mac_firewall), ("FileVault", mac_filevault), ("SIP", mac_sip)],
}
COMMON = [("Listening ports", listening_ports), ("DNS", dns_resolver), ("VPN", vpn_present),
          ("Tooling", tool_inventory)]

WEIGHT = {"PASS": 1.0, "WARN": 0.5, "FAIL": 0.0}


def run_audit():
    results = []
    for name, fn in CHECKS.get(SYSTEM, []) + COMMON:
        try:
            status, detail = fn()
        except Exception as e:  # a single broken check must not kill the audit
            status, detail = "SKIP", f"error: {e}"
        results.append({"check": name, "status": status, "detail": detail})
    scored = [r for r in results if r["status"] in WEIGHT]
    score = round(100 * sum(WEIGHT[r["status"]] for r in scored) / len(scored)) if scored else None
    return {"system": SYSTEM, "release": platform.release(), "machine": platform.machine(),
            "admin": _is_admin(), "score": score, "results": results}


def _is_admin():
    if SYSTEM == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0
