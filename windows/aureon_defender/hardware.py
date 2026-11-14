"""Hardware intelligence: everything about this machine, its ports, what was plugged into each port and when,
which network ports are open and by whom, and every downloaded file with when and where it came from.

  inventory()   maker, model, BIOS, CPU, memory, graphics, disks, network adapters (MAC), battery health,
                cameras, audio, Bluetooth radio, physical port connectors (from the firmware's own tables)
  usb_ports()   each USB port (hub + port number) with the device on it now and every device seen on it
  net_ports()   listening TCP/UDP ports with the program and its file
  downloads()   files downloaded in Chrome, Edge, Brave, Vivaldi, Opera and Firefox: time, size, the exact link,
                the page you were on (referrer) and the site; plus Mark-of-the-Web origin for files in Downloads
  report_html() all of the above (plus the device timeline) as one standalone HTML report
Everything is read locally; nothing leaves the PC.
"""
import html
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from .core import expand_all

NOWIN = 0x08000000


# ---------------- WMI ----------------
def _wmi(namespace="root\\cimv2"):
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        return win32com.client.GetObject(f"winmgmts:{{impersonationLevel=impersonate}}!//./{namespace.replace(chr(92), '/')}")
    except Exception:
        return None


def _q(w, wql, fields):
    out = []
    if w is None:
        return out
    try:
        for o in w.ExecQuery(wql):
            row = {}
            for f in fields:
                try:
                    v = getattr(o, f)
                except Exception:
                    v = None
                row[f] = v.strip() if isinstance(v, str) else v
            out.append(row)
    except Exception:
        pass
    return out


PORT_TYPES = {16: "USB", 18: "IEEE 1394", 14: "Mouse", 13: "Keyboard", 28: "Video", 29: "Audio", 30: "Modem", 31: "Network",
              32: "SATA", 33: "SAS", 255: "Other", 34: "MFDP", 35: "Thunderbolt", 9: "Serial", 5: "Parallel"}
CONNECTOR_TYPES = {18: "USB", 6: "RJ-45", 23: "Mini-jack (headphones)", 255: "Other", 34: "HDMI", 32: "Mini DisplayPort",
                   33: "DisplayPort", 35: "USB-C", 31: "SATA", 30: "SAS", 7: "50-pin MiniSCSI"}


