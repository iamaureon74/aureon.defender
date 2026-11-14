"""Install / uninstall aureon.defender (admin). Only the packaged exe is installed.

Layout
  %ProgramFiles%\\Aureon\\aureon.defender.exe
  %ProgramData%\\Aureon\\           SYSTEM + Administrators full, Users read-only (settings can't be changed by malware running as you)
  %ProgramData%\\Aureon\\inbox      Users may drop harmless requests (scan, refresh)
Tasks
  "Aureon Defender Engine"  at startup, as SYSTEM, restarts every minute if it stops, no time limit, runs on battery
  "Aureon Defender Agent"   at every logon, as the signed-in user (dashboard, toasts, widget)
"""
import ctypes
import os
import shutil
import subprocess
import time
import sys
from pathlib import Path

from .core import VERSION

NOWIN = 0x08000000
TARGET = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Aureon"
DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Aureon"
START_MENU = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs/Aureon Defender.lnk"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AureonDefender"
ENGINE_TASK, AGENT_TASK = "Aureon Defender Engine", "Aureon Defender Agent"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, creationflags=NOWIN)


def psq(s):
    return "'" + str(s).replace("'", "''") + "'"


def task_script(exe):
    e = psq(exe)
    return f"""
$set = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
       -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName {psq(ENGINE_TASK)} -Force -Settings $set `
  -Action (New-ScheduledTaskAction -Execute {e} -Argument 'engine') -Trigger (New-ScheduledTaskTrigger -AtStartup) `
  -Principal (New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -RunLevel Highest) -Description 'Aureon Defender 24/7 protection engine' | Out-Null
Register-ScheduledTask -TaskName {psq(AGENT_TASK)} -Force -Settings $set `
  -Action (New-ScheduledTaskAction -Execute {e} -Argument 'agent') -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
  -Principal (New-ScheduledTaskPrincipal -GroupId 'S-1-5-32-545' -RunLevel Limited) -Description 'Aureon Defender alerts, dashboard and desktop widget' | Out-Null
Start-ScheduledTask -TaskName {psq(ENGINE_TASK)}
$s = (New-Object -ComObject WScript.Shell).CreateShortcut({psq(START_MENU)})
$s.TargetPath = {e}; $s.Arguments = 'open'; $s.IconLocation = {e}; $s.Description = 'Aureon Defender'; $s.Save()
"""


def acl_commands(data=DATA):
    d = str(data)
    return [
        ["icacls", d, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-32-545:(OI)(CI)RX"],
        ["icacls", str(data / "inbox"), "/grant", "*S-1-5-32-545:(OI)(CI)M"],
    ]


def stop_installed_copies(target=None, me=None):
    """Stop only Aureon processes running from the installed folder. Never the installer itself or the window that
    launched it (the old `taskkill /im` killed the waiting installer and the dashboard never started)."""
    import psutil
    target = Path(target or TARGET).resolve()
    me = me or os.getpid()
    keep = {me}
    try:
        keep.add(psutil.Process(me).ppid())
    except Exception:
        pass
    stopped = []
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            exe = Path(p.info["exe"] or "").resolve()
        except OSError:
            continue
        if p.info["pid"] not in keep and target in exe.parents:
            try:
                p.kill()
                stopped.append(p.info["pid"])
            except Exception:
                pass
    return stopped


def install():
    if not getattr(sys, "frozen", False):
        print("Install works from the packaged aureon.defender.exe (windows/build.ps1). In dev, use: python -m aureon_defender run")
        return 2
    if not is_admin():
        # ask for admin for the machine-wide part, then start the dashboard agent as *you* (not elevated)
        from .agent import engine_alive, run_elevated
        _, before = engine_alive()
        old_pid = before.get("pid")
        if not run_elevated(["install"]):
            print("The administrator prompt was declined; nothing was installed.")
            return 1
        print("Approve the administrator prompt to continue...")
        for _ in range(240):                     # wait for the *new* engine, not a heartbeat left by the old one
            time.sleep(1)
            alive, st = engine_alive()
            if alive and st.get("version") == VERSION and st.get("pid") != old_pid:
                break
        else:
            print(f"The new engine didn't report within 4 minutes. Details: {DATA / 'aureon.log'}")
            return 1
        subprocess.Popen([str(TARGET / "aureon.defender.exe"), "agent", "--open"], creationflags=0x00000008)
        print(f"Aureon Defender {VERSION} installed and running.")
        return 0
    from .core import log
    log(f"install {VERSION} started (elevated)")
    TARGET.mkdir(parents=True, exist_ok=True)
    exe = TARGET / "aureon.defender.exe"
    src = Path(sys.executable).resolve().parent            # the unzipped program folder
    if src != TARGET.resolve():
        ps(f"Stop-ScheduledTask -TaskName {psq(ENGINE_TASK)} -ErrorAction SilentlyContinue")
        ps(f"Stop-ScheduledTask -TaskName {psq(AGENT_TASK)} -ErrorAction SilentlyContinue")
        log(f"stopped {stop_installed_copies()}")
        for attempt in range(5):                 # a file can stay locked for a moment after its process dies
            try:
                shutil.copytree(src, TARGET, dirs_exist_ok=True)
                break
            except (OSError, shutil.Error) as ex:
                log(f"copy attempt {attempt + 1} failed: {ex}")
                time.sleep(2)
                stop_installed_copies()
        else:
            raise RuntimeError("could not replace the installed files")
        log("files copied")
    (DATA / "inbox").mkdir(parents=True, exist_ok=True)
    (DATA / "rules").mkdir(exist_ok=True)
    for cmd in acl_commands():
        subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    r = ps(task_script(exe))
    if r.returncode:
        log("task registration failed: " + r.stderr[-1500:])
        print(r.stderr)
        return 1
    log("tasks registered and engine started")
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as k:
        for n, v in (("DisplayName", "Aureon Defender"), ("DisplayVersion", VERSION), ("Publisher", "Aureon Hardware"),
                     ("DisplayIcon", str(exe)), ("UninstallString", f'"{exe}" uninstall'), ("InstallLocation", str(TARGET))):
            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
    # The dashboard agent is started by the non-elevated caller (or the logon task), never from this admin process.
    print(f"Aureon Defender {VERSION} installed to {TARGET}")
    return 0


def uninstall(purge=False):
    if not is_admin():
        from .agent import run_elevated
        return 0 if run_elevated(["uninstall"] + (["--purge"] if purge else [])) else 1
    ps(f"""foreach($t in {psq(ENGINE_TASK)},{psq(AGENT_TASK)}){{ Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue;
          Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue }}""")
    stop_installed_copies()
    try:
        from .feeds import apply_hosts
        apply_hosts([])                       # remove our DNS-shield block, keep the user's own entries
    except OSError:
        pass
    START_MENU.unlink(missing_ok=True)
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
    except OSError:
        pass
    if purge:
        shutil.rmtree(DATA, ignore_errors=True)
    # the running exe can't delete itself: remove the folder a few seconds after we exit
    subprocess.Popen(f'cmd /c timeout /t 3 /nobreak >nul & rmdir /s /q "{TARGET}"', shell=True, creationflags=NOWIN)
    print("Aureon Defender removed" + (" (including quarantine and logs)" if purge else "; quarantine and logs kept in " + str(DATA)))
    return 0
