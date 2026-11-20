"""Microphone and screen-capture watch.

Windows records, per app, when the microphone and camera were last switched on and off, under the Capability Access
Manager. An app that started and never stopped is using it right now. We read that, and we read whether you have turned
the microphone off for apps at all; if something is listening while you believe it is off, that is worth knowing.

Hidden screen capture is what surveillance and "screen-recording" tools do: they grab your screen frame by frame.
We can't see a single BitBlt from user space, but we can name the software that does it — Windows Recall's continuous
snapshots, screen recorders, and remote-view tools — and we can hide a window from every capture so a snooping tool
records black where your secrets were (SetWindowDisplayAffinity, the same call banking apps use).
"""
import ctypes
import os
import time

MIC = "microphone"
CAM = "webcam"
CONSENT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
CONSENT_HKLM = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"

# software whose job is to capture or stream the screen continuously
CAPTURE_SOFTWARE = {
    "obs64.exe": "OBS screen recorder", "obs32.exe": "OBS screen recorder", "obs.exe": "OBS screen recorder",
    "sharex.exe": "ShareX screen capture", "snagit32.exe": "Snagit screen capture", "snagiteditor.exe": "Snagit",
    "camtasia.exe": "Camtasia recorder", "bandicam.exe": "Bandicam recorder", "flashback.exe": "FlashBack recorder",
    "action.exe": "Mirillis Action recorder", "fraps.exe": "Fraps recorder", "screenrec.exe": "ScreenRec",
    "anydesk.exe": "AnyDesk remote view", "rustdesk.exe": "RustDesk remote view", "teamviewer.exe": "TeamViewer remote view",
    "tv_w32.exe": "TeamViewer remote view", "tv_x64.exe": "TeamViewer remote view", "ultraviewer_desktop.exe": "UltraViewer remote view",
    "aa_v3.exe": "Ammyy Admin remote view", "winvnc.exe": "VNC remote view", "tvnserver.exe": "TightVNC remote view",
    "vncserver.exe": "VNC remote view", "mstsc.exe": "Remote Desktop (someone viewing this PC)",
    "quickassist.exe": "Windows Quick Assist remote view", "dwagent.exe": "DWAgent remote view",
    "supremo.exe": "Supremo remote view", "aweray_remote.exe": "AweSun remote view", "gotoassist.exe": "GoToAssist remote view",
    "activtrak.exe": "ActivTrak employee monitor", "teramind_agent.exe": "Teramind employee monitor",
    "veriato.exe": "Veriato monitor", "hubstaff.exe": "Hubstaff monitor", "timedoctor.exe": "Time Doctor monitor",
    "wmplayer.exe": "", "actalogger.exe": "Activity logger",
}


def _consent_scan(hive, root, which):
    """[(app, running_now)] for every app that has used mic/camera, newest activity first."""
    import winreg
    out = []
    try:
        base = winreg.OpenKey(hive, root + "\\" + which)
    except OSError:
        return out

    def read(k, app):
        try:
            start = winreg.QueryValueEx(k, "LastUsedTimeStart")[0]
            stop = winreg.QueryValueEx(k, "LastUsedTimeStop")[0]
            out.append({"app": app, "active": stop == 0 and start > 0, "last": start})
        except OSError:
            pass

    i = 0
    while True:
        try:
            name = winreg.EnumKey(base, i); i += 1
        except OSError:
            break
        try:
            with winreg.OpenKey(base, name) as k:
                if name == "NonPackaged":
                    j = 0
                    while True:
                        try:
                            sub = winreg.EnumKey(k, j); j += 1
                        except OSError:
                            break
                        with winreg.OpenKey(k, sub) as sk:
                            read(sk, sub.split("#")[-1].replace("_", "\\"))
                else:
                    read(k, name)
        except OSError:
            pass
    return out


def access_value(which):
    """'Allow' / 'Deny' — whether apps may use the mic/camera at all (the Windows privacy switch)."""
    import winreg
    for hive, root in ((winreg.HKEY_CURRENT_USER, CONSENT), (winreg.HKEY_LOCAL_MACHINE, CONSENT_HKLM)):
        try:
            with winreg.OpenKey(hive, root + "\\" + which) as k:
                v = winreg.QueryValueEx(k, "Value")[0]
                if v == "Deny":
                    return "Deny"
        except OSError:
            pass
    return "Allow"


