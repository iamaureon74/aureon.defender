"""Host agent for the Aureon Key (key/firmware/main.py).

  pip install pyserial
  python -m aureon.keyagent --port COM5        (Windows)
  python -m aureon.keyagent --port /dev/ttyACM0 (Linux)

Locks the screen on "LOCK ..." messages, and on walk-away when heartbeats stop
for --timeout seconds after having been seen (Key unplugged / cable yanked).
"""
import argparse
import platform
import subprocess
import time


def lock_screen():
    s = platform.system()
    if s == "Windows":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
    elif s == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"])
    else:
        for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"]):
            if subprocess.run(cmd).returncode == 0:
                break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--timeout", type=float, default=4.0, help="seconds without heartbeat before locking")
    ap.add_argument("--dry-run", action="store_true", help="log instead of locking")
    a = ap.parse_args()
    try:
        import serial
    except ImportError:
        raise SystemExit("pip install pyserial")

    act = (lambda why: print(f"[dry-run] would lock: {why}")) if a.dry_run else (lambda why: (print(f"lock: {why}"), lock_screen()))
    armed, last = False, time.monotonic()
    while True:
        try:
            with serial.Serial(a.port, 115200, timeout=0.5) as ser:
                print(f"connected to Aureon Key on {a.port}")
                while True:
                    line = ser.readline().decode(errors="ignore").strip()
                    now = time.monotonic()
                    if line.startswith("HB"):
                        armed, last = True, now
                    elif line.startswith("LOCK"):
                        act(line[5:] or "key")
                    if armed and now - last > a.timeout:
                        act("heartbeat lost")
                        armed = False
        except (OSError, serial.SerialException):
            if armed and time.monotonic() - last > a.timeout:
                act("key removed")
                armed = False
            time.sleep(1)


if __name__ == "__main__":
    main()
