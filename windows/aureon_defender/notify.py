"""Notifications that look native: Aureon's own name and icon in Action Center, a severity line, and buttons.

  identity   an AppUserModelID registered per user (HKCU) with display name "aureon.defender" and the app icon
  buttons    "Open" deep-links into the dashboard section (aureon:// protocol, per user); "Dismiss"
  grouping   same kind+subject replaces itself (tag/group) instead of stacking
  calm       bursts collapse into one summary; info-level events never notify; quiet hours optional
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from xml.sax.saxutils import escape

AUMID = "Aureon.Defender"
NOWIN = 0x08000000


def icon_path():
    try:
        from .icon import find
        return find("icon.png")
    except Exception:
        pass
    for p in (Path(sys.executable).parent / "_internal" / "aureon_defender" / "ui" / "icon.png",
              Path(__file__).parent / "ui" / "icon.png"):
        if p.exists():
            return p
    return None


def exe_for_protocol():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" open --url "%1"'
    return None


def register():
    """Per-user: toast identity + aureon:// links. Safe to call on every agent start."""
    if os.name != "nt":
        return False
    import winreg
    ico = icon_path()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "aureon.defender")
        if ico:
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(ico))
        winreg.SetValueEx(k, "IconBackgroundColor", 0, winreg.REG_SZ, "FF0D0C0E")
        winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)
    cmd = exe_for_protocol()
    if cmd:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Classes\aureon", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:aureon.defender")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Classes\aureon\shell\open\command", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    return True


SEVERITY_LINE = {"high": "Needs your attention", "medium": "Worth a look", "low": "For your information"}
SECTION = {"threat": "activity", "suspicious": "activity", "ransomware": "activity", "network": "activity", "usb": "devices",
           "device": "devices", "wifi": "devices", "radar": "radar", "privacy": "radar", "phone": "phones", "posture": "leaks",
           "leak": "leaks", "defender": "activity", "clipboard": "activity"}


def toast_xml(title, body, severity="medium", kind="", tag="", attribution=None):
    section = SECTION.get(kind, "overview")
    ico = icon_path()
    logo = f'<image placement="appLogoOverride" src="{escape(str(ico))}"/>' if ico else ""
    scenario = ' scenario="reminder"' if severity == "high" else ""       # high stays on screen until handled
    attr = escape(attribution or SEVERITY_LINE.get(severity, ""))
    audio = '<audio silent="true"/>' if severity == "low" else ""
    return (f'<toast launch="aureon://{section}" activationType="protocol"{scenario}>'
            f'<visual><binding template="ToastGeneric"><text hint-maxLines="1">{escape(title)}</text>'
            f'<text>{escape(body)}</text><text placement="attribution">{attr}</text>{logo}</binding></visual>'
            f'<actions><action content="Open" activationType="protocol" arguments="aureon://{section}"/>'
            f'<action content="Dismiss" activationType="system" arguments="dismiss"/></actions>'
            f'{audio}</toast>')


PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml($env:AUR_XML)
$t = [Windows.UI.Notifications.ToastNotification]::new($x)
if ($env:AUR_TAG) { $t.Tag = $env:AUR_TAG; $t.Group = 'aureon' }
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:AUR_ID).Show($t)
"""


def show(title, body, severity="medium", kind="", tag="", attribution=None):
    xml = toast_xml(title[:110], body[:260], severity, kind, tag, attribution)
    env = dict(os.environ, AUR_XML=xml, AUR_TAG=(tag or "")[:60], AUR_ID=AUMID)
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS], env=env, creationflags=NOWIN,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def _call(f):
    try:
        return bool(f())
    except Exception:
        return False


def silent_setting():
    from .core import Settings
    return Settings().load().get("silent_mode", True)


class Notifier:
    """Decides what deserves a toast. Bursts within `window` seconds become one summary."""
    def __init__(self, send=show, window=8.0, burst=3, quiet=None, silent=None):
        self.send = send
        self.silent = silent               # callable -> bool: only blocked/deleted threats notify
        self.window = window
        self.burst = burst
        self.quiet = quiet                 # (start_hour, end_hour) or None
        self.recent = []

    def in_quiet(self, now):
        if not self.quiet:
            return False
        h = time.localtime(now).tm_hour
        a, b = self.quiet
        return a <= h < b if a < b else (h >= a or h < b)

    def handle(self, e, now=None):
        now = now or time.time()
        sev = e.get("severity", "info")
        if sev not in ("medium", "high"):
            return None
        if self.silent and _call(self.silent) and not (e.get("blocked") or e.get("kind") == "ransomware"):
            return None                     # silent mode: everything else waits quietly in the dashboard
        if self.in_quiet(now) and sev != "high":
            return None
        self.recent = [t for t in self.recent if now - t < self.window]
        self.recent.append(now)
        n = len(self.recent)
        if n > self.burst:
            if n == self.burst + 1:
                self.send("Several things need a look", "Open Aureon to see them together.", "medium", "radar", tag="burst",
                          attribution="aureon.defender")
            return "summarised"
        tag = f"{e.get('kind', '')}:{e.get('title', '')}"[:60]
        self.send(e.get("title", ""), e.get("detail", ""), sev, e.get("kind", ""), tag=tag)
        return "shown"
