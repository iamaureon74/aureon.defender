"""Turn any picture into aureon.defender's icon set.

One photo becomes: the Windows .ico (title bar, taskbar, Start, installer), the window favicon, the toast icon,
and the phone home-screen icons (Android 192/512 + maskable, iPhone 180). The crop centres on the brightest
subject in the picture (a glowing figure, a lamp, a face in light) blended toward the middle so the scene around
it stays in frame, then rounds the corners into a soft squircle so it sits well beside other app icons.

Custom icons live in %LOCALAPPDATA%\\Aureon\\icon, a normal-permission folder Explorer and Action Center can read.
"""
import os
import shutil
import sys
from pathlib import Path

SIZES_ICO = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
PNGS = {"icon.png": 256, "icon-180.png": 180, "icon-192.png": 192, "icon-512.png": 512}


def custom_dir():
    base = os.environ.get("AUREON_ICON_DIR") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aureon" / "icon"
    return Path(base)


def bundled_dir():
    for p in (Path(getattr(sys, "_MEIPASS", "")) / "aureon_defender" / "ui", Path(__file__).parent / "ui"):
        if (p / "icon.png").exists():
            return p
    return Path(__file__).parent / "ui"


def find(name="icon.png"):
    """The custom icon if the user chose one, else the bundled one."""
    c = custom_dir() / name
    if c.exists():
        return c
    b = bundled_dir() / name
    return b if b.exists() else bundled_dir() / "icon.png"


def focus_point(im):
    """Brightness-weighted centre of the brightest 0.6% of pixels, in 0..1 coordinates."""
    g = im.convert("L")
    small = g.resize((max(1, g.width // 4), max(1, g.height // 4)))
    px = list(small.getdata())
    cut = sorted(px)[int(len(px) * 0.994)]
    sx = sy = n = 0
    w = small.width
    for i, v in enumerate(px):
        if v >= cut and v > 40:
            wgt = v - cut + 1
            sx += (i % w) * wgt
            sy += (i // w) * wgt
            n += wgt
    if not n:
        return 0.5, 0.5
    return sx / n / small.width, sy / n / small.height


def square_crop(im, zoom=0.72):
    fx, fy = focus_point(im)
    cx, cy = 0.55 * fx + 0.45 * 0.5, 0.55 * fy + 0.45 * 0.5          # keep the scene around the subject
    side = int(min(im.width, im.height) * zoom)
    left = min(max(int(cx * im.width - side / 2), 0), im.width - side)
    top = min(max(int(cy * im.height - side / 2), 0), im.height - side)
    return im.crop((left, top, left + side, top + side))


def squircle_mask(size, radius=0.235):
    from PIL import Image, ImageDraw
    k = 4                                                              # supersample for smooth edges
    m = Image.new("L", (size * k, size * k), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size * k - 1, size * k - 1), int(size * k * radius), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def render(square, size, rounded=True):
    from PIL import Image, ImageEnhance
    im = square.resize((size, size), Image.LANCZOS)
    if size <= 32:                                                    # small sizes need more punch to read
        im = ImageEnhance.Contrast(ImageEnhance.Brightness(im).enhance(1.25)).enhance(1.25)
    if not rounded:
        return im.convert("RGB")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im.convert("RGB"), (0, 0), squircle_mask(size))
    return out


def make_set(src, out_dir):
    """Writes icon.png, icon-180/192/512.png, icon-maskable-512.png and aureon.ico into out_dir. Returns the paths."""
    from PIL import Image, ImageOps
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if min(im.size) < 64:
            raise ValueError("that picture is too small for an icon")
        sq = square_crop(im)
    paths = {}
    for name, size in PNGS.items():
        p = out / name
        render(sq, size, rounded=(name != "icon-180.png")).save(p)   # iPhone rounds its own corners
        paths[name] = p
    mask = out / "icon-maskable-512.png"                              # Android adaptive: full bleed, OS crops it
    render(sq, 512, rounded=False).save(mask)
    paths["icon-maskable-512.png"] = mask
    ico = out / "aureon.ico"
    big = render(sq, 256)
    big.save(ico, sizes=[(s, s) for s in SIZES_ICO])
    paths["aureon.ico"] = ico
    return paths


def set_custom(src):
    """Makes the chosen picture the app icon for this user: window, taskbar, toasts and a Start menu shortcut."""
    tmp = custom_dir().with_name("icon.new")
    shutil.rmtree(tmp, ignore_errors=True)
    paths = make_set(src, tmp)
    shutil.rmtree(custom_dir(), ignore_errors=True)
    tmp.rename(custom_dir())
    apply_shell()
    return {k: str(custom_dir() / Path(v).name) for k, v in paths.items()}


def reset():
    shutil.rmtree(custom_dir(), ignore_errors=True)
    apply_shell()


def apply_shell():
    """Points the toast identity and the per-user Start shortcut at the current icon."""
    if os.name != "nt":
        return
    try:
        from .notify import register
        register()
    except Exception:
        pass
    if not getattr(sys, "frozen", False):
        return
    import subprocess
    ico = custom_dir() / "aureon.ico"
    lnk = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/aureon.defender.lnk"
    icon = str(ico) if ico.exists() else sys.executable
    q = lambda s: "'" + str(s).replace("'", "''") + "'"                 # noqa: E731
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(lnk)});$s.TargetPath={q(sys.executable)};"
          f"$s.Arguments='open';$s.IconLocation={q(icon)};$s.Description='aureon.defender';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, timeout=30,
                   creationflags=0x08000000)
