"""Remote rescue of a laptop/desktop that won't boot, through a PiKVM (pikvm/kvmd) or compatible KVM.

The KVM sees the machine's screen over HDMI capture, types as a USB keyboard, can mount a rescue ISO
as a virtual USB drive, and (with the ATX board) press the real power/reset buttons. That works below
the OS: BIOS/UEFI, boot loader, disk-unlock prompt, blue screen.

Credentials come from the environment, never the command line:
  set AUREON_KVM_URL=https://pikvm.lan   AUREON_KVM_USER=admin   AUREON_KVM_PASS=...
  python -m aureon rescue status
  python -m aureon rescue screenshot shot.jpg
  python -m aureon rescue power on|off|hard-off|reset
  python -m aureon rescue type "text to type"         (e.g. a BitLocker/LUKS recovery key prompt)
  python -m aureon rescue key Delete                   (enter BIOS: press during boot)
  python -m aureon rescue iso rescue.iso               upload + attach as CD-ROM, then reboot into it

Use --insecure only for the KVM's own self-signed cert on your LAN.
API reference: https://docs.pikvm.org/api/
"""
import json
import os
import ssl
import time
import urllib.parse
import urllib.request

BUTTONS = {"on": "power", "off": "power", "hard-off": "power_long", "reset": "reset"}


class KVM:
    def __init__(self, insecure=False):
        self.url = os.environ.get("AUREON_KVM_URL", "").rstrip("/")
        user, pw = os.environ.get("AUREON_KVM_USER"), os.environ.get("AUREON_KVM_PASS")
        if not (self.url and user and pw):
            raise SystemExit("set AUREON_KVM_URL, AUREON_KVM_USER, AUREON_KVM_PASS")
        self.headers = {"X-KVMD-User": user, "X-KVMD-Passwd": pw}
        self.ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()

    def call(self, method, path, params=None, data=None, ctype=None, raw=False, timeout=30):
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        req = urllib.request.Request(self.url + path + q, data=data, method=method, headers=dict(self.headers))
        if ctype:
            req.add_header("Content-Type", ctype)
        with urllib.request.urlopen(req, context=self.ctx, timeout=timeout) as r:
            body = r.read()
        return body if raw else json.loads(body or b"{}").get("result")

    # --- actions ---
    def status(self):
        atx = self.call("GET", "/api/atx")
        msd = self.call("GET", "/api/msd")
        return {"power_led": atx.get("leds", {}).get("power"), "hdd_led": atx.get("leds", {}).get("hdd"),
                "atx_enabled": atx.get("enabled"),
                "msd_connected": msd.get("drive", {}).get("connected"),
                "msd_image": (msd.get("drive", {}).get("image") or {}).get("name")}

    def power(self, what):
        on = self.call("GET", "/api/atx").get("leds", {}).get("power")
        if what == "on" and on:
            return "already on"
        if what == "off" and not on:
            return "already off"
        self.call("POST", "/api/atx/click", {"button": BUTTONS[what]})
        return f"pressed {BUTTONS[what]}"

    def screenshot(self, path):
        img = self.call("GET", "/api/streamer/snapshot", raw=True)
        with open(path, "wb") as f:
            f.write(img)
        return f"saved {len(img)} bytes to {path}"

    def type(self, text):
        self.call("POST", "/api/hid/print", {"limit": 0}, data=text.encode(), ctype="text/plain")
        return f"typed {len(text)} characters"

    def key(self, name):
        # PiKVM key names follow the web KeyboardEvent.code values: Delete, F2, F12, Enter, Escape...
        self.call("POST", "/api/hid/events/send_key", {"key": name})
        return f"sent {name}"

    def iso(self, path):
        name = os.path.basename(path)
        self.call("POST", "/api/msd/set_connected", {"connected": 0})
        with open(path, "rb") as f:  # streamed: ISOs are GBs, don't load into RAM
            req = urllib.request.Request(f"{self.url}/api/msd/write?{urllib.parse.urlencode({'image': name})}",
                                         data=f, method="POST", headers=dict(self.headers))
            req.add_header("Content-Type", "application/octet-stream")
            req.add_header("Content-Length", str(os.path.getsize(path)))
            urllib.request.urlopen(req, context=self.ctx, timeout=3600).read()
        self.call("POST", "/api/msd/set_params", {"image": name, "cdrom": 1})
        self.call("POST", "/api/msd/set_connected", {"connected": 1})
        return f"{name} attached as virtual CD-ROM; reboot the target and pick the USB/CD boot entry"


def cli(a):
    kvm = KVM(insecure=a.insecure)
    if a.action == "status":
        print(json.dumps(kvm.status(), indent=1))
    elif a.action == "power":
        print(kvm.power(a.arg))
    elif a.action == "screenshot":
        print(kvm.screenshot(a.arg or f"kvm-{int(time.time())}.jpg"))
    elif a.action == "type":
        print(kvm.type(a.arg))
    elif a.action == "key":
        print(kvm.key(a.arg))
    elif a.action == "iso":
        print(kvm.iso(a.arg))
    return 0
