"""Aureon Studio: make the laptop look good without multi-GB theming apps.

Everything is a per-user (HKCU) setting Windows already supports, applied directly, with a snapshot taken
first so `restore()` puts the machine back exactly as it was. Nothing needs admin rights.

  theme       light/dark for apps and for Windows itself
  accent      accent colour on Start, taskbar and title bars
  transparency, taskbar alignment (left/centre), seconds on the taskbar clock
  time/date   12h/24h, short date pattern
  wallpaper   generated in-app (aurora, mesh, dusk, grain, mono) at your screen resolution, or your own image
  fonts       install .ttf/.otf for the current user; widgets use any installed family
  widgets     desktop clock/date/stats/shield (see widget.py)
"""
import colorsys
import ctypes
import json
import math
import os
import random
import shutil
from pathlib import Path

from .core import user_dir

PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
DWM = r"Software\Microsoft\Windows\DWM"
INTL = r"Control Panel\International"
DESKTOP = r"Control Panel\Desktop"
FONTS = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"


# ---------------- registry backends ----------------
class WinReg:
    """Real HKCU."""
    def get(self, key, name):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                return winreg.QueryValueEx(k, name)
        except OSError:
            return None

    def set(self, key, name, value, kind):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, kind, value)

    def delete(self, key, name):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass


class MemReg:
    """In-memory registry for tests and previews."""
    def __init__(self, data=None):
        self.data = data or {}

    def get(self, key, name):
        return self.data.get((key, name))

    def set(self, key, name, value, kind):
        self.data[(key, name)] = (value, kind)

    def delete(self, key, name):
        self.data.pop((key, name), None)


REG_SZ, REG_DWORD = 1, 4


def broadcast(area):
    """Tell Explorer and apps a setting changed (WM_SETTINGCHANGE)."""
    if os.name != "nt":
        return
    res = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, area, 0x0002, 2000, ctypes.byref(res))


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def abgr_dword(hexcolor):
    r, g, b = hex_to_rgb(hexcolor)
    return 0xFF000000 | (b << 16) | (g << 8) | r


