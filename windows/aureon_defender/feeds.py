"""Threat-intel feeds from abuse.ch. Online: refresh (nothing about you is sent). Offline: the cached copy keeps working.

abuse.ch retired its public download lists in 2026 (they answer 410 Gone). What's left:
  Feodo Tracker  botnet command-and-control IPs                  public, no key
  MalwareBazaar  newest malware SHA-256 hashes -> reputation DB  API, needs a free Auth-Key
  URLhaus        live malware-distribution hosts -> DNS shield   API, needs a free Auth-Key
  ThreatFox      fresh C2 servers and malicious domains          API, needs a free Auth-Key
  LOLDrivers     signed drivers known to be abused to kill security tools   public, no key (loldrivers.io)
Get the key at https://auth.abuse.ch/ (sign in, then "Optional" > Auth-Key) and paste it in Settings > Threat feeds.
Indicators accumulate across refreshes and expire after 30 days, so short API windows still build a full list.
"""
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .core import data_dir

FEODO = "https://feodotracker.abuse.ch/downloads/ipblocklist.txt"
SOURCES = {
    "feodo":         {"url": FEODO, "key": False},
    "malwarebazaar": {"url": "https://mb-api.abuse.ch/api/v1/", "key": True, "form": {"query": "get_recent", "selector": "time"}},
    "urlhaus":       {"url": "https://urlhaus-api.abuse.ch/v1/urls/recent/", "key": True},
    "threatfox":     {"url": "https://threatfox-api.abuse.ch/api/v1/", "key": True, "json": {"query": "get_iocs", "days": 1}},
    "loldrivers":    {"url": "https://www.loldrivers.io/api/drivers.json", "key": False},
}
FEEDS = {k: v["url"] for k, v in SOURCES.items()}      # kept for callers that list feed names
UA = "aureon.defender"
KEEP_DAYS = 30
KEY_HELP = "https://auth.abuse.ch/"


class NeedsKey(Exception):
    pass


