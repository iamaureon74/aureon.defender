"""Browsers from every region, installable in one click through Windows' package manager (winget).

Every id below was checked against the winget catalogue. Installs come from the vendor's own installer as
listed in winget; Aureon downloads nothing itself. Each entry says plainly who makes it, where, and how private
it is by default, so people can choose knowingly.
"""
import shutil
import subprocess

NOWIN = 0x08000000
# (winget id, name, made in, by, privacy: best | good | standard | caution, note)
CATALOG = [
    ("TorProject.TorBrowser", "Tor Browser", "Global (non-profit)", "The Tor Project", "best", "Routes through Tor; strongest anonymity"),
    ("MullvadVPN.MullvadBrowser", "Mullvad Browser", "Sweden", "Mullvad + Tor Project", "best", "Tor Browser's anti-fingerprinting without Tor"),
    ("LibreWolf.LibreWolf", "LibreWolf", "Global (community)", "LibreWolf community", "best", "Firefox with telemetry removed, uBlock built in"),
    ("Brave.Brave", "Brave", "United States", "Brave Software", "good", "Blocks ads and trackers by default"),
    ("Mozilla.Firefox", "Firefox", "United States", "Mozilla (non-profit)", "good", "Independent engine; strong tracker protection"),
    ("Mozilla.Firefox.ESR", "Firefox ESR", "United States", "Mozilla", "good", "Long-term support Firefox"),
    ("DuckDuckGo.DesktopBrowser", "DuckDuckGo", "United States", "DuckDuckGo", "good", "Tracker blocking and cookie-pop-up handling"),
    ("eloston.ungoogled-chromium", "Ungoogled Chromium", "Global (community)", "community", "good", "Chromium with Google services removed"),
    ("Zen-Team.Zen-Browser", "Zen", "Global (community)", "Zen team", "good", "Firefox-based, calm design"),
    ("Ablaze.Floorp", "Floorp", "Japan", "Ablaze", "good", "Firefox-based, customisable"),
    ("Waterfox.Waterfox", "Waterfox", "United Kingdom", "Waterfox / System1", "good", "Firefox-based"),
    ("MoonchildProductions.PaleMoon", "Pale Moon", "Netherlands", "Moonchild Productions", "standard", "Independent Goanna engine"),
    ("Vivaldi.Vivaldi", "Vivaldi", "Norway", "Vivaldi Technologies", "standard", "Very customisable, tracker blocker built in"),
    ("Ecosia.EcosiaBrowser", "Ecosia", "Germany", "Ecosia", "standard", "Plants trees with search revenue"),
    ("Alex313031.Thorium", "Thorium", "United States", "Alex313031", "standard", "Speed-optimised Chromium"),
    ("TheBrowserCompany.Arc", "Arc", "United States", "The Browser Company", "standard", "Sidebar-first design; needs an account"),
    ("Google.Chrome", "Chrome", "United States", "Google", "caution", "Fast and compatible; Google account and ad data"),
    ("Microsoft.Edge", "Edge", "United States", "Microsoft", "caution", "Built into Windows; Microsoft data collection"),
    ("Opera.Opera", "Opera", "Norway (owned in China)", "Opera / Kunlun", "caution", "Free VPN-like proxy; owned by a Chinese consortium"),
    ("Opera.OperaGX", "Opera GX", "Norway (owned in China)", "Opera / Kunlun", "caution", "Gaming-styled Opera"),
    ("Yandex.Browser", "Yandex Browser", "Russia", "Yandex", "caution", "Russia's main browser; subject to Russian data law"),
    ("NAVER.Whale", "Naver Whale", "South Korea", "NAVER", "standard", "Korea's own browser"),
    ("CentStudio.CentBrowser", "Cent Browser", "China", "Cent Studio", "caution", "Chromium-based, popular in China"),
    ("Maxthon.Maxthon", "Maxthon", "China / Singapore", "Maxthon", "caution", "Long-running Chinese browser"),
    ("Tencent.QQBrowser", "QQ Browser", "China", "Tencent", "caution", "Tencent; history of data-collection findings"),
    ("360.360SE", "360 Secure Browser", "China", "Qihoo 360", "caution", "Qihoo 360; subject to Chinese data law"),
]
ORDER = {"best": 0, "good": 1, "standard": 2, "caution": 3}


def winget():
    return shutil.which("winget")


def installed_ids():
    w = winget()
    if not w:
        return set()
    r = subprocess.run([w, "list", "--accept-source-agreements", "--disable-interactivity"], capture_output=True, text=True,
                       timeout=120, creationflags=NOWIN, encoding="utf-8", errors="ignore")
    ids = set()
    for line in r.stdout.splitlines():
        for wid, *_ in CATALOG:
            if f" {wid} " in f" {line} ":
                ids.add(wid)
    return ids


def catalog(installed=None):
    inst = installed if installed is not None else installed_ids()
    rows = [{"id": i, "name": n, "region": r, "maker": m, "privacy": p, "note": t, "installed": i in inst} for i, n, r, m, p, t in CATALOG]
    return sorted(rows, key=lambda b: (ORDER[b["privacy"]], b["name"]))


def install(wid):
    """Starts the vendor installer through winget. Returns the process (runs in the background)."""
    if wid not in {c[0] for c in CATALOG}:
        raise ValueError("not in the catalogue")
    w = winget()
    if not w:
        raise RuntimeError("Windows Package Manager (winget) isn't available on this PC")
    return subprocess.Popen([w, "install", "--id", wid, "-e", "--accept-package-agreements", "--accept-source-agreements",
                             "--disable-interactivity"], creationflags=NOWIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