class Studio:
    def __init__(self, reg=None, backup=None, apply_wallpaper=None, live=True):
        self.reg = reg or WinReg()
        self.backup_path = backup or (user_dir() / "studio_backup.json")
        self.apply_wallpaper_fn = apply_wallpaper or self._spi_wallpaper
        self.live = live                  # broadcast changes (off in tests)

    # ---------- snapshot / restore ----------
    def _remember(self, key, name):
        b = self._load_backup()
        k = f"{key}|{name}"
        if k not in b:                     # first change wins: that's the original value
            cur = self.reg.get(key, name)
            b[k] = list(cur) if cur else None
            self.backup_path.write_text(json.dumps(b, indent=1), encoding="utf-8")

    def _load_backup(self):
        try:
            return json.loads(self.backup_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _set(self, key, name, value, kind):
        self._remember(key, name)
        self.reg.set(key, name, value, kind)

    def restore(self):
        b = self._load_backup()
        for k, v in b.items():
            key, name = k.split("|", 1)
            if v is None:
                self.reg.delete(key, name)
            else:
                self.reg.set(key, name, v[0], v[1])
        wp = b.get(f"{DESKTOP}|WallPaper")
        if wp and wp[0]:
            self.apply_wallpaper_fn(wp[0])
        self.backup_path.unlink(missing_ok=True)
        self._refresh("ImmersiveColorSet", "intl", "TraySettings", "WindowsThemeElement")
        return len(b)

    def _refresh(self, *areas):
        if self.live:
            for a in areas:
                broadcast(a)

    # ---------- settings ----------
    def set_theme(self, apps="dark", system="dark"):
        self._set(PERSONALIZE, "AppsUseLightTheme", 0 if apps == "dark" else 1, REG_DWORD)
        self._set(PERSONALIZE, "SystemUsesLightTheme", 0 if system == "dark" else 1, REG_DWORD)
        self._refresh("ImmersiveColorSet", "WindowsThemeElement")

    def set_accent(self, hexcolor, on_taskbar=True, on_titlebars=True):
        v = abgr_dword(hexcolor)
        self._set(DWM, "AccentColor", v, REG_DWORD)
        self._set(DWM, "ColorizationColor", 0xC4000000 | (v & 0x00FFFFFF), REG_DWORD)
        self._set(DWM, "ColorPrevalence", 1 if on_titlebars else 0, REG_DWORD)
        self._set(PERSONALIZE, "ColorPrevalence", 1 if on_taskbar else 0, REG_DWORD)
        self._refresh("ImmersiveColorSet")

    def set_transparency(self, on=True):
        self._set(PERSONALIZE, "EnableTransparency", 1 if on else 0, REG_DWORD)
        self._refresh("ImmersiveColorSet")

    def set_taskbar(self, align="center", seconds=False):
        self._set(ADVANCED, "TaskbarAl", 1 if align == "center" else 0, REG_DWORD)
        self._set(ADVANCED, "ShowSecondsInSystemClock", 1 if seconds else 0, REG_DWORD)
        self._refresh("TraySettings")

    def set_time_format(self, hours=24, date="yyyy-MM-dd"):
        short, long_ = ("HH:mm", "HH:mm:ss") if hours == 24 else ("h:mm tt", "h:mm:ss tt")
        self._set(INTL, "sShortTime", short, REG_SZ)
        self._set(INTL, "sTimeFormat", long_, REG_SZ)
        self._set(INTL, "iTime", "1" if hours == 24 else "0", REG_SZ)
        self._set(INTL, "sShortDate", date, REG_SZ)
        self._refresh("intl")

    def set_wallpaper(self, path, style="fill"):
        styles = {"fill": ("10", "0"), "fit": ("6", "0"), "stretch": ("2", "0"), "center": ("0", "0"), "span": ("22", "0")}
        ws, tile = styles[style]
        self._set(DESKTOP, "WallpaperStyle", ws, REG_SZ)
        self._set(DESKTOP, "TileWallpaper", tile, REG_SZ)
        self._remember(DESKTOP, "WallPaper")
        self.apply_wallpaper_fn(str(path))

    @staticmethod
    def _spi_wallpaper(path):
        if os.name == "nt":
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 0x01 | 0x02)   # SPI_SETDESKWALLPAPER, update+broadcast

    def install_font(self, src):
        """Per-user font install (no admin)."""
        src = Path(src)
        if src.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            raise ValueError("fonts must be .ttf, .otf or .ttc")
        dst_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Microsoft/Windows/Fonts"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.copy(src, dst)
        name = f"{src.stem} ({'OpenType' if src.suffix.lower() == '.otf' else 'TrueType'})"
        self.reg.set(FONTS, name, str(dst), REG_SZ)       # fonts are additive; not part of restore
        if self.live and os.name == "nt":
            ctypes.windll.gdi32.AddFontResourceW(str(dst))
            broadcast("fonts")
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 2000, None)  # WM_FONTCHANGE
        return str(dst)

    def current(self):
        def v(k, n, default=None):
            r = self.reg.get(k, n)
            return r[0] if r else default
        acc = v(DWM, "AccentColor")
        return {
            "apps": "light" if v(PERSONALIZE, "AppsUseLightTheme", 1) else "dark",
            "system": "light" if v(PERSONALIZE, "SystemUsesLightTheme", 0) else "dark",
            "accent": "#%02x%02x%02x" % (acc & 0xFF, (acc >> 8) & 0xFF, (acc >> 16) & 0xFF) if acc is not None else None,
            "transparency": bool(v(PERSONALIZE, "EnableTransparency", 1)),
            "taskbar": "center" if v(ADVANCED, "TaskbarAl", 1) else "left",
            "seconds": bool(v(ADVANCED, "ShowSecondsInSystemClock", 0)),
            "time": v(INTL, "sShortTime"), "date": v(INTL, "sShortDate"),
            "wallpaper": v(DESKTOP, "WallPaper"),
            "has_backup": self.backup_path.exists(),
        }

    def apply_preset(self, name, width=None, height=None, out_dir=None):
        p = PRESETS[name]
        w, h = (width, height) if width else screen_size()
        out = Path(out_dir or user_dir() / "wallpapers")
        out.mkdir(parents=True, exist_ok=True)
        img = out / f"{name.lower()}-{w}x{h}.png"
        generate_wallpaper(p["wallpaper"], p["palette"], w, h, img, seed=p.get("seed", 7))
        self.set_theme(p["mode"], p["mode"])
        self.set_accent(p["accent"], on_taskbar=p.get("accent_taskbar", False), on_titlebars=True)
        self.set_transparency(True)
        self.set_taskbar(p.get("taskbar", "center"), p.get("seconds", False))
        self.set_wallpaper(img)
        widget_cfg = dict(WIDGET_DEFAULT, **p["widget"])
        (user_dir() / "widget.json").write_text(json.dumps(widget_cfg, indent=1), encoding="utf-8")
        return {"wallpaper": str(img), "widget": widget_cfg}


