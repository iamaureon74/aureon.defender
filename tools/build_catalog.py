"""Regenerate stack.json, docs/CATALOG.md and the upstream/ submodule pins.

Usage:  python tools/build_catalog.py <path-to-rasberry-pi-checkout> [--pin]

--pin writes .gitmodules and stages gitlinks (same upstream commits the
rasberry-pi repo pinned), without cloning anything.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from picks import PICKS  # noqa: E402

PLATFORM_NAMES = {"L": "Linux laptop", "W": "Windows laptop", "M": "macOS", "A": "Android",
                  "I": "iOS", "N": "Aureon Node"}

# Why a category's unpicked projects were left out.
SKIP_REASON = {
    "official": "Pi-board specific (kernel/firmware/camera for Broadcom SoC)",
    "pico": "Superseded by the chosen Key toolchain",
    "hardware": "Pi GPIO/HAT library - only relevant to Node add-ons",
    "os": "Pi-only distro or duplicate of a chosen base",
    "gaming": "Entertainment; not core (installable via app layer)",
    "media": "Media/camera service; optional Node app",
    "network": "Duplicate of a chosen net component or crypto-node",
    "selfhost": "Duplicate of a chosen cloud component",
    "containers": "Duplicate of chosen ops tooling",
    "iot": "Home-automation detail; covered by home-assistant",
    "ai": "Robotics/drone-specific or superseded runtime",
    "print": "3D printing/CNC - out of scope",
    "radio": "Hobby radio (ADS-B, ham, satellites) - out of scope",
    "astro": "Astronomy - out of scope",
    "security": "Offensive-only, deprecated, or duplicated; not suitable for a protection product",
    "education": "Learning tool; not core",
    "desktop": "Duplicate UI/toolkit or Pi-specific",
}


def parse_catalog(rpi: Path):
    rows, cat = [], None
    for line in (rpi / "README.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r'<a id="([^"]+)"></a>', line)
        if m:
            cat = m.group(1)
            continue
        m = re.match(r"\| (.+?) \| \[([^\]]+)\]\((https://github\.com/[^)]+)\) \| `([^`]+)` \|", line)
        if m and cat:
            rows.append({"name": m.group(1), "repo": m.group(2), "url": m.group(3),
                         "rpi_path": m.group(4), "category": cat})
    return rows


def gitlinks(rpi: Path):
    out = subprocess.run(["git", "-C", str(rpi), "ls-tree", "-r", "HEAD", "software"],
                         capture_output=True, text=True, check=True).stdout
    links = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode, typ, sha = meta.split()
        if typ == "commit":
            links[path] = sha
    return links


def load_caps():
    from capmap_a import CAPS_A
    from capmap_b import CAPS_B
    from capmap_c import CAPS_C
    from capmap_d import CAPS_D
    caps = []
    for cid, domain, name, fused, realised, members in CAPS_A + CAPS_B + CAPS_C + CAPS_D:
        mem = []
        for line in members.strip().splitlines():
            repo, best = line.split(":", 1)
            mem.append({"repo": repo.strip(), "best": best.strip()})
        caps.append({"id": cid, "domain": domain, "name": name, "fused": fused, "realised": realised,
                     "members": mem})
    return caps


def build_capabilities(rows, by_repo):
    """Every catalog project must contribute its best capability to exactly one Aureon capability."""
    caps = load_caps()
    owner = {}
    for c in caps:
        for m in c["members"]:
            if m["repo"] in owner:
                sys.exit(f"{m['repo']} mapped twice: {owner[m['repo']]} and {c['id']}")
            if m["repo"] not in by_repo:
                sys.exit(f"{m['repo']} in capability map but not in catalog")
            owner[m["repo"]] = c["id"]
            m["url"] = by_repo[m["repo"]]["url"]
            m["picked"] = m["repo"] in PICKS
    missing = sorted(set(by_repo) - set(owner))
    if missing:
        sys.exit(f"catalog projects without a capability: {missing}")
    (ROOT / "capabilities.json").write_text(json.dumps(caps, indent=1) + "\n", encoding="utf-8")

    domains = []
    for c in caps:
        if c["domain"] not in domains:
            domains.append(c["domain"])
    lines = ["# Aureon capability map",
             "",
             f"Each of the {len(owner)} projects in shep95/rasberry-pi was read for its single best capability. "
             f"Those capabilities are fused into **{len(caps)} Aureon capabilities** across {len(domains)} domains. "
             "This is the one system: `python -m aureon caps` browses it, `python -m aureon caps show <id>` "
             "explains one, and the *Realised in* line says where it lives in this repo.",
             "",
             "Status words in *Realised in*: **built** = Aureon code in this repo, deploy/* = ready compose stack, "
             "profile = in a device plan, catalog = pinned or listed and fetchable, not yet wired in.",
             "",
             "| Domain | Capabilities | Projects |", "|---|---|---|"]
    for d in domains:
        cs = [c for c in caps if c["domain"] == d]
        lines.append(f"| {d} | {', '.join(c['name'] for c in cs)} | {sum(len(c['members']) for c in cs)} |")
    for d in domains:
        lines += ["", f"## {d}"]
        for c in caps:
            if c["domain"] != d:
                continue
            lines += ["", f"### {c['name']} (`{c['id']}`)", "", f"**Fused capability:** {c['fused']}", "",
                      f"**Realised in:** {c['realised']}", "",
                      "| Project | Best capability taken | Pinned |", "|---|---|---|"]
            for m in c["members"]:
                lines.append(f"| [{m['repo']}]({m['url']}) | {m['best']} | {'yes' if m['picked'] else ''} |")
    (ROOT / "docs" / "CAPABILITIES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(caps)} capabilities cover all {len(owner)} projects")


def main():
    rpi = Path(sys.argv[1]).resolve()
    pin = "--pin" in sys.argv
    rows = parse_catalog(rpi)
    links = gitlinks(rpi)
    by_repo = {}
    for r in rows:
        by_repo.setdefault(r["repo"], r)
    missing = [p for p in PICKS if p not in by_repo]
    if missing:
        sys.exit(f"picks not in catalog: {missing}")

    stack = []
    for repo, (layer, plats, role) in PICKS.items():
        r = by_repo[repo]
        path = f"upstream/{layer}/{repo.replace('/', '__')}"
        stack.append({"repo": repo, "url": r["url"], "layer": layer,
                      "platforms": [c for c in plats if c in PLATFORM_NAMES],
                      "role": role, "path": path, "commit": links.get(r["rpi_path"]),
                      "source_category": r["category"]})
    (ROOT / "stack.json").write_text(json.dumps(stack, indent=1) + "\n", encoding="utf-8")

    # Full catalog with a verdict for every one of the source projects.
    lines = ["# Full catalog review",
             "",
             f"Every project in [shep95/rasberry-pi](https://github.com/shep95/rasberry-pi) "
             f"({len(rows)} entries, {len(by_repo)} unique upstreams) with the verdict for Aureon Hardware.",
             "",
             f"**Picked: {len(PICKS)}.** Picked projects show their Aureon layer; the rest show why they were left out.",
             ""]
    cat = None
    for r in rows:
        if r["category"] != cat:
            cat = r["category"]
            n = sum(1 for x in rows if x["category"] == cat)
            k = sum(1 for x in rows if x["category"] == cat and x["repo"] in PICKS)
            lines += ["", f"## {cat} ({k} of {n} picked)", "", "| Project | Verdict |", "|---|---|"]
        p = PICKS.get(r["repo"])
        verdict = f"**{p[0]}** - {p[2]}" if p else SKIP_REASON[cat]
        lines.append(f"| [{r['repo']}]({r['url']}) | {verdict} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "CATALOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    build_capabilities(rows, by_repo)

    if pin:
        gm = []
        for s in stack:
            gm += [f'[submodule "{s["path"]}"]', f'\tpath = {s["path"]}', f'\turl = {s["url"]}.git',
                   "\tshallow = true"]
            # an empty folder keeps `git add -A` from treating the unfetched submodule as deleted
            (ROOT / s["path"]).mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "-C", str(ROOT), "update-index", "--add", "--cacheinfo",
                            f"160000,{s['commit']},{s['path']}"], check=True)
        (ROOT / ".gitmodules").write_text("\n".join(gm) + "\n", encoding="utf-8")
    print(f"{len(rows)} catalog rows, {len(stack)} picks written; pinned={pin}")


if __name__ == "__main__":
    main()
