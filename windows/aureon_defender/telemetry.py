"""Reported battery precision and observed throughput. No fabricated battery decimals or WAN test."""
import threading
import time

_lock=threading.Lock()
_last=None

def collect():
    import psutil
    global _last
    battery=psutil.sensors_battery()
    now=time.monotonic();io=psutil.net_io_counters();interfaces=psutil.net_if_stats()
    network={'download_mbps':None,'upload_mbps':None,'interval_seconds':None,'source':'psutil OS network byte counters','scope':'Aggregate interface traffic; VPN/virtual adapters may double-count. Not internet connection capacity or a speed-test result.','links':[{'name':k,'up':v.isup,'reported_link_mbps':v.speed or None} for k,v in interfaces.items()]}
    with _lock:
        if _last:
            t,sent,received=_last;dt=now-t
            if dt>=.25:
                network.update(download_mbps=max(0,io.bytes_recv-received)*8/dt/1000000,upload_mbps=max(0,io.bytes_sent-sent)*8/dt/1000000,interval_seconds=dt)
        if _last is None or now-_last[0]>=.25:_last=(now,io.bytes_sent,io.bytes_recv)
    return {'sampled_at':time.time(),'battery':None if battery is None else {'percent':battery.percent,'charging':battery.power_plugged,'seconds_left':battery.secsleft if battery.secsleft>=0 else None,'source':'psutil / Windows power status' if __import__('os').name=='nt' else 'psutil / OS battery status','precision':'OS-reported value; Windows usually reports whole percentage points. 98% does not imply 98.74%.','meaning':'Estimated charge remaining, not battery health or exact energy.'},'network':network}
