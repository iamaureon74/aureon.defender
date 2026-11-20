"""Aureon portable preview. Local posture/USB observations, not Windows feature parity."""
import argparse
import hashlib
import json
import platform
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from aureon.audit import run_audit
from aureon.security_node import usb_inventory

HERE = Path(__file__).resolve().parent


def snapshot():
    try:
        import psutil
        battery=psutil.sensors_battery()
        vitals=dict(cpu=psutil.cpu_percent(),memory=psutil.virtual_memory().percent,
                    battery=battery.percent if battery else None)
    except (ImportError, OSError, AttributeError):
        vitals={}
    specs=dict(cpu_model=platform.processor() or None,logical_processors=__import__('os').cpu_count(),gpu_status='No universal GPU API configured; unavailable, not inferred')
    try:
        memory=psutil.virtual_memory();storage=psutil.disk_usage(str(Path.home()));specs.update(ram_total_bytes=memory.total,ram_available_bytes=memory.available,home_volume_total_bytes=storage.total,home_volume_free_bytes=storage.free)
        fn=getattr(psutil,'sensors_temperatures',None);specs['temperature_c']={group:[{'label':v.label,'value':v.current} for v in values] for group,values in (fn() if fn else {}).items()}
    except (NameError,AttributeError,OSError):pass
    return dict(specs=specs,platform=platform.system(),architecture=platform.machine(),version='0.4.9-preview',
                observed_at=time.time(),vitals=vitals,
                usb=usb_inventory() if platform.system()=='Linux' else None,
                scope='While open: every download and desktop file is scanned, anything found is removed on its own unless the hardware needs it, new downloads get clean copies, old trash is emptied. Read-only posture checks and local USB descriptors on Linux. No process blocking, VPN or Windows Defender.')


def handler(token,state,lock,port,auto=None):
    class H(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,value,kind='application/json'):
            data=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Frame-Options','DENY');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def authorized(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port[0]}',f'localhost:{port[0]}') and secrets.compare_digest(self.headers.get('X-Aureon-Token',''),token)
        def do_GET(self):
            u=urlparse(self.path)
            if self.headers.get('Host') not in (f'127.0.0.1:{port[0]}',f'localhost:{port[0]}'):
                return self.send(403,{'error':'Invalid host'})
            if u.path=='/' and secrets.compare_digest(parse_qs(u.query).get('t',[''])[0],token):
                return self.send(200,(HERE/'dashboard.html').read_bytes().replace(b'__TOKEN__',token.encode()),'text/html; charset=utf-8')
            if not self.authorized():return self.send(403,{'error':'Invalid token'})
            if u.path=='/api/state':
                with lock:value={**state}
                if auto is not None:value['activity']=list(auto.log[:50]);value['automation']={'clean_downloads':auto.clean,'trash_days':auto.trash_days,'downloads':str(auto.downloads),**auto.status()}
                return self.send(200,value)
            if u.path=='/api/drain':
                if auto is None:return self.send(404,{'error':'Not running'})
                return self.send(200,auto.report())
            return self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.authorized():return self.send(403,{'error':'Invalid token'})
            if self.path!='/api/audit':return self.send(404,{'error':'Not supported'})
            try:n=int(self.headers.get('Content-Length','0'))
            except ValueError:return self.send(400,{'error':'Invalid length'})
            if n<0 or n>1024 or self.headers.get('Transfer-Encoding'):return self.send(400,{'error':'Unsupported body'})
            self.connection.settimeout(5)
            try:self.rfile.read(n)
            except OSError:return self.send(408,{'error':'Timed out'})
            with lock:
                if state.get('busy'):return self.send(409,{'error':'Audit already running'})
                state['busy']=True
            def work():
                try:
                    report=run_audit()
                    with lock:state['posture']=report;state['device']=snapshot();state.pop('error',None)
                except Exception as e:
                    with lock:state['error']=type(e).__name__+': '+str(e)
                finally:
                    with lock:state['busy']=False
            threading.Thread(target=work,daemon=True).start()
            return self.send(202,{'message':'Read-only audit started'})
    return H


def memory_cli(argv):
    """python -m portable.app memory status|now|versions|restore|dupes [path] [--version N] [--out FILE]"""
    import portable.automation  # noqa: F401  (sets the data folders, puts the shared engine on the path)
    from aureon_defender.memory import Keeper,fm
    p=argparse.ArgumentParser(prog='memory');p.add_argument('action',choices=['status','now','versions','restore','dupes']);p.add_argument('path',nargs='?')
    p.add_argument('--version',type=int,default=1);p.add_argument('--out');a=p.parse_args(argv)
    k=Keeper()
    if a.action=='status':print(json.dumps(k.status(),indent=1));return 0
    if a.action=='now':print(json.dumps(k.run_once(),indent=1));return 0
    if a.action=='dupes':print(json.dumps(k.dupes(),indent=1));return 0
    if not a.path:print('give the path of the file');return 2
    with fm.FoldMemory(k.store) as m:
        if a.action=='versions':print(json.dumps(m.versions(a.path),indent=1));return 0
        r=m.unfold(a.path,dest=a.out or a.path+'.restored',version=a.version);print(json.dumps(r,indent=1));return 0 if r.get('ok') else 1


def main():
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='memory':return memory_cli(sys.argv[2:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--no-auto-clean',action='store_true',help='do not make clean copies of new downloads')
    parser.add_argument('--no-protect',action='store_true',help='do not scan and remove threats from downloads and desktop')
    parser.add_argument('--trash-days',type=int,default=30,help='empty trash items older than this many days (0 = never)')
    args=parser.parse_args()
    if args.self_test:
        value=snapshot()
        assert value['platform'] and (HERE/'dashboard.html').is_file()
        from portable.automation import Automation
        assert Automation(clean=False,trash_days=0).report()['method']
        if __import__('sys').stdout is not None:print(json.dumps({'self_test':'passed','platform':value['platform'],'architecture':value['architecture']}))
        return 0
    state={'device':snapshot(),'posture':None,'busy':False};lock=threading.Lock();port=[0];token=secrets.token_urlsafe(32)
    from portable.automation import Automation
    auto=Automation(clean=not args.no_auto_clean,trash_days=max(0,args.trash_days),protect=not args.no_protect)
    threading.Thread(target=auto.run,name='aureon-auto',daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',0),handler(token,state,lock,port,auto));port[0]=server.server_port
    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{port[0]}/?t={token}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:auto.stop.set();server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
