"""Explicit, read-only full scan with bounded findings and reviewed quarantine actions."""
import copy
import os
import threading
import time
import uuid
from pathlib import Path


def local_roots():
    if os.name != 'nt':
        return [Path.home()]
    import ctypes
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(chr(65+i)+':\\') for i in range(26) if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(chr(65+i)+':\\') == 3]


class ScanJobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.state = {'status':'idle', 'scanned':0, 'skipped':0, 'errors':0, 'findings':[], 'finding_count':0}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def start(self, scanner, roots=None, exclusions=(), limit=200000):
        with self.lock:
            if self.state['status'] in ('running','cancelling'):
                raise ValueError('A full scan is already running')
            roots = list(local_roots() if roots is None else roots)
            self.cancel.clear()
            self.state = {'id':uuid.uuid4().hex, 'status':'running','started':time.time(),'scanned':0,'skipped':0,'errors':0,'findings':[],'finding_count':0,'roots':[str(p) for p in roots],'current':'','limit':limit,'scope':'Accessible files on local fixed drives; no network drives, links or junctions. Read-only; no automatic cleanup.'}
            threading.Thread(target=self._run,args=(scanner,roots,exclusions,limit),daemon=True).start()
            return self.snapshot()

    def stop(self):
        with self.lock:
            if self.state['status']=='running':
                self.cancel.set();self.state['status']='cancelling'
        return self.snapshot()

    def _run(self, scanner, roots, exclusions, limit):
        excluded=[Path(p).resolve() for p in exclusions]
        count=0
        def blocked(p):
            try:
                return p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) or any(p.resolve().is_relative_to(x) for x in excluded)
            except OSError:
                return True
        def error(_):
            with self.lock:self.state['errors']+=1
        try:
            for root in roots:
                for folder, dirs, files in os.walk(root, followlinks=False, onerror=error):
                    if self.cancel.is_set() or count>=limit:break
                    dirs[:]=[d for d in dirs if not blocked(Path(folder)/d)]
                    for name in files:
                        if self.cancel.is_set() or count>=limit:break
                        p=Path(folder)/name
                        if blocked(p):
                            with self.lock:self.state['skipped']+=1
                            continue
                        with self.lock:self.state['current']=str(p)
                        try:
                            # Scanner has no remediation; unlike Engine.on_file this never auto-cleans/quarantines.
                            result=scanner.scan(p)
                        except Exception as ex:
                            result={'verdict':'error','reasons':[str(ex)]}
                        count+=1
                        with self.lock:
                            self.state['scanned']=count
                            verdict=result.get('verdict')
                            if verdict in ('error','skipped'):
                                self.state['errors' if verdict=='error' else 'skipped']+=1
                            if verdict in ('malicious','suspicious'):
                                self.state['finding_count']+=1
                                if len(self.state['findings'])<1000:
                                    self.state['findings'].append({**result,'id':uuid.uuid4().hex,'recommendation':'Review evidence, then quarantine if unwanted. Heuristic matches may be false positives. Never delete system files blindly.','action':'pending'})
            with self.lock:
                self.state.update(status='cancelled' if self.cancel.is_set() else 'limited' if count>=limit else 'completed',finished=time.time(),current='')
        except Exception as ex:
            with self.lock:self.state.update(status='failed',error=str(ex),finished=time.time())

    def quarantine(self, ids, vault):
        from .scanner import sha256
        if not isinstance(ids,list) or not ids or len(ids)>100:
            raise ValueError('Choose 1 to 100 findings for quarantine')
        results=[]
        with self.lock:
            for fid in dict.fromkeys(ids):
                item=next((x for x in self.state['findings'] if x['id']==fid),None)
                if not item or item['action']!='pending':
                    results.append({'id':fid,'error':'Finding unavailable or already handled'});continue
                try:
                    p=Path(item['path'])
                    if not item.get('sha256') or sha256(p)!=item['sha256']:
                        raise ValueError('File changed since scanning; scan it again')
                    entry=vault.put(p,item);item['action']='quarantined'
                    results.append({'id':fid,'quarantine_id':entry['id']})
                except (OSError,ValueError) as ex:results.append({'id':fid,'error':str(ex)})
        return results
