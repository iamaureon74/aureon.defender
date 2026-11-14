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
import os
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
    op = sub.add_parser("open"); op.add_argument("--url")
    s = sub.add_parser("scan"); s.add_argument("path"); s.add_argument("--json", action="store_true")
    sub.add_parser("status")
    sub.add_parser("update")
    st = sub.add_parser("studio"); st.add_argument("action", choices=["list", "preset", "restore"]); st.add_argument("name", nargs="?")
    q = sub.add_parser("quarantine"); q.add_argument("action", choices=["list", "restore", "delete"]); q.add_argument("id", nargs="?")
    se = sub.add_parser("settings"); se.add_argument("--apply")
    lk = sub.add_parser("leaks"); lk.add_argument("action", choices=["list", "fix"]); lk.add_argument("id", nargs="?")
    dv = sub.add_parser("devices"); dv.add_argument("action", choices=["list", "sweep", "clear"])
    sub.add_parser("native-host")
    ct = sub.add_parser("controls"); ct.add_argument("action", choices=["telemetry-close", "telemetry-open", "usb-block", "usb-allow", "wifi-on", "wifi-off"])
    hd = sub.add_parser("harden"); hd.add_argument("--apply", action="store_true"); hd.add_argument("--undo", action="store_true")
    hw = sub.add_parser("hardware"); hw.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    cmd = args.cmd or "open"

    if cmd == "install":
        from .install import install
        return install()
    if cmd == "uninstall":
        from .install import uninstall
        return uninstall(args.purge)
    if cmd == "engine":
        import traceback
        from .core import log
        log(f"engine starting (user {os.environ.get('USERNAME')})")
        try:
            from .engine import Engine
            eng = Engine()
            log("engine initialised")
            eng.run()
        except Exception:
            log("engine crashed:\n" + traceback.format_exc())
            raise
        return 0
    if cmd == "agent":
        from .agent import run_agent
        run_agent(with_widget=not args.no_widget, open_ui=args.open)
        return 0
    if cmd == "open" and getattr(args, "url", None):
        pass
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
            if r["verdict"] not in ("clean", "skipped"):
                bad += 1
            if args.json:
                print(json.dumps(r))
            elif r["verdict"] not in ("clean", "skipped"):
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
    if cmd == "harden":
        from .harden import apply_machine, plan, score, undo_machine
        from .core import log
        if args.apply:
            changed = apply_machine()
            log(f"protect-this-PC applied: {changed}")
            print("changed:", ", ".join(changed) or "nothing")
            return 0
        if args.undo:
            print(f"restored {undo_machine()} settings")
            return 0
        items = plan()
        for i in items:
            print(f"{'ok  ' if i['done'] else 'TODO'} {i['group']:<9} {i['title']}")
        print(f"{score(items)}% protected")
        return 0
    if cmd == "hardware":
        from .hardware import write_report
        from .devices import timeline, history, live_log
        out, data = write_report(timeline(history(fallback=False), live_log()))
        print(out)
        if args.report:
            os.startfile(str(out))
        return 0
    if cmd == "controls":
        from . import controls as c
        from .core import log
        a = args.action
        res = {"telemetry-close": c.close_telemetry, "telemetry-open": c.reopen_telemetry,
               "usb-block": lambda: c.set_usb_storage(True), "usb-allow": lambda: c.set_usb_storage(False),
               "wifi-on": lambda: c.set_wifi_allowlist(True), "wifi-off": lambda: c.set_wifi_allowlist(False)}[a]()
        log(f"controls {a}: {res}")
        print(res)
        return 0
    if cmd == "native-host":
        from .noah import native_host_loop
        native_host_loop()
        return 0
    if cmd == "leaks":
        from .leaks import audit, fix, fix_machine, MACHINE_SAFE
        if args.action == "list":
            for r in audit():
                print(f"{'ok  ' if r['ok'] else 'LEAK'} {r['title']:<42} {'' if r['ok'] else r['fix']}")
            return 0
        (fix_machine if args.id in MACHINE_SAFE else fix)(args.id)
        print(f"fixed {args.id}")
        return 0
    if cmd == "devices":
        from .core import data_dir
        from .devices import sweep
        if args.action == "clear":
            for f in ("devices.jsonl", "devices.json"):
                (data_dir() / f).unlink(missing_ok=True)
            print("Aureon's device log cleared (Windows' own records were not touched)")
            return 0
        snap = sweep()
        if args.action == "list":
            for e in snap["timeline"][:60]:
                print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(e['t']))}  {e['kind']:<16} {e['category']:<22} {e['name']}"
                      + ("   <- tracking tag" if e.get("tracker") else ""))
        print(f"{len(snap['devices'])} devices known, {len(snap['present'])} connected now")
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
