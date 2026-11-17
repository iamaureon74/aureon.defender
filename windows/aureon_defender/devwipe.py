"""Wipe the laptop's own memory of USB devices that were plugged in and are gone: chargers, cables, drives, phones.

Windows keeps a permanent record of every USB device ever connected (vendor, product, serial number, first/last
connection time) in the PnP database. That record is what makes a history of "everything this laptop was charged
or connected with". For devices that are *not connected now* and were last removed more than N days ago, the
record is removed with Windows' own tool (pnputil /remove-device). If the device is plugged in again Windows simply
installs it fresh; nothing breaks.

Not touched: devices that are connected now, built-in hardware, and Bluetooth pairings (removing those would unpair
headphones and keyboards). A charger's own chip can't be read or erased by the computer, so nothing is sent to it.
"""
import subprocess
import time

WIPE_PREFIXES = ("USB\\", "USBSTOR\\", "SWD\\WPDBUSENUM\\", "WPD\\", "SCSI\\DISK&VEN_", "HID\\VID_")


def candidates(records, present, days, now=None):
    now = time.time() if now is None else now
    cut = now - days * 86400
    present = {p.upper() for p in present}
    out = []
    for r in records:
        dev = r.get("id") or ""
        up = dev.upper()
        if not up.startswith(WIPE_PREFIXES) or up in present or r.get("builtin"):
            continue
        last = r.get("removal") or r.get("arrival") or r.get("first")
        if last is None or last > cut:
            continue
        out.append(dev)
    return sorted(set(out))


def remove_record(dev_id, run=subprocess.run):
    from .governor import child_flags
    try:
        p = run(["pnputil", "/remove-device", dev_id], capture_output=True, text=True, timeout=60,
                creationflags=child_flags())
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def wipe_traces(days, records=None, present=None, run=subprocess.run, limit=500, now=None):
    """Returns {"removed": n, "failed": n}. Needs the SYSTEM engine (administrator) on Windows."""
    if records is None or present is None:
        from .devices import present_ids, registry_history
        from .devices import is_builtin
        records = [{**r, "builtin": is_builtin(r["id"])} for r in registry_history()] if records is None else records
        present = present_ids() if present is None else present
    ids = candidates(records, present, days, now)[:limit]
    ok = sum(remove_record(i, run) for i in ids)
    return {"removed": ok, "failed": len(ids) - ok}
