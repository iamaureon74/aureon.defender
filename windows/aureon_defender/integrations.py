"""Optional local command-line engines. No downloads, automatic installs or shell commands."""
import os
import shutil
import subprocess

TOOLS={'clamav':('clamscan','https://docs.clamav.net/manual/Usage/Scanning.html'),
       'osquery':('osqueryi','https://osquery.io/'),
       'exiftool':('exiftool','https://exiftool.org/'),
       'suricata':('suricata','https://docs.suricata.io/'),
       'zeek':('zeek','https://zeek.org/'),
       'crowdsec':('cscli','https://docs.crowdsec.net/'),
       'usbguard':('usbguard','https://usbguard.github.io/')}

def availability():
    return {k:{'installed':bool(shutil.which(v[0])),'integration':'optional file scanner' if k=='clamav' else 'discovery only; no engine execution configured','documentation':v[1]} for k,v in TOOLS.items()}

def clamav_scan(path):
    exe=shutil.which('clamscan')
    if not exe:return 'unavailable','ClamAV is not installed or not on PATH'
    try:
        p=subprocess.run([exe,'--no-summary','--infected',str(path)],capture_output=True,text=True,timeout=120,creationflags=0x08000000 if os.name=='nt' else 0)
        detail=(p.stdout+'\n'+p.stderr).strip()[-4000:]
        if p.returncode==0:return 'no_match','No ClamAV match; not proof of safety'
        if p.returncode==1:return 'threat',detail
        return 'unavailable',detail or 'ClamAV scan error'
    except (OSError,subprocess.TimeoutExpired) as ex:return 'unavailable',str(ex)
