"""Power and load governor: keeps protection on while costing as little battery and responsiveness as possible.

Model (no AI, plain arithmetic):
  * Every task has a base interval T. The governor returns an effective interval T * m, where the multiplier m
    depends on power source, battery level and how busy the machine is.
  * Real-time sensors (file watch, ransomware tripwire, USB keyboard guard) are "critical": their multiplier is
    capped low so protection never meaningfully degrades. Heavy sweeps (radar, posture, assets, feeds) are
    "deferrable": they stretch a lot on battery and are postponed while the user is actively using the CPU.
  * Jitter of +/-10% spreads tasks so they don't all wake the CPU at the same instant. Each wake-up costs the CPU
    a transition out of a deep idle state; fewer, spread wake-ups let the processor stay in low-power states longer.
  * Load uses an exponentially-weighted moving average (alpha 0.3) so a single spike doesn't cause deferral.
  * A deferrable task is never postponed more than max_defer seconds, so nothing silently stops running.

Energy reasoning: average power ~ P_idle + sum(E_task / T_eff). Stretching heavy tasks' T_eff by 3x on low battery
cuts their share of energy by ~67% while the critical sensors stay near their normal cadence.
"""
import os
import random
import time

CRITICAL = {"realtime", "canary", "hid", "inbox", "devices_live"}
DEFERRABLE = {"radar", "posture", "assets", "feeds", "leaks", "devices", "persistence", "integrity", "report"}

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_PRIORITY_CLASS = 0x00000040
CREATE_NO_WINDOW = 0x08000000


def child_flags(background=True):
    """creationflags for helper processes (PowerShell, MpCmdRun): hidden and below-normal priority on Windows."""
    if os.name != "nt":
        return 0
    return CREATE_NO_WINDOW | (BELOW_NORMAL_PRIORITY_CLASS if background else 0)


def lower_own_priority():
    """Run the engine itself below normal CPU and low I/O priority so foreground apps and games never stutter."""
    try:
        import psutil
        p = psutil.Process()
        if os.name == "nt":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            try:
                p.ionice(psutil.IOPRIO_LOW)
            except Exception:
                pass
            _eco_qos()
        else:
            p.nice(10)
            try:
                p.ionice(psutil.IOPRIO_CLASS_BE, 7)
            except Exception:
                pass
        return True
    except Exception:
        return False


def _eco_qos():
    """Windows 11 EcoQoS: ask the scheduler to run this process on efficient cores at efficient clocks."""
    try:
        import ctypes
        from ctypes import wintypes

        class PPTS(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
        s = PPTS(1, PROCESS_POWER_THROTTLING_EXECUTION_SPEED, PROCESS_POWER_THROTTLING_EXECUTION_SPEED)
        k = ctypes.windll.kernel32
        ProcessPowerThrottling = 4
        k.SetProcessInformation(k.GetCurrentProcess(), ProcessPowerThrottling, ctypes.byref(s), ctypes.sizeof(s))
    except Exception:
        pass


class Governor:
    def __init__(self, probe=None, rng=None, max_defer=4 * 3600, busy=70.0):
        self.probe = probe or self._probe
        self.rng = rng or random.Random()
        self.max_defer = max_defer
        self.busy = busy
        self.load = None
        self.power = {"plugged": True, "percent": None}
        self.deferred_since = {}
        self._last = 0

    @staticmethod
    def _probe():
        import psutil
        b = None
        try:
            b = psutil.sensors_battery()
        except Exception:
            pass
        return {"cpu": psutil.cpu_percent(interval=None),
                "plugged": True if b is None else bool(b.power_plugged),
                "percent": None if b is None else b.percent}

    def sample(self, now=None):
        now = time.time() if now is None else now
        if now - self._last < 10:
            return
        self._last = now
        try:
            s = self.probe()
        except Exception:
            return
        cpu = float(s.get("cpu") or 0)
        self.load = cpu if self.load is None else 0.3 * cpu + 0.7 * self.load
        self.power = {"plugged": s.get("plugged", True), "percent": s.get("percent")}

    def mode(self):
        if self.power["plugged"]:
            return "ac"
        pct = self.power.get("percent")
        if pct is not None and pct <= 20:
            return "saver"
        return "battery"

    def multiplier(self, name):
        m = self.mode()
        if name in CRITICAL:
            return {"ac": 1.0, "battery": 1.0, "saver": 1.5}[m]
        if name in DEFERRABLE:
            return {"ac": 1.0, "battery": 2.0, "saver": 4.0}[m]
        return {"ac": 1.0, "battery": 1.5, "saver": 2.5}[m]

    def interval(self, name, base):
        eff = base * self.multiplier(name)
        if name in CRITICAL:
            return eff
        return eff * self.rng.uniform(0.9, 1.1)

    def should_defer(self, name, now=None):
        """Postpone heavy sweeps while the user is busy (EWMA CPU above threshold), bounded by max_defer."""
        if name not in DEFERRABLE or self.load is None or self.load < self.busy:
            self.deferred_since.pop(name, None)
            return False
        now = time.time() if now is None else now
        first = self.deferred_since.setdefault(name, now)
        if now - first >= self.max_defer:
            self.deferred_since.pop(name, None)
            return False
        return True

    def snapshot(self):
        return {"mode": self.mode(), "load": None if self.load is None else round(self.load, 1), **self.power,
                "deferred": sorted(self.deferred_since)}