def screen_size():
    if os.name == "nt":
        u = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    return 1920, 1080


# ---------------- presets ----------------
WIDGET_DEFAULT = {"enabled": True, "position": "top-left", "font": "Segoe UI Variable Display", "mono": "Cascadia Mono",
                  "color": "#ffffff", "dim": "#b8c2cc", "clock_size": 96, "show_seconds": False, "hours": 24,
                  "show_date": True, "show_stats": True, "show_shield": True, "opacity": 0.92}

PRESETS = {
    "Ember":    {"mode": "dark", "accent": "#c9803f", "wallpaper": "ember", "palette": ["#060608", "#1a0f0a", "#c9803f", "#ffd9b0"],
                 "taskbar": "center", "seed": 11,
                 "widget": {"font": "Bahnschrift Light", "mono": "Cascadia Mono", "color": "#ffd9b0", "dim": "#c9803f",
                            "position": "top-left", "hours": 12, "clock_size": 112}},
    "Aurora":   {"mode": "dark", "accent": "#3ddc97", "wallpaper": "aurora", "palette": ["#04121c", "#0b3d4a", "#3ddc97", "#7b5cff"],
                 "widget": {"font": "Bahnschrift Light", "color": "#e8fff6", "dim": "#8fd9bd", "position": "top-left"}},
    "Obsidian": {"mode": "dark", "accent": "#8ab4ff", "wallpaper": "grain", "palette": ["#0b0d12", "#151a24", "#2a3346", "#8ab4ff"],
                 "widget": {"font": "Segoe UI Variable Display Light", "color": "#f2f4f8", "dim": "#8792a6", "position": "center", "clock_size": 140}},
    "Dusk":     {"mode": "dark", "accent": "#ff8a5c", "wallpaper": "dusk", "palette": ["#1a1033", "#5b2a6e", "#ff8a5c", "#ffd59e"],
                 "widget": {"font": "Georgia", "color": "#fff4e8", "dim": "#ffcfa8", "position": "bottom-left"}},
    "Paper":    {"mode": "light", "accent": "#2f6f62", "wallpaper": "mono", "palette": ["#f3f1ec", "#e3dfd6", "#c9c2b4", "#2f6f62"],
                 "widget": {"font": "Segoe UI Variable Display Semibold", "color": "#23312d", "dim": "#5d6b66", "position": "top-right"}},
    "Lagoon":   {"mode": "light", "accent": "#0078a8", "wallpaper": "mesh", "palette": ["#dff6ff", "#9fe3f5", "#45b6e0", "#ffd3a8"],
                 "widget": {"font": "Bahnschrift", "color": "#06324a", "dim": "#2b6a86", "position": "top-left"}},
    "Terminal": {"mode": "dark", "accent": "#5af78e", "wallpaper": "grain", "palette": ["#050806", "#0a120c", "#12301a", "#5af78e"],
                 "widget": {"font": "Cascadia Mono", "color": "#5af78e", "dim": "#3a9e5c", "position": "bottom-right", "show_seconds": True}},
}