def inventory():
    w = _wmi()
    cs = (_q(w, "SELECT Manufacturer, Model, SystemFamily, TotalPhysicalMemory FROM Win32_ComputerSystem",
             ["Manufacturer", "Model", "SystemFamily", "TotalPhysicalMemory"]) or [{}])[0]
    bios = (_q(w, "SELECT SMBIOSBIOSVersion, ReleaseDate, SerialNumber, Manufacturer FROM Win32_BIOS",
               ["SMBIOSBIOSVersion", "ReleaseDate", "SerialNumber", "Manufacturer"]) or [{}])[0]
    cpu = _q(w, "SELECT Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed FROM Win32_Processor",
             ["Name", "NumberOfCores", "NumberOfLogicalProcessors", "MaxClockSpeed"])
    gpu = _q(w, "SELECT Name, DriverVersion, AdapterRAM FROM Win32_VideoController", ["Name", "DriverVersion", "AdapterRAM"])
    disks = _q(w, "SELECT Model, Size, InterfaceType, MediaType, SerialNumber FROM Win32_DiskDrive",
               ["Model", "Size", "InterfaceType", "MediaType", "SerialNumber"])
    nics = _q(w, "SELECT Name, MACAddress, NetConnectionStatus, NetConnectionID FROM Win32_NetworkAdapter WHERE PhysicalAdapter=True",
              ["Name", "MACAddress", "NetConnectionStatus", "NetConnectionID"])
    ports = _q(w, "SELECT ExternalReferenceDesignator, InternalReferenceDesignator, PortType, ConnectorType FROM Win32_PortConnector",
               ["ExternalReferenceDesignator", "InternalReferenceDesignator", "PortType", "ConnectorType"])
    pnp = _q(w, "SELECT Name, PNPClass, Status FROM Win32_PnPEntity WHERE PNPClass='Camera' OR PNPClass='Image' OR PNPClass='Bluetooth' "
                "OR PNPClass='AudioEndpoint' OR PNPClass='Biometric'", ["Name", "PNPClass", "Status"])
    batt = battery()
    for p in ports:
        ct = p.get("ConnectorType")
        ct = ct[0] if isinstance(ct, (list, tuple)) and ct else ct
        p["kind"] = CONNECTOR_TYPES.get(ct) or PORT_TYPES.get(p.get("PortType"), "Port")
        p["label"] = p.get("ExternalReferenceDesignator") or p.get("InternalReferenceDesignator") or p["kind"]
    status = {2: "connected", 7: "disconnected", 0: "disconnected"}
    return {
        "system": {"maker": cs.get("Manufacturer"), "model": cs.get("Model"), "family": cs.get("SystemFamily"),
                   "memory_gb": round(int(cs.get("TotalPhysicalMemory") or 0) / 2 ** 30, 1)},
        "bios": {"vendor": bios.get("Manufacturer"), "version": bios.get("SMBIOSBIOSVersion"),
                 "date": (bios.get("ReleaseDate") or "")[:8], "serial": bios.get("SerialNumber")},
        "cpu": [{"name": c["Name"], "cores": c["NumberOfCores"], "threads": c["NumberOfLogicalProcessors"], "mhz": c["MaxClockSpeed"]} for c in cpu],
        "gpu": [{"name": g["Name"], "driver": g["DriverVersion"]} for g in gpu],
        "disks": [{"model": d["Model"], "gb": round(int(d["Size"] or 0) / 1e9), "bus": d["InterfaceType"], "type": d["MediaType"],
                   "serial": (d["SerialNumber"] or "").strip()} for d in disks],
        "network": [{"name": n["Name"], "mac": n["MACAddress"], "state": status.get(n["NetConnectionStatus"], "other"),
                     "label": n["NetConnectionID"]} for n in nics],
        "ports": [{"label": p["label"], "kind": p["kind"]} for p in ports],
        "peripherals": [{"name": e["Name"], "class": e["PNPClass"], "status": e["Status"]} for e in pnp],
        "battery": batt,
    }


def battery():
    w = _wmi("root\\wmi")
    full = _q(w, "SELECT FullChargedCapacity FROM BatteryFullChargedCapacity", ["FullChargedCapacity"])
    design = _q(w, "SELECT DesignedCapacity FROM BatteryStaticData", ["DesignedCapacity"])
    cyc = _q(w, "SELECT CycleCount FROM BatteryCycleCount", ["CycleCount"])
    if not full or not design or not design[0]["DesignedCapacity"]:
        return None
    f, d = full[0]["FullChargedCapacity"] or 0, design[0]["DesignedCapacity"]
    return {"full_mwh": f, "design_mwh": d, "health_pct": round(100 * f / d, 1) if d else None,
            "cycles": cyc[0]["CycleCount"] if cyc else None}


# ---------------- USB ports ----------------
_LOC = re.compile(r"Port_#(\d+)\.Hub_#(\d+)", re.I)


def usb_ports(timeline=None):
    """Physical USB port -> device now + every device recorded on it (uses the device timeline when given)."""
    import winreg
    from .devices import ENUM, describe, present_ids
    present = present_ids()
    ports = {}
    for root in ("USB", "USBSTOR"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ENUM + "\\" + root) as k:
                i = 0
                while True:
                    try:
                        hw = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    i += 1
                    if "ROOT_HUB" in hw.upper():
                        continue
                    with winreg.OpenKey(k, hw) as h:
                        j = 0
                        while True:
                            try:
                                inst = winreg.EnumKey(h, j)
                            except OSError:
                                break
                            j += 1
                            dev_id = f"{root}\\{hw}\\{inst}"
                            try:
                                with winreg.OpenKey(h, inst) as d:
                                    loc = winreg.QueryValueEx(d, "LocationInformation")[0]
                            except OSError:
                                continue
                            m = _LOC.search(str(loc))
                            if not m:
                                continue
                            key = f"Hub {int(m.group(2))} · Port {int(m.group(1))}"
                            info = describe(dev_id)
                            slot = ports.setdefault(key, {"port": key, "now": [], "seen": []})
                            if dev_id in present:
                                slot["now"].append(info["name"])
                            slot["seen"].append({"name": info["name"], "category": info["category"], "id": dev_id})
        except OSError:
            continue
    if timeline:
        by_id = {}
        for e in timeline:
            by_id.setdefault(e.get("id"), []).append(e)
        for slot in ports.values():
            for s in slot["seen"]:
                ev = sorted(by_id.get(s["id"], []), key=lambda e: e["t"])
                s["first"] = ev[0]["t"] if ev else None
                s["last"] = ev[-1]["t"] if ev else None
    return sorted(ports.values(), key=lambda p: [int(x) for x in re.findall(r"\d+", p["port"])])


