"""aureon - one CLI over the curated stack.

  python -m aureon audit [--json]                 read-only posture check of this machine
  python -m aureon profiles                       list device profiles
  python -m aureon plan <profile>                 ordered install/hardening plan
  python -m aureon components [--layer L] [--platform P]
  python -m aureon fetch <layer|repo> ...         shallow-clone pinned upstream source
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from .audit import run_audit
from .profiles import PROFILES

ROOT = Path(__file__).resolve().parent.parent
PLAT = {"L": "linux", "W": "windows", "M": "macos", "A": "android", "I": "ios", "N": "node"}
COLOR = {"PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m", "INFO": "\033[36m", "SKIP": "\033[90m"}


def load_stack():
    return json.loads((ROOT / "stack.json").read_text(encoding="utf-8"))


def cmd_audit(a):
    rep = run_audit()
    if a.json:
        print(json.dumps(rep, indent=2))
        return 0
    tty = sys.stdout.isatty()
    print(f"Aureon audit - {rep['system']} {rep['release']} ({rep['machine']}) admin={rep['admin']}")
    for r in rep["results"]:
        tag = f"{COLOR[r['status']]}{r['status']:4}\033[0m" if tty else f"{r['status']:4}"
        print(f"  [{tag}] {r['check']:<17} {r['detail']}")
    print(f"Score: {rep['score']}/100" if rep["score"] is not None else "Score: n/a")
    if not rep["admin"]:
        print("Tip: run elevated for encryption/secure-boot checks.")
    return 0


def cmd_profiles(a):
    for k, p in PROFILES.items():
        print(f"{k:<15} {p['summary']}")
    return 0


def cmd_plan(a):
    p = PROFILES.get(a.profile)
    if not p:
        print(f"unknown profile; choose from {', '.join(PROFILES)}")
        return 2
    by = {s["repo"]: s for s in load_stack()}
    print(f"# {a.profile}: {p['summary']}\n")
    for i, (title, layer, comps, how) in enumerate(p["steps"], 1):
        print(f"{i:>2}. [{layer}] {title}")
        for c in comps:
            print(f"      - {c}: {by[c]['role'] if c in by else ''}")
        print(f"      $ {how}")
    return 0


def cmd_components(a):
    rows = load_stack()
    if a.layer:
        rows = [r for r in rows if r["layer"] == a.layer]
    if a.platform:
        code = {v: k for k, v in PLAT.items()}.get(a.platform, a.platform.upper())
        rows = [r for r in rows if code in r["platforms"]]
    for r in rows:
        plats = ",".join(PLAT[c] for c in r["platforms"]) or "firmware"
        print(f"{r['layer']:<7} {r['repo']:<42} [{plats}] {r['role']}")
    print(f"\n{len(rows)} components")
    return 0


def cmd_fetch(a):
    rows = load_stack()
    paths = [r["path"] for r in rows if r["layer"] in a.targets or r["repo"] in a.targets]
    if not paths:
        print("nothing matched")
        return 2
    return subprocess.call(["git", "-C", str(ROOT), "submodule", "update", "--init", "--depth", "1",
                            "--jobs", "8", "--", *paths])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aureon", description="Aureon Hardware control CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("audit"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_audit)
    sub.add_parser("profiles").set_defaults(f=cmd_profiles)
    s = sub.add_parser("plan"); s.add_argument("profile"); s.set_defaults(f=cmd_plan)
    s = sub.add_parser("components"); s.add_argument("--layer"); s.add_argument("--platform")
    s.set_defaults(f=cmd_components)
    s = sub.add_parser("fetch"); s.add_argument("targets", nargs="+"); s.set_defaults(f=cmd_fetch)
    a = ap.parse_args(argv)
    return a.f(a)
