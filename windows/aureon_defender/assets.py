"""A roll-call of your devices — every laptop, tablet and phone that has been on your network or paired to this PC.

Inspired by NetAlertX (the open-source network-presence tracker you'd run on a Raspberry Pi), but kept entirely on
this machine with no server. It watches the local network's neighbour table and this PC's Bluetooth history, and keeps
a durable record of each device: when it first appeared, when it was last seen, what kind it is, and whether you've
marked it as yours. A device you don't recognise showing up is the whole point — that's how you catch a stranger's
phone that has joined your Wi-Fi, or a tracker that keeps reappearing.

Nothing leaves this PC. The record is a plain file you can read, relabel or wipe.
"""
import json
import os
import re
import subprocess
import time

from .core import atomic_write, data_dir

NOWIN = 0x08000000

# OUI prefixes → maker, for naming unknown devices (small, common set; extended at runtime by reverse DNS)
OUI = {
    "3C:5A:B4": "Google", "F4:F5:E8": "Google", "DA:A1:19": "Google", "00:1A:11": "Google",
    "AC:DE:48": "Apple", "F0:18:98": "Apple", "A4:83:E7": "Apple", "DC:A9:04": "Apple", "00:1C:B3": "Apple",
    "00:12:FB": "Samsung", "00:1A:8A": "Samsung", "5C:0A:5B": "Samsung", "B4:07:F9": "Samsung",
    "00:50:F2": "Microsoft", "00:15:5D": "Microsoft (Hyper-V)", "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi", "00:0C:29": "VMware", "00:1D:D8": "Intel", "00:21:6A": "Intel",
}


def _store():
    return data_dir() / "assets.json"


def _load():
    try:
        return json.loads(_store().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d):
    atomic_write(_store(), json.dumps(d, indent=0))


def _maker(mac):
    return OUI.get(mac[:8].upper())


def kind_of(mac, name):
    n = (name or "").lower()
    maker = _maker(mac) or ""
    if any(w in n for w in ("iphone", "ipad", "pixel", "galaxy", "phone", "android", "oneplus")):
        return "phone"
    if "ipad" in n or "tablet" in n:
        return "tablet"
    if maker in ("Apple", "Samsung", "Google") and not n:
        return "phone"
    if maker == "Raspberry Pi":
        return "pi"
    if any(w in n for w in ("tv", "roku", "firestick", "chromecast", "shield")):
        return "tv"
    if any(w in n for w in ("laptop", "desktop", "pc", "macbook", "surface")):
        return "computer"
    return "device"


def arp_neighbors():
    """[(mac, ip, name)] of devices on the local network right now (the neighbour/ARP table)."""
    if os.name != "nt":
        return []
    out = []
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=12, creationflags=NOWIN,
                           encoding="utf-8", errors="ignore").stdout
    except Exception:
        return out
    for line in r.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\s+(\w+)", line)
        if m and m.group(3).lower() == "dynamic":
            mac = m.group(2).replace("-", ":").upper()
            if not mac.startswith("FF:") and not mac.endswith("FF:FF:FF") and not mac.startswith("01:00:5E"):
                out.append((mac, m.group(1), ""))
    return out


def bluetooth_seen():
    """[(address, name)] of Bluetooth devices this PC has paired with or seen."""
    try:
        from .devices import bluetooth_history
        return [(d.get("address", d.get("id", "")), d.get("name", "")) for d in bluetooth_history()]
    except Exception:
        return []


def this_pc():
    try:
        from .hardware import inventory
        inv = inventory()
        sysm = inv.get("system", {})
        return {"id": "self:" + (sysm.get("serial") or sysm.get("uuid") or "this-pc"),
                "name": sysm.get("model") or "This PC", "kind": "computer", "maker": sysm.get("maker", "")}
    except Exception:
        return {"id": "self:this-pc", "name": "This PC", "kind": "computer", "maker": ""}


def scan():
    """Merge every source into the registry, update first/last-seen, return new arrivals."""
    reg = _load()
    now = time.time()
    seen_ids, new = [], []

    def touch(aid, name, kind, source, extra=None):
        seen_ids.append(aid)
        rec = reg.get(aid)
        if not rec:
            rec = {"id": aid, "name": name, "kind": kind, "first_seen": now, "trusted": False, "label": ""}
            new.append(rec)
        rec["last_seen"] = now
        rec["source"] = source
        if name and not rec.get("name"):
            rec["name"] = name
        if extra:
            rec.update(extra)
        reg[aid] = rec

    pc = this_pc()
    touch(pc["id"], pc["name"], pc["kind"], "this pc", {"trusted": True, "maker": pc.get("maker", "")})
    for mac, ip, name in arp_neighbors():
        touch("mac:" + mac, name, kind_of(mac, name), "network", {"mac": mac, "ip": ip, "maker": _maker(mac) or ""})
    for addr, name in bluetooth_seen():
        if addr:
            touch("bt:" + str(addr), name, kind_of("", name) if "phone" in (name or "").lower() else "bluetooth", "bluetooth")

    for aid, rec in reg.items():
        rec["present"] = aid in seen_ids
    _save(reg)
    return {"new": new, "present": sum(1 for r in reg.values() if r.get("present")), "total": len(reg)}


def registry():
    """All known devices, present ones first, then by most-recently-seen."""
    reg = _load()
    rows = sorted(reg.values(), key=lambda r: (not r.get("present"), -r.get("last_seen", 0)))
    return rows


def label(aid, name=None, trusted=None):
    reg = _load()
    if aid in reg:
        if name is not None:
            reg[aid]["label"] = name
        if trusted is not None:
            reg[aid]["trusted"] = bool(trusted)
        _save(reg)
        return True
    return False


def forget(aid):
    reg = _load()
    if reg.pop(aid, None) is not None:
        _save(reg)
        return True
    return False
