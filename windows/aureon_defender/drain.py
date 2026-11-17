"""What is draining this device, what runs silently, and what is allowed to listen.

  DrainMeter   samples every process's CPU time and disk I/O once a minute and keeps 24 rolling hourly buckets.
               CPU-seconds are the best battery proxy the OS exposes to normal programs: on a laptop CPU package
               power dominates and scales roughly with busy time, so share_of_cpu ~ share_of_battery used by programs.
               (Screen, radios and GPU are not attributed; the report says so.) Cost: one process walk per minute.
  silent()     processes that have no visible window. Session-0 processes are system services; anything else
               without a window is "running silently in your account", grouped by the company that signed/made it.
  listeners()  voice wake-word settings and known always-listening assistants that are installed or running.
"""
import os
import time
from collections import defaultdict

HOUR = 3600

# Known assistants that keep a wake-word detector or ambient-audio model running.
LISTENING_APPS = {
    "cortana.exe": "Cortana (voice assistant)",
    "copilot.exe": "Microsoft Copilot (can listen for 'Hey Copilot' when voice activation is on)",
    "alexa.exe": "Amazon Alexa",
    "alexaapp.exe": "Amazon Alexa",
    "siri.exe": "Siri",
    "intelvoiceassistant.exe": "Intel voice wake",
    "voiceaccess.exe": "Windows Voice Access (listens continuously while running)",
    "speechruntime.exe": "Windows speech runtime (keyword spotting for apps)",
}


class DrainMeter:
    def __init__(self, sampler=None, keep_hours=24):
        self.sampler = sampler or self._sample
        self.keep = keep_hours
        self.prev = {}                       # pid -> (create_time, cpu_s, io_bytes, name)
        self.buckets = {}                    # hour -> {name: [cpu_s, io_bytes]}

    @staticmethod
    def _sample():
        import psutil
        out = {}
        for p in psutil.process_iter(["pid", "name", "create_time", "cpu_times"]):
            try:
                ct = p.info["cpu_times"]
                cpu = (ct.user + ct.system) if ct else 0.0
                try:
                    io = p.io_counters()
                    iob = io.read_bytes + io.write_bytes
                except Exception:
                    iob = 0
                out[p.info["pid"]] = (p.info["create_time"], cpu, iob, p.info["name"] or "?")
            except Exception:
                continue
        return out

    def tick(self, now=None):
        now = time.time() if now is None else now
        cur = self.sampler()
        hour = int(now // HOUR)
        b = self.buckets.setdefault(hour, defaultdict(lambda: [0.0, 0]))
        for pid, (ctime, cpu, iob, name) in cur.items():
            old = self.prev.get(pid)
            if old and old[0] == ctime:                       # same process (pid not reused)
                dcpu, dio = max(0.0, cpu - old[1]), max(0, iob - old[2])
                if dcpu or dio:
                    b[name][0] += dcpu
                    b[name][1] += dio
        self.prev = cur
        for h in [h for h in self.buckets if h <= hour - self.keep]:
            self.buckets.pop(h)

    def top(self, hours=24, n=15, now=None):
        now = time.time() if now is None else now
        since = int(now // HOUR) - hours + 1
        tot = defaultdict(lambda: [0.0, 0])
        for h, b in self.buckets.items():
            if h >= since:
                for name, (c, io) in b.items():
                    tot[name][0] += c
                    tot[name][1] += io
        all_cpu = sum(v[0] for v in tot.values()) or 1.0
        rows = sorted(((k, v) for k, v in tot.items() if v[0] >= 0.05 or v[1] >= (1 << 20)),
                      key=lambda kv: kv[1][0], reverse=True)[:n]
        return [{"name": k, "cpu_seconds": round(v[0], 1), "share": round(100 * v[0] / all_cpu, 1),
                 "disk_mb": round(v[1] / (1 << 20), 1)} for k, v in rows]


def _visible_window_pids():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    pids = set()
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) > 0:
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(pid.value)
        return True
    u.EnumWindows(CB(cb), 0)
    return pids


def silent(procs=None, windowed=None, company=None):
    """Group processes without a visible window: {"system": [...], "your_account": {company: [names]}}."""
    if procs is None:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "exe", "username"]):
            try:
                sess = None
                if os.name == "nt":
                    import ctypes
                    s = ctypes.c_ulong()
                    if ctypes.windll.kernel32.ProcessIdToSessionId(p.info["pid"], ctypes.byref(s)):
                        sess = s.value
                procs.append({**p.info, "session": sess})
            except Exception:
                continue
    if windowed is None:
        windowed = _visible_window_pids() or set()
    if company is None:
        try:
            from .radar import company_of
        except Exception:
            company_of = None
        company = (lambda exe: company_of(exe) if company_of and exe else None)
    system, user = set(), defaultdict(set)
    for p in procs:
        if p["pid"] in windowed or not p.get("name"):
            continue
        if p.get("session") == 0 or (p.get("username") or "").upper().endswith(("SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE")):
            system.add(p["name"])
        else:
            user[company(p.get("exe")) or "Unknown maker"].add(p["name"])
    return {"system": sorted(system), "your_account": {k: sorted(v) for k, v in sorted(user.items())},
            "system_count": len(system), "silent_count": sum(len(v) for v in user.values())}


def voice_activation():
    """Windows 'Let apps use voice activation' (wake-word listening) and on-lock-screen setting."""
    if os.name != "nt":
        return {}
    import winreg
    base = r"Software\Microsoft\Speech_OneCore\Settings\VoiceActivation\UserPreferenceForAllApps"
    out = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as k:
            for v in ("AgentActivationEnabled", "AgentActivationOnLockScreenEnabled"):
                try:
                    out[v] = bool(winreg.QueryValueEx(k, v)[0])
                except OSError:
                    pass
    except OSError:
        pass
    return out


def listeners(names=None, voice=None):
    if names is None:
        import psutil
        names = set()
        for p in psutil.process_iter(["name"]):
            try:
                names.add((p.info["name"] or "").lower())
            except Exception:
                continue
    names = {n.lower() for n in names}
    running = sorted({label for exe, label in LISTENING_APPS.items() if exe in names})
    voice = voice_activation() if voice is None else voice
    notes = []
    if voice.get("AgentActivationEnabled"):
        notes.append("Apps are allowed to listen for their wake word (Settings → Privacy → Voice activation).")
    if voice.get("AgentActivationOnLockScreenEnabled"):
        notes.append("Voice activation also works while the PC is locked.")
    return {"running": running, "voice_activation": voice, "notes": notes}


def report(meter=None):
    return {"t": time.time(), "drain_24h": meter.top() if meter else [], "silent": silent(), "listening": listeners(),
            "method": "CPU time per program over the last 24 hours (battery proxy). Screen, radios and GPU are not "
                      "attributed per program by the OS."}