# ---------------- wallpaper generator ----------------
def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _ramp(cols, t):
    t = max(0.0, min(1.0, t)) * (len(cols) - 1)
    i = min(int(t), len(cols) - 2)
    return _lerp(cols[i], cols[i + 1], t - i)


def generate_wallpaper(style, palette, w, h, out, seed=7):
    """Render at 1/4 resolution with numpy-free math, then upscale smoothly and add grain."""
    from PIL import Image, ImageFilter
    rnd = random.Random(seed)
    cols = [hex_to_rgb(c) for c in palette]
    sw, sh = max(64, w // 8), max(36, h // 8)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    blobs = [(rnd.random() * sw, rnd.random() * sh, (0.35 + rnd.random() * 0.5) * max(sw, sh), cols[i % len(cols)])
             for i in range(5)]
    for y in range(sh):
        for x in range(sw):
            u, v = x / sw, y / sh
            if style == "ember":
                # void sky, warm glow rising from a low horizon, faint ember haze
                horizon = math.exp(-((v - 1.02) ** 2) / 0.09) * (0.75 + 0.25 * math.sin(u * 2.4 + 0.6))
                core = math.exp(-(((u - 0.62) * sw / sh) ** 2 * 0.6 + (v - 0.95) ** 2) / 0.05)
                c = _lerp(cols[0], cols[1], min(1.0, v * 0.9))
                c = _lerp(c, cols[2], min(1.0, horizon * 0.85))
                c = _lerp(c, cols[3], min(1.0, core * 0.55))
            elif style == "aurora":
                band = sum(math.exp(-((v - (0.35 + 0.12 * k + 0.08 * math.sin(u * 6.2 + k * 1.7))) ** 2) / 0.006) * (0.9 - 0.25 * k)
                           for k in range(3))
                base = _ramp(cols[:2], v * 0.9)
                glow = _ramp(cols[2:], (math.sin(u * 3 + v * 2) + 1) / 2)
                c = _lerp(base, glow, min(1.0, band))
            elif style == "dusk":
                c = _ramp(cols, (v + 0.15 * math.sin(u * 3.1)) * 1.05)
                sun = math.exp(-(((u - 0.72) * sw / sh) ** 2 + (v - 0.62) ** 2) / 0.01)
                c = _lerp(c, cols[-1], min(1.0, sun * 1.4))
            elif style == "mono":
                c = _ramp(cols[:3], v * 0.7 + 0.1 * math.sin(u * 2.5))
            else:  # mesh / grain: soft blob field
                acc, wsum = [0.0, 0.0, 0.0], 0.0
                for bx, by, r, bc in blobs:
                    wgt = math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (r * r))
                    wsum += wgt
                    for i in range(3):
                        acc[i] += bc[i] * wgt
                mix = tuple(a / wsum for a in acc) if wsum else cols[0]
                c = _lerp(cols[0], mix, 0.55 if style == "grain" else 0.95)
            px[x, y] = c
    img = img.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(radius=max(2, w // 400)))
    if style == "ember":                          # sparks: small soft glowing dots drifting up from the horizon
        from PIL import ImageDraw
        sparks = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(sparks)
        glow = hex_to_rgb(palette[3])
        for _ in range(max(40, w * h // 26000)):
            y = int(h * (0.35 + 0.65 * rnd.random() ** 0.6))
            x = int(w * rnd.random())
            r = max(1, int(w / 1500 * (0.6 + rnd.random() * 1.8)))
            a = int(40 + 180 * (y / h) * rnd.random())
            d.ellipse((x - r, y - r, x + r, y + r), fill=glow + (a,))
        sparks = sparks.filter(ImageFilter.GaussianBlur(radius=max(1, w // 1600)))
        img = Image.alpha_composite(img.convert("RGBA"), sparks).convert("RGB")
    grain = Image.effect_noise((w, h), 10 if style in ("grain", "mono") else 5).convert("RGB")
    img = Image.blend(img, grain, 0.035)
    img.save(out, optimize=True)
    return out
