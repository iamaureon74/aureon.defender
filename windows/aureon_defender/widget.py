"""Desktop widget: big clock, date, live CPU/RAM/battery and the Aureon shield state, drawn straight on the
wallpaper. Transparent, click-through, hidden from the taskbar and Alt-Tab, kept behind normal windows.
About 25 MB of RAM. Settings live in %APPDATA%/Aureon/widget.json (written by Studio presets).
"""
import ctypes
import json
import os
import time
import tkinter as tk
from datetime import datetime

from .core import data_dir, user_dir
from .studio import WIDGET_DEFAULT

KEY = "#010203"          # transparency key colour (never used by real content)


def load_cfg():
    try:
        return {**WIDGET_DEFAULT, **json.loads((user_dir() / "widget.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(WIDGET_DEFAULT)


def _cfg_mtime():
    try:
        return (user_dir() / "widget.json").stat().st_mtime
    except OSError:
        return None


def shield_line():
    try:
        st = json.loads((data_dir() / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Shield offline", False
    age = time.time() - st.get("heartbeat", 0)
    if age > 30:
        return "Shield not running", False
    c = st.get("counts", {})
    net = "online" if st.get("online") else "offline mode"
    return f"Shield active  ·  {c.get('scanned', 0)} scanned  ·  {c.get('quarantined', 0)} blocked  ·  {net}", True


def fmt_time(cfg, now):
    if cfg["hours"] == 24:
        return now.strftime("%H:%M:%S" if cfg["show_seconds"] else "%H:%M")
    return now.strftime("%I:%M:%S" if cfg["show_seconds"] else "%I:%M").lstrip("0")


class Widget:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_cfg()
        self.mtime = _cfg_mtime()
        if os.name == "nt":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)     # crisp text, real pixel positions on scaled displays
            except (AttributeError, OSError):
                pass
        self.root = tk.Tk()
        self.root.title("Aureon Widget")
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.root.attributes("-alpha", self.cfg["opacity"])
        c = self.cfg
        f, size = c["font"], c["clock_size"]
        self.clock = tk.Label(self.root, font=(f, size), fg=c["color"], bg=KEY)
        self.date = tk.Label(self.root, font=(f, max(14, size // 4)), fg=c["dim"], bg=KEY)
        self.stats = tk.Label(self.root, font=(c["mono"], max(10, size // 9)), fg=c["dim"], bg=KEY, justify="left")
        self.shield = tk.Label(self.root, font=(c["mono"], max(10, size // 9)), fg=c["dim"], bg=KEY)
        anchor = "e" if "right" in c["position"] else "center" if c["position"] == "center" else "w"
        for w, on in ((self.clock, True), (self.date, c["show_date"]), (self.stats, c["show_stats"]), (self.shield, c["show_shield"])):
            if on:
                w.pack(anchor=anchor)
        self.tick()                       # fill the labels first so the window is sized to real text
        self.root.update_idletasks()
        self._place()
        self.root.update()
        self._win32_style()

    def _place(self):
        r = self.root
        r.update_idletasks()
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = max(r.winfo_reqwidth(), 10), max(r.winfo_reqheight(), 10)
        m = 48
        pos = self.cfg["position"]
        x = m if "left" in pos else sw - w - m if "right" in pos else (sw - w) // 2
        y = m if "top" in pos else sh - h - m - 48 if "bottom" in pos else (sh - h) // 2 - 60
        r.geometry(f"{w}x{h}+{x}+{y}")

    def _win32_style(self):
        if os.name != "nt":
            return
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT, WS_EX_LAYERED, WS_EX_NOACTIVATE = -20, 0x80, 0x20, 0x80000, 0x08000000
        st = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, st | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE)
        self.hwnd = hwnd
        self._to_bottom()

    def _to_bottom(self):
        if os.name == "nt" and getattr(self, "hwnd", None):
            HWND_BOTTOM, SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 1, 0x1, 0x2, 0x10
            ctypes.windll.user32.SetWindowPos(self.hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

    def stats_text(self):
        import psutil
        b = psutil.sensors_battery()
        bat = f"   BAT {b.percent:.0f}%{' +' if b.power_plugged else ''}" if b else ""
        return f"CPU {psutil.cpu_percent():>3.0f}%   RAM {psutil.virtual_memory().percent:>3.0f}%{bat}"

    def tick(self):
        now = datetime.now()
        first = not getattr(self, "_ticked", False)
        self._ticked = True
        self.clock.config(text=fmt_time(self.cfg, now))
        self.date.config(text=now.strftime("%A, %d %B"))
        if self.cfg["show_stats"] and (first or now.second % 2 == 0):
            self.stats.config(text=self.stats_text())
        if self.cfg["show_shield"] and (first or now.second % 5 == 0):
            text, ok = shield_line()
            self.shield.config(text=("●  " if ok else "○  ") + text)
        if now.second % 30 == 0:
            self._to_bottom()
        if now.second % 3 == 0 and _cfg_mtime() != self.mtime:     # Studio changed the widget: rebuild
            self.root.destroy()
            return
        self.root.after(1000 - now.microsecond // 1000, self.tick)

    def run(self):
        self.root.mainloop()


def main():
    """Runs forever; rebuilds when widget.json changes, idles while disabled."""
    while True:
        cfg = load_cfg()
        if cfg.get("enabled", True):
            Widget(cfg).run()
        else:
            time.sleep(3)
