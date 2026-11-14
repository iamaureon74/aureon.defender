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
    return dict(platform=platform.system(),architecture=platform.machine(),version='0.4.1-preview',
                observed_at=time.time(),vitals=vitals,
                usb=usb_inventory() if platform.system()=='Linux' else None,
                scope='Read-only posture, local USB descriptors on Linux, and browser-local file hashes. No quarantine, process blocking, VPN, or Windows Defender.')


def handler(token,state,lock,port):
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
                return self.send(200,value)
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        value=snapshot()
        assert value['platform'] and (HERE/'dashboard.html').is_file()
        if __import__('sys').stdout is not None:print(json.dumps({'self_test':'passed','platform':value['platform'],'architecture':value['architecture']}))
        return 0
    state={'device':snapshot(),'posture':None,'busy':False};lock=threading.Lock();port=[0];token=secrets.token_urlsafe(32)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler(token,state,lock,port));port[0]=server.server_port
    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{port[0]}/?t={token}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
