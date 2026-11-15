"""Best-effort reported temperatures/fans and NVIDIA driver telemetry. Never guessed sensors."""
import csv
import io
import os
import shutil
import subprocess

def collect():
    import psutil
    result={'temperature_c':[],'fans_rpm':[],'gpus':[],'source':'Available OS/driver APIs only','limits':['No sensor reading means unavailable, not a temperature of zero.','ACPI thermal-zone readings need not be CPU/GPU die temperatures.','GPU driver telemetry depends on vendor/API availability.']}
    for method,key in [('sensors_temperatures','temperature_c'),('sensors_fans','fans_rpm')]:
        fn=getattr(psutil,method,None)
        if fn:
            try:
                for group,items in fn().items():
                    for item in items:result[key].append({'group':group,'label':item.label or group,'value':item.current})
            except (OSError,AttributeError,RuntimeError):pass
    exe=shutil.which('nvidia-smi')
    if exe:
        try:
            p=subprocess.run([exe,'--query-gpu=name,temperature.gpu,utilization.gpu,memory.total,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,creationflags=0x08000000 if os.name=='nt' else 0)
            if p.returncode==0:
                for row in csv.reader(io.StringIO(p.stdout)):
                    if len(row)!=5:continue
                    def number(v):
                        try:return float(v.strip())
                        except ValueError:return None
                    result['gpus'].append({'name':row[0].strip(),'temperature_c':number(row[1]),'utilization_percent':number(row[2]),'memory_total_mib':number(row[3]),'memory_used_mib':number(row[4]),'source':'nvidia-smi / driver-reported'})
        except (OSError,subprocess.TimeoutExpired):pass
    return result
