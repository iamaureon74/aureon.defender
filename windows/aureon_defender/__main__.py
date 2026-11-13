"""aureon.defender command line.

  aureon.defender                  open the dashboard (starts a portable session if not installed)
  aureon.defender install          install for all users (asks for admin)  | uninstall [--purge]
  aureon.defender run              portable: engine + dashboard + widget in this session, no install
  aureon.defender engine           24/7 engine (what the SYSTEM task runs)
  aureon.defender agent [--open] [--no-widget]
  aureon.defender scan PATH        scan a file or folder now and print verdicts
  aureon.defender status           one-screen status
  aureon.defender update           refresh threat feeds now
  aureon.defender studio list | preset NAME | restore
  aureon.defender quarantine list | restore ID | delete ID
  aureon.defender settings --apply FILE     (used by the dashboard through the admin prompt)
"""
import argparse
import json
import sys
import threading
import time
from pathlib import Path


def _status():
    from .agent import engine_alive
    alive, st = engine_alive()
    if not st:
        print("Engine has never run on this PC.")
        return 1
    c = st.get("counts", {})
    print(f"Aureon Defender {st.get('version')}  engine {'RUNNING' if alive else 'STOPPED'}  ({'online' if st.get('online') else 'offline mode'})")
    print(f"  scanned {c.get('scanned', 0)}  quarantined {c.get('quarantined', 0)}  alerts {c.get('alerts', 0)}  known-bad hashes {st.get('reputation', 0)}")
    for m, s in sorted(st.get("modules", {}).items()):
        print(f"  {m:<12} {s}")
    return 0 if alive else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aureon.defender")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("install")
    u = sub.add_parser("uninstall"); u.add_argument("--purge", action="store_true")
    sub.add_parser("run")
    sub.add_parser("engine")
    a = sub.add_parser("agent"); a.add_argument("--open", action="store_true"); a.add_argument("--no-widget", action="store_true")
    sub.add_parser("open")
    s = sub.add_parser("scan"); s.add_argument("path"); s.add_argument("--json", action="store_true")
    sub.add_parser("status")
    sub.add_parser("update")
    st = sub.add_parser("studio"); st.add_argument("action", choices=["list", "preset", "restore"]); st.add_argument("name", nargs="?")
    q = sub.add_parser("quarantine"); q.add_argument("action", choices=["list", "restore", "delete"]); q.add_argument("id", nargs="?")
    se = sub.add_parser("settings"); se.add_argument("--apply")
    args = ap.parse_args(argv)
    cmd = args.cmd or "open"

    if cmd == "install":
        from .install import install
        return install()
    if cmd == "uninstall":
        from .install import uninstall
        return uninstall(args.purge)
    if cmd == "engine":
        from .engine import Engine
        Engine().run()
        return 0
    if cmd == "agent":
        from .agent import run_agent
        run_agent(with_widget=not args.no_widget, open_ui=args.open)
        return 0
    if cmd in ("run", "open"):
        from .agent import engine_alive, open_dashboard, run_agent
        from .core import user_dir
        info_p = user_dir() / "agent.json"
        if cmd == "open" and info_p.exists():
            try:
                import urllib.request
                info = json.loads(info_p.read_text())
                urllib.request.urlopen(f"http://127.0.0.1:{info['port']}/api/state", timeout=1)
            except Exception as e:
                if getattr(e, "code", None) == 403:      # agent is alive (it rejected the token-less call)
                    open_dashboard()
                    return 0
        if not engine_alive()[0]:
            from .engine import Engine
            eng = Engine()
            threading.Thread(target=eng.run, daemon=True).start()
        run_agent(with_widget=True, open_ui=True)
        return 0
    if cmd == "scan":
        from .engine import Engine
        from .scanner import Scanner
        from .core import Settings
        sc = Scanner(Settings().load())
        p = Path(args.path).expanduser()
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        bad = 0
        for f in files:
            r = sc.scan(f)
            if args.json:
                print(json.dumps(r))
            elif r["verdict"] not in ("clean", "skipped"):
                bad += 1
                print(f"{r['verdict'].upper():<10} {f}\n           {'; '.join(r['reasons'])}")
        if not args.json:
            print(f"{len(files)} files scanned, {bad} findings")
        return 3 if bad else 0
    if cmd == "status":
        return _status()
    if cmd == "update":
        from .feeds import Feeds, online
        from .scanner import Reputation
        if not online():
            print("Offline: keeping the cached feeds.")
            return 1
        print(Feeds().update(Reputation()))
        return 0
    if cmd == "studio":
        from .studio import PRESETS, Studio
        s = Studio()
        if args.action == "list":
            for n, p in PRESETS.items():
                print(f"{n:<10} {p['mode']:<6} accent {p['accent']}  widget font {p['widget']['font']}")
        elif args.action == "preset":
            print(json.dumps(s.apply_preset(args.name), indent=1))
        else:
            print(f"restored {s.restore()} settings")
        return 0
    if cmd == "quarantine":
        from .quarantine import Vault
        v = Vault()
        if args.action == "list":
            for m in v.list():
                print(f"{m['id']}  {time.strftime('%Y-%m-%d %H:%M', time.localtime(m['t']))}  {m['original']}")
        elif args.action == "restore":
            print("restored to", v.restore(args.id))
        else:
            v.delete(args.id)
        return 0
    if cmd == "settings" and args.apply:
        from .core import Settings
        Settings().save(json.loads(Path(args.apply).read_text(encoding="utf-8")))
        Path(args.apply).unlink(missing_ok=True)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