def online(host="1.1.1.1", port=443, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def fetch(url, form=None, json_body=None, key=None, timeout=30):
    headers = {"User-Agent": UA}
    data = None
    if key:
        headers["Auth-Key"] = key
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(50_000_000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise NeedsKey("abuse.ch refused the Auth-Key" if key else "needs a free abuse.ch Auth-Key") from None
        raise


def _is_ip(s):
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def parse_sha256(text):
    return sorted({l.strip().lower() for l in text.splitlines() if re.fullmatch(r"[0-9a-fA-F]{64}", l.strip())})


def parse_ips(text):
    return sorted({l.strip() for l in text.splitlines() if _is_ip(l.strip())})


def parse_hosts(text):
    out = set()
    for l in text.splitlines():
        m = re.match(r"^\s*(?:0\.0\.0\.0|127\.0\.0\.1)\s+([a-z0-9.-]+\.[a-z]{2,})\s*$", l, re.I)
        if m and m.group(1).lower() not in ("localhost",):
            out.add(m.group(1).lower())
    return sorted(out)


def _api(text):
    d = json.loads(text or "{}")
    st = d.get("query_status")
    if st in ("unknown_auth_key", "invalid_auth_key"):
        raise NeedsKey("abuse.ch refused the Auth-Key")
    if st not in ("ok", "no_results", None):
        raise ValueError(f"abuse.ch said {st}")
    return d


def parse_bazaar(text):
    """-> {"hashes": [(sha256, signature)]}"""
    d = _api(text)
    rows = d.get("data") or []
    return {"hashes": [(r["sha256_hash"].lower(), r.get("signature")) for r in rows if isinstance(r, dict) and r.get("sha256_hash")]}


def parse_urlhaus(text):
    """-> {"hosts": [...], "ips": [...]} for URLs still online."""
    d = _api(text)
    hosts, ips = set(), set()
    for u in d.get("urls") or []:
        if u.get("url_status") not in ("online", None):
            continue
        h = (u.get("host") or urllib.parse.urlparse(u.get("url", "")).hostname or "").lower()
        if h:
            (ips if _is_ip(h) else hosts).add(h)
    return {"hosts": sorted(hosts), "ips": sorted(ips)}


def parse_threatfox(text):
    d = _api(text)
    hosts, ips = set(), set()
    for r in d.get("data") or []:
        ioc, typ = str(r.get("ioc", "")), r.get("ioc_type", "")
        if typ == "ip:port":
            ips.add(ioc.rsplit(":", 1)[0])
        elif typ == "domain":
            hosts.add(ioc.lower())
        elif typ == "url":
            h = (urllib.parse.urlparse(ioc).hostname or "").lower()
            if h:
                (ips if _is_ip(h) else hosts).add(h)
    return {"hosts": sorted(hosts), "ips": sorted(ips)}


def parse_loldrivers(text):
    """loldrivers.io drivers.json -> {"hashes": [(sha256, label)]}. Each entry lists KnownVulnerableSamples."""
    d = json.loads(text)
    if not isinstance(d, list):
        raise ValueError("unexpected LOLDrivers format")
    out = {}
    for drv in d:
        if not isinstance(drv, dict):
            continue
        cat = str(drv.get("Category") or "vulnerable driver").lower()
        for smp in drv.get("KnownVulnerableSamples") or []:
            h = str((smp or {}).get("SHA256") or "").lower()
            if re.fullmatch(r"[0-9a-f]{64}", h):
                name = (smp.get("Filename") or smp.get("OriginalFilename") or "driver").lower()
                out[h] = f"{'malicious' if 'malicious' in cat else 'vulnerable'} driver {name}"
    return {"hashes": sorted(out.items())}


class Feeds:
    def __init__(self, root: Path = None, fetcher=fetch):
        self.root = root or (data_dir() / "feeds")
        self.root.mkdir(parents=True, exist_ok=True)
        self.fetcher = fetcher

    def _file(self, name):
        return self.root / f"{name}.json"

    def cached(self, name):
        """{"t": last refresh, "items": [...]} - the union of what's been seen in the last KEEP_DAYS."""
        try:
            d = json.loads(self._file(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"t": 0, "items": []}
        items = d.get("items", [])
        if isinstance(items, dict):
            items = sorted(items)
        return {"t": d.get("t", 0), "items": items}

    def _merge(self, name, new_items, now):
        try:
            d = json.loads(self._file(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        seen = d.get("items", {})
        if isinstance(seen, list):                         # older cache format
            seen = {i: d.get("t", now) for i in seen}
        for i in new_items:
            seen[i] = now
        cut = now - KEEP_DAYS * 86400
        seen = {i: t for i, t in seen.items() if t >= cut}
        self._file(name).write_text(json.dumps({"t": now, "items": seen}), encoding="utf-8")
        return len(seen)

    def update(self, reputation=None, key=""):
        """Returns {feed: count | "needs key" | "error: ..."}. Never raises."""
        key = (key or "").strip()
        report, now = {}, time.time()
        for name, src in SOURCES.items():
            if src["key"] and not key:
                report[name] = "needs key"
                continue
            try:
                text = self.fetcher(src["url"], form=src.get("form"), json_body=src.get("json"), key=key if src["key"] else None)
                if name == "feodo":
                    ips = parse_ips(text)
                    if not ips:
                        raise ValueError("empty feed")
                    report[name] = self._merge("feodo", ips, now)
                elif name == "loldrivers":
                    rows = parse_loldrivers(text)["hashes"]
                    if not rows:
                        raise ValueError("empty feed")
                    if reputation:
                        reputation.add_bad([(h, "LOLDrivers", label) for h, label in rows])
                    report[name] = self._merge("loldrivers", [h for h, _ in rows], now)
                elif name == "malwarebazaar":
                    rows = parse_bazaar(text)["hashes"]
                    if reputation and rows:
                        reputation.add_bad([(h, "MalwareBazaar", sig) for h, sig in rows])
                    report[name] = self._merge("malwarebazaar", [h for h, _ in rows], now)
                else:
                    got = (parse_urlhaus if name == "urlhaus" else parse_threatfox)(text)
                    self._merge(f"{name}_hosts", got["hosts"], now)
                    self._merge(f"{name}_ips", got["ips"], now)
                    report[name] = len(got["hosts"]) + len(got["ips"])
            except NeedsKey as e:
                report[name] = str(e)
            except Exception as e:
                report[name] = f"error: {e.__class__.__name__}"
        return report

    def bad_ips(self):
        return set(self.cached("feodo")["items"]) | set(self.cached("urlhaus_ips")["items"]) | set(self.cached("threatfox_ips")["items"])

    def bad_hosts(self):
        return sorted(set(self.cached("urlhaus_hosts")["items"]) | set(self.cached("threatfox_hosts")["items"]))

    def age_hours(self, name):
        t = max(self.cached(n)["t"] for n in ([f"{name}_hosts", f"{name}_ips"] if name in ("urlhaus", "threatfox") else [name]))

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
