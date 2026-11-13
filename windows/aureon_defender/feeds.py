"""Threat-intel feeds. Online: refresh from free abuse.ch feeds (nothing about you is sent).
Offline: everything keeps working from the last cached copy.

  MalwareBazaar  recent malware SHA-256 hashes      -> reputation DB
  Feodo Tracker  botnet command-and-control IPs     -> network monitor
  URLhaus        malware-distribution hostnames     -> optional hosts-file DNS shield
"""
import json
import re
import socket
import time
import urllib.request
from pathlib import Path

from .core import data_dir

FEEDS = {
    "malwarebazaar": "https://bazaar.abuse.ch/export/txt/sha256/recent/",
    "feodo": "https://feodotracker.abuse.ch/downloads/ipblocklist.txt",
    "urlhaus": "https://urlhaus.abuse.ch/downloads/hostfile/",
}
UA = "aureon.defender"


def online(host="1.1.1.1", port=443, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(50_000_000).decode("utf-8", errors="ignore")


def parse_sha256(text):
    return sorted({l.strip().lower() for l in text.splitlines() if re.fullmatch(r"[0-9a-fA-F]{64}", l.strip())})


def parse_ips(text):
    return sorted({l.strip() for l in text.splitlines() if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", l.strip())})


def parse_hosts(text):
    out = set()
    for l in text.splitlines():
        m = re.match(r"^\s*(?:0\.0\.0\.0|127\.0\.0\.1)\s+([a-z0-9.-]+\.[a-z]{2,})\s*$", l, re.I)
        if m and m.group(1).lower() not in ("localhost",):
            out.add(m.group(1).lower())
    return sorted(out)


class Feeds:
    def __init__(self, root: Path = None, fetcher=fetch):
        self.root = root or (data_dir() / "feeds")
        self.root.mkdir(parents=True, exist_ok=True)
        self.fetcher = fetcher

    def _file(self, name):
        return self.root / f"{name}.json"

    def cached(self, name):
        try:
            return json.loads(self._file(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"t": 0, "items": []}

    def update(self, reputation=None):
        """Returns {feed: count or error}. Never raises."""
        report = {}
        for name, url in FEEDS.items():
            try:
                text = self.fetcher(url)
                items = {"malwarebazaar": parse_sha256, "feodo": parse_ips, "urlhaus": parse_hosts}[name](text)
                if not items:
                    raise ValueError("empty feed")
                self._file(name).write_text(json.dumps({"t": time.time(), "items": items}), encoding="utf-8")
                report[name] = len(items)
                if name == "malwarebazaar" and reputation:
                    reputation.add_bad([(h, "MalwareBazaar", None) for h in items])
            except Exception as e:
                report[name] = f"error: {e.__class__.__name__}"
        return report

    def bad_ips(self):
        return set(self.cached("feodo")["items"])

    def bad_hosts(self):
        return self.cached("urlhaus")["items"]

    def age_hours(self, name):
        t = self.cached(name)["t"]
        return None if not t else (time.time() - t) / 3600


# ---------------- optional hosts-file DNS shield ----------------
BEGIN, END = "# >>> aureon dns shield >>>", "# <<< aureon dns shield <<<"
HOSTS = Path(r"C:\Windows\System32\drivers\etc\hosts")


def render_hosts(current: str, domains) -> str:
    """Replace (or add) the Aureon block, leaving the user's own entries untouched."""
    pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n?", re.S)
    base = pat.sub("", current).rstrip("\r\n")
    if not domains:
        return base + "\n"
    block = "\n".join([BEGIN] + [f"0.0.0.0 {d}" for d in domains] + [END])
    return f"{base}\n\n{block}\n"


def apply_hosts(domains, hosts=HOSTS):
    cur = hosts.read_text(encoding="utf-8", errors="ignore") if hosts.exists() else ""
    new = render_hosts(cur, domains)
    if new != cur:
        hosts.write_text(new, encoding="utf-8")
    return len(domains)
