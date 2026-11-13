"""Entry point for the packaged exe.

The exe is a windowed app (no console flashes when it starts at logon). Three ways it gets started:
  * by a browser as noah.shield's companion: argv[1] is chrome-extension://... (Chromium) or a manifest path
    (Firefox) -> binary native-messaging pipes on stdin/stdout
  * from a terminal (`aureon.defender.exe scan <folder>`) -> text to the pipe/file given, else the parent console
  * from the Start menu, the logon task or an aureon:// link -> no console at all
"""
import sys


def _std_handle(n):
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.GetStdHandle.restype = ctypes.c_void_p
    h = k32.GetStdHandle(n)
    if h in (None, 0, ctypes.c_void_p(-1).value) or k32.GetFileType(ctypes.c_void_p(h)) not in (1, 3):   # disk file or pipe
        return None
    return h


def _wire_text_output():
    import ctypes
    import msvcrt
    import os
    h = _std_handle(-11)
    if h:
        stream = os.fdopen(msvcrt.open_osfhandle(h, os.O_WRONLY), "w", encoding="utf-8", buffering=1)
    elif ctypes.windll.kernel32.AttachConsole(-1):
        stream = open("CONOUT$", "w", encoding="utf-8", buffering=1)
    else:
        return
    sys.stdout = sys.stderr = stream


def _native_host():
    import msvcrt
    import os
    from aureon_defender.noah import native_host_loop
    hin, hout = _std_handle(-10), _std_handle(-11)
    if not (hin and hout):
        return 1
    native_host_loop(os.fdopen(msvcrt.open_osfhandle(hin, os.O_RDONLY), "rb", buffering=0),
                     os.fdopen(msvcrt.open_osfhandle(hout, os.O_WRONLY), "wb", buffering=0))
    return 0


def _is_browser_call(argv):
    return len(argv) > 1 and (argv[1].startswith("chrome-extension://") or argv[1].lower().endswith(".json"))


if getattr(sys, "frozen", False) and _is_browser_call(sys.argv):
    sys.exit(_native_host())

if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] not in ("engine", "agent", "run", "open"):
    try:
        _wire_text_output()
    except Exception:
        pass

from aureon_defender.__main__ import main  # noqa: E402

sys.exit(main())