# ---------------- network ports ----------------
def net_ports():
    import psutil
    rows = {}
    for c in psutil.net_connections(kind="inet"):
        if c.status not in ("LISTEN", "NONE") or not c.laddr:
            continue
        if c.status == "NONE" and c.type != 2:          # UDP sockets have no state
            continue
        proto = "UDP" if c.type == 2 else "TCP"
        key = (proto, c.laddr.port, c.laddr.ip)
        name, exe = "", ""
        if c.pid:
            try:
                p = psutil.Process(c.pid)
                name, exe = p.name(), p.exe()
            except Exception:
                pass
        rows[key] = {"proto": proto, "port": c.laddr.port, "address": c.laddr.ip, "exposed": c.laddr.ip in ("0.0.0.0", "::"),
                     "program": name, "path": exe, "pid": c.pid}
    return sorted(rows.values(), key=lambda r: (not r["exposed"], r["proto"], r["port"]))


# ---------------- downloads ----------------
CHROMIUM = {"Chrome": "%LOCALAPPDATA%/Google/Chrome/User Data", "Edge": "%LOCALAPPDATA%/Microsoft/Edge/User Data",
            "Brave": "%LOCALAPPDATA%/BraveSoftware/Brave-Browser/User Data", "Vivaldi": "%LOCALAPPDATA%/Vivaldi/User Data",
            "Opera": "%APPDATA%/Opera Software/Opera Stable", "Opera GX": "%APPDATA%/Opera Software/Opera GX Stable"}
WEBKIT_EPOCH = 11644473600


def _copy_db(path):
    """Browsers keep their history open; read a copy so we never lock or corrupt theirs."""
    tmp = Path(tempfile.mkdtemp(prefix="aureon-h-")) / "h.db"
    try:
        shutil.copy2(path, tmp)
    except OSError:
        return None
    return tmp


def _chromium_downloads(browser, history):
    db = _copy_db(history)
    if not db:
        return []
    out = []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("""SELECT d.id, d.target_path, d.start_time, d.received_bytes, d.total_bytes, d.tab_url, d.referrer,
                                     d.site_url, d.mime_type, d.danger_type,
                                     (SELECT url FROM downloads_url_chains c WHERE c.id = d.id ORDER BY chain_index DESC LIMIT 1)
                              FROM downloads d ORDER BY d.start_time DESC LIMIT 2000""").fetchall()
        con.close()
    except sqlite3.Error:
        rows = []
    finally:
        shutil.rmtree(db.parent, ignore_errors=True)
    for _id, target, start, recv, total, tab, ref, site, mime, danger, final_url in rows:
        out.append({"t": start / 1e6 - WEBKIT_EPOCH if start else None, "file": target, "size": recv or total,
                    "url": final_url or "", "page": tab or "", "referrer": ref or "", "site": site or "", "mime": mime or "",
                    "flagged_by_browser": bool(danger and danger not in (0, 4)), "browser": browser,
                    "exists": bool(target) and os.path.exists(target)})
    return out


