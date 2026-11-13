"""USB-HID injection guard: catches Rubber-Ducky / pico-ducky / O.MG-style attacks.

Those devices pretend to be a keyboard and type commands at machine speed. This guard keeps a
baseline of keyboards you own and reacts the moment a new keyboard-class device appears:
alert, optionally lock the screen (the injected keystrokes then land on the lock screen), and
tell the Aureon Key to flash.

  python -m aureon hidguard --learn                 trust the keyboards plugged in now
  python -m aureon hidguard                         watch; alert on new keyboards
  python -m aureon hidguard --lock --key-port COM5  also lock + signal the Aureon Key

Windows: PnP keyboard class. Linux: /proc/bus/input/devices (no root needed).
"""
import json
import platform
import re
import subprocess
import time
from pathlib import Path

BASE = Path.home() / ".aureon" / "hid_baseline.json"


def keyboards():
    s = platform.system()
    if s == "Windows":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-PnpDevice -Class Keyboard -PresentOnly | % { $_.InstanceId + '|' + $_.FriendlyName }"],
                             capture_output=True, text=True).stdout
        return {l.split("|")[0]: l.split("|", 1)[1] for l in out.splitlines() if "|" in l}
    if s == "Linux":
        devs = {}
        for block in Path("/proc/bus/input/devices").read_text().split("\n\n"):
            if "kbd" not in block or not re.search(r"EV=1[0-9a-f]*3\b", block):
                continue
            name = re.search(r'N: Name="([^"]*)"', block)
            phys = re.search(r"P: Phys=(\S*)", block)
            ident = re.search(r"I: (.*)", block)
            key = f"{ident.group(1) if ident else ''}|{phys.group(1) if phys else ''}"
            devs[key] = name.group(1) if name else "?"
        return devs
    raise SystemExit("hidguard supports Windows and Linux")


def cli(a):
    from .keyagent import lock_screen
    if a.learn:
        k = keyboards()
        BASE.parent.mkdir(exist_ok=True)
        BASE.write_text(json.dumps(k, indent=1))
        print(f"trusted {len(k)} keyboard devices:")
        for v in k.values():
            print(f"  - {v}")
        return 0
    if not BASE.exists():
        raise SystemExit("run with --learn first")
    trusted = json.loads(BASE.read_text())
    ser = None
    if a.key_port:
        import serial
        ser = serial.Serial(a.key_port, 115200, timeout=0.2)
    print(f"watching for new keyboards ({len(trusted)} trusted)... Ctrl+C to stop")
    alerted = set()
    while True:
        now = keyboards()
        for ident, name in now.items():
            if ident in trusted or ident in alerted:
                continue
            alerted.add(ident)
            print(f"[ALERT] new keyboard device: {name}  ({ident})")
            if ser:
                ser.write(b"ALERT\n")
            if a.lock:
                lock_screen()
                print("        screen locked - if you just plugged in a keyboard you trust, re-run --learn")
        alerted &= set(now)  # unplugged -> re-alert next time
        time.sleep(a.interval)