def _friendly(app):
    base = os.path.basename(app).lower()
    known = {"skype.exe": "Skype", "teams.exe": "Microsoft Teams", "ms-teams.exe": "Microsoft Teams",
             "zoom.exe": "Zoom", "discord.exe": "Discord", "chrome.exe": "Chrome", "msedge.exe": "Edge",
             "firefox.exe": "Firefox", "slack.exe": "Slack", "webexmta.exe": "Webex"}
    return known.get(base) or CAPTURE_SOFTWARE.get(base) or app.rsplit("\\", 1)[-1]


def mic_state():
    """What is using the microphone right now, and whether the mic is supposed to be off."""
    if os.name != "nt":
        return {"supported": False}
    import winreg
    apps = _consent_scan(winreg.HKEY_CURRENT_USER, CONSENT, MIC)
    active = [a for a in apps if a["active"]]
    access = access_value(MIC)
    return {"supported": True, "access": access, "on": bool(active),
            "using": [{"app": _friendly(a["app"])} for a in active],
            "listening_while_off": access == "Deny" and bool(active)}


def camera_state():
    if os.name != "nt":
        return {"supported": False}
    import winreg
    active = [a for a in _consent_scan(winreg.HKEY_CURRENT_USER, CONSENT, CAM) if a["active"]]
    return {"supported": True, "on": bool(active), "using": [{"app": _friendly(a["app"])} for a in active]}


def recall_active():
    """Windows Recall takes a screenshot of everything you do every few seconds. Is it on?"""
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Policies\Microsoft\Windows\WindowsAI") as k:
            return winreg.QueryValueEx(k, "DisableAIDataAnalysis")[0] != 1
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\graphicsCaptureProgrammatic"):
            pass
    except OSError:
        pass
    return None     # unknown / not present on this build


def screen_capturers():
    """Software currently running whose purpose is to capture, record or remote-view the screen."""
    if os.name != "nt":
        return []
    try:
        import psutil
    except ImportError:
        return []
    seen, out = set(), []
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower()
        if n in CAPTURE_SOFTWARE and CAPTURE_SOFTWARE[n] and n not in seen:
            seen.add(n)
            out.append({"process": n, "what": CAPTURE_SOFTWARE[n]})
    return out


def screen_state():
    cap = screen_capturers()
    rec = recall_active()
    return {"supported": os.name == "nt", "capturers": cap, "recall_on": rec,
            "watched": bool(cap) or rec is True}


WDA_EXCLUDEFROMCAPTURE = 0x11
WDA_NONE = 0x0


def protect_window(hwnd, on=True):
    """Hide a window from every screen capture and screenshot. Capture tools record black over it."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if on else WDA_NONE))
    except Exception:
        return False


def find_window(title_contains):
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_contains.lower() in buf.value.lower() and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def protect_app_window(on=True):
    """Hide the aureon.defender window itself from screen capture (it shows your passwords and devices)."""
    hwnd = find_window("aureon.defender")
    return protect_window(hwnd, on) if hwnd else False


CAM_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
RECALL_KEY = r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI"


def enforce_capture_guards(reg=None):
    """Machine-wide, run by the SYSTEM engine. Returns what it changed (empty when already in place).

    * Windows Recall: policy 'DisableAIDataAnalysis' = 1, so Windows stops saving screen snapshots.
    * Borderless capture: the graphicsCaptureWithoutBorder consent is set to Deny, so any app that captures the
      screen must show Windows' yellow capture border. Ordinary screenshots, screen sharing and recorders keep
      working; they just can't do it invisibly any more.
    """
    if os.name != "nt" and reg is None:
        return []
    if reg is None:
        import winreg

        def reg(path, name, value, kind):
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                try:
                    if winreg.QueryValueEx(k, name)[0] == value:
                        return False
                except OSError:
                    pass
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD if kind == "dword" else winreg.REG_SZ, value)
                return True
    changed = []
    if reg(RECALL_KEY, "DisableAIDataAnalysis", 1, "dword"):
        changed.append("windows recall snapshots turned off")
    if reg(CAM_KEY + "\\graphicsCaptureWithoutBorder", "Value", "Deny", "sz"):
        changed.append("apps can no longer capture the screen without the yellow border")
    return changed


def hidden_capturers(log=None):
    """Programs capturing the screen right now without the capture border, from Windows' own access records."""
    if log is None:
        if os.name != "nt":
            return []
        from .radar import privacy_log
        log = privacy_log()
    out = []
    for r in log:
        if r.get("capability") == "graphicsCaptureWithoutBorder" and r.get("in_use"):
            app = r.get("app") or ""
            out.append({"app": app, "exe": app.replace("#", "\\") if "#" in app else "", "user": r.get("user")})
    return out


def collect():
    return {"mic": mic_state(), "camera": camera_state(), "screen": screen_state(), "t": time.time()}