def _firefox_downloads(places):
    db = _copy_db(places)
    if not db:
        return []
    out = []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("""SELECT p.url, a.content, a.dateAdded FROM moz_annos a
                              JOIN moz_anno_attributes n ON n.id = a.anno_attribute_id
                              JOIN moz_places p ON p.id = a.place_id
                              WHERE n.name = 'downloads/destinationFileURI' ORDER BY a.dateAdded DESC LIMIT 2000""").fetchall()
        con.close()
    except sqlite3.Error:
        rows = []
    finally:
        shutil.rmtree(db.parent, ignore_errors=True)
    from urllib.parse import unquote, urlparse
    for url, dest, added in rows:
        path = unquote(urlparse(dest).path).lstrip("/").replace("/", "\\") if dest else ""
        out.append({"t": added / 1e6 if added else None, "file": path, "size": None, "url": url, "page": "", "referrer": "",
                    "site": "", "mime": "", "flagged_by_browser": False, "browser": "Firefox", "exists": bool(path) and os.path.exists(path)})
    return out


def motw(path):
    """Mark-of-the-Web: where Windows says a file came from."""
    try:
        with open(str(path) + ":Zone.Identifier", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except OSError:
        return None
    g = lambda k: (re.search(rf"^{k}=(.*)$", txt, re.M) or [None, None])[1]
    return {"zone": g("ZoneId"), "url": (g("HostUrl") or "").strip(), "referrer": (g("ReferrerUrl") or "").strip()}


def downloads(limit=1500):
    from urllib.parse import urlparse
    items = []
    for browser, base in CHROMIUM.items():
        for root in expand_all(base):
            for hist in list(Path(root).glob("*/History")) + list(Path(root).glob("History")):
                items += _chromium_downloads(browser, hist)
    for root in expand_all("%APPDATA%/Mozilla/Firefox/Profiles"):
        for places in Path(root).glob("*/places.sqlite"):
            items += _firefox_downloads(places)
    known = {os.path.normcase(i["file"]) for i in items if i["file"]}
    for folder in expand_all("~/Downloads"):                 # files that arrived another way (apps, chat, mail)
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for e in entries:
            if not e.is_file() or os.path.normcase(e.path) in known:
                continue
            m = motw(e.path)
            st = e.stat()
            items.append({"t": st.st_mtime, "file": e.path, "size": st.st_size, "url": (m or {}).get("url", ""),
                          "page": "", "referrer": (m or {}).get("referrer", ""), "site": "", "mime": "",
                          "flagged_by_browser": False, "browser": "Windows (Mark-of-the-Web)" if m else "unknown origin", "exists": True})
    for i in items:
        src = i["url"] or i["referrer"] or i["page"]
        i["domain"] = urlparse(src).hostname or "" if src and src.startswith(("http", "ftp")) else ""
        i["name"] = os.path.basename(i["file"] or "") or "(unnamed)"
    items.sort(key=lambda i: i["t"] or 0, reverse=True)
    return items[:limit]


# ---------------- report ----------------
def collect(timeline=None):
    return {"t": time.time(), "inventory": inventory(), "usb_ports": usb_ports(timeline), "net_ports": net_ports(),
            "downloads": downloads()}


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else "–"


def report_html(data, timeline=None):
    e = html.escape
    inv = data["inventory"]
    s = inv["system"]
    b = inv.get("battery") or {}
    rows = lambda cells: "".join(f"<td>{c}</td>" for c in cells)
    table = lambda head, body: (f"<table><thead><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr></thead><tbody>"
                                + "".join(f"<tr>{rows(r)}</tr>" for r in body) + "</tbody></table>")
    link = lambda u: f'<a href="{e(u)}">{e(u)}</a>' if u and u.startswith(("http://", "https://", "ftp://")) else e(u or "")
    parts = [
        f"<h1>aureon.defender · hardware report</h1><p class=m>{e(s.get('maker') or '')} {e(s.get('model') or '')} · generated {_ts(data['t'])}</p>",
        "<h2>This machine</h2>" + table(["", ""], [
            ["Model", e(f"{s.get('maker')} {s.get('model')} ({s.get('family') or ''})")],
            ["Firmware", e(f"{inv['bios'].get('vendor')} {inv['bios'].get('version')} ({inv['bios'].get('date')})")],
            ["Serial", e(inv["bios"].get("serial") or "")],
            ["Processor", e("; ".join(f"{c['name']} · {c['cores']} cores / {c['threads']} threads" for c in inv["cpu"]))],
            ["Memory", f"{s.get('memory_gb')} GB"],
            ["Graphics", e("; ".join(f"{g['name']} (driver {g['driver']})" for g in inv["gpu"]))],
            ["Battery", e(f"{b.get('health_pct')}% of design capacity · {b.get('cycles')} cycles") if b else "no battery"]]),
        "<h2>Storage</h2>" + table(["Disk", "Size", "Bus", "Serial"], [[e(d["model"] or ""), f"{d['gb']} GB", e(d["bus"] or ""), e(d["serial"])] for d in inv["disks"]]),
        "<h2>Network adapters</h2>" + table(["Adapter", "MAC address", "State"], [[e(n["name"] or ""), e(n["mac"] or ""), e(n["state"])] for n in inv["network"]]),
        "<h2>Physical ports (firmware tables)</h2>" + (table(["Port", "Kind"], [[e(p["label"]), e(p["kind"])] for p in inv["ports"]]) if inv["ports"] else "<p class=m>This firmware doesn't list its ports.</p>"),
        "<h2>USB ports and what has used them</h2>" + table(["Port", "Now", "Seen on this port"], [
            [e(p["port"]), e(", ".join(p["now"]) or "empty"),
             "<br>".join(f"{e(x['name'])} <span class=m>({e(x['category'])}{', last ' + _ts(x.get('last')) if x.get('last') else ''})</span>" for x in p["seen"])]
            for p in data["usb_ports"]]),
        "<h2>Open network ports</h2>" + table(["Protocol", "Port", "Listening on", "Program"], [
            [r["proto"], str(r["port"]), e(r["address"]) + (" <b>(whole network)</b>" if r["exposed"] else ""), e(r["program"]) + f"<br><span class=m>{e(r['path'])}</span>"]
            for r in data["net_ports"]]),
        "<h2>Downloads</h2>" + table(["When", "File", "From", "Browser"], [
            [_ts(d["t"]), e(d["name"]) + ("" if d["exists"] else " <span class=m>(deleted)</span>") + ("<br><b>browser warned about this file</b>" if d["flagged_by_browser"] else ""),
             link(d["url"]) + (f"<br><span class=m>page: </span>{link(d['page'] or d['referrer'])}" if (d["page"] or d["referrer"]) else ""), e(d["browser"])]
            for d in data["downloads"]]),
    ]
    if timeline:
        parts.append("<h2>Device timeline</h2>" + table(["When", "Device", "Event", "Source"], [
            [_ts(t["t"]), e(t["name"]) + (" <b>(tracking tag)</b>" if t.get("tracker") else ""), e(f"{t['category']} · {t['kind']}"), e(t.get("source", ""))]
            for t in timeline[:800]]))
    css = ("body{font:14px/1.5 'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;background:#0b0b0d;color:#ece6df;max-width:1180px;margin:0 auto;padding:32px 24px 80px}"
           "h1{font-weight:600;margin:0}h2{font-weight:600;margin:34px 0 10px;font-size:17px}.m{color:#8d857d}a{color:#d9a46b;word-break:break-all}"
           "table{width:100%;border-collapse:separate;border-spacing:0;background:#141215;border-radius:14px;overflow:hidden}"
           "th{text-align:left;font-weight:600;color:#8d857d;font-size:12px;padding:10px 14px;background:#18161a}"
           "td{padding:9px 14px;vertical-align:top}tbody tr:nth-child(even) td{background:#17151a}")
    return f"<!doctype html><html lang=en><meta charset=utf-8><title>aureon.defender hardware report</title><style>{css}</style><body>{''.join(parts)}</body></html>"


def write_report(timeline=None, folder=None):
    data = collect(timeline)
    folder = Path(folder or Path.home() / "Documents" / "aureon")
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / time.strftime("hardware-report-%Y%m%d-%H%M.html")
    out.write_text(report_html(data, timeline), encoding="utf-8")
    return out, data
