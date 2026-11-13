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


def install():
    if not getattr(sys, "frozen", False):
        print("Install works from the packaged aureon.defender.exe (windows/build.ps1). In dev, use: python -m aureon_defender run")
        return 2
    if not is_admin():
        from .agent import run_elevated
        return 0 if run_elevated(["install"]) else 1
    TARGET.mkdir(parents=True, exist_ok=True)
    exe = TARGET / "aureon.defender.exe"
    src = Path(sys.executable).resolve().parent            # the unzipped program folder
    if src != TARGET.resolve():
        ps(f"Stop-ScheduledTask -TaskName {psq(ENGINE_TASK)} -ErrorAction SilentlyContinue")
        subprocess.run(["taskkill", "/f", "/im", "aureon.defender.exe", "/fi", f"PID ne {os.getpid()}"], capture_output=True, creationflags=NOWIN)
        shutil.copytree(src, TARGET, dirs_exist_ok=True)
    (DATA / "inbox").mkdir(parents=True, exist_ok=True)
    (DATA / "rules").mkdir(exist_ok=True)
    for cmd in acl_commands():
        subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    r = ps(task_script(exe))
    if r.returncode:
        print(r.stderr)
        return 1
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as k:
        for n, v in (("DisplayName", "Aureon Defender"), ("DisplayVersion", VERSION), ("Publisher", "Aureon Hardware"),
                     ("DisplayIcon", str(exe)), ("UninstallString", f'"{exe}" uninstall'), ("InstallLocation", str(TARGET))):
            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
    subprocess.Popen([str(exe), "agent", "--open"], creationflags=0x00000008)   # DETACHED_PROCESS: start now for this user
    print(f"Aureon Defender {VERSION} installed to {TARGET}")
    return 0


def uninstall(purge=False):
    if not is_admin():
        from .agent import run_elevated
        return 0 if run_elevated(["uninstall"] + (["--purge"] if purge else [])) else 1
    ps(f"""foreach($t in {psq(ENGINE_TASK)},{psq(AGENT_TASK)}){{ Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue;
          Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue }}""")
    subprocess.run(["taskkill", "/f", "/im", "aureon.defender.exe", "/fi", f"PID ne {os.getpid()}"], capture_output=True, creationflags=NOWIN)
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
