"""Entry point for the packaged exe.

The exe is a windowed app (no console flashes when it starts at logon). For command-line use such as
`aureon.defender.exe scan C:\\x`, output goes to whatever the caller gave us: a pipe/file if redirected,
otherwise the terminal window it was started from.
"""
import sys


def _wire_output():
    import ctypes
    import msvcrt
    import os
    k32 = ctypes.windll.kernel32
    k32.GetStdHandle.restype = ctypes.c_void_p
    h = k32.GetStdHandle(-11)                                  # STD_OUTPUT_HANDLE
    if h not in (None, 0, ctypes.c_void_p(-1).value) and k32.GetFileType(ctypes.c_void_p(h)) in (1, 3):   # disk file or pipe
        stream = os.fdopen(msvcrt.open_osfhandle(h, os.O_WRONLY), "w", encoding="utf-8", buffering=1)
    elif k32.AttachConsole(-1):                                # ATTACH_PARENT_PROCESS
        stream = open("CONOUT$", "w", encoding="utf-8", buffering=1)
    else:
        return
    sys.stdout = sys.stderr = stream


if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] not in ("engine", "agent", "run", "open"):
    try:
        _wire_output()
    except Exception:
        pass

from aureon_defender.__main__ import main  # noqa: E402

sys.exit(main())
