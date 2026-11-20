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


def ordered_roots():
    """User folders first (where threats land), then every fixed drive. Duplicated paths are skipped by the walker."""
    users = Path(os.environ.get('SYSTEMDRIVE', 'C:') + '\\Users') if os.name == 'nt' else Path.home()
    return ([users] if users.is_dir() else []) + local_roots()


class ScanJobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.state = {'status':'idle', 'scanned':0, 'skipped':0, 'errors':0, 'findings':[], 'finding_count':0}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def start(self, scanner, roots=None, exclusions=(), limit=200000, vault=None, automatic=False, journal=None, react=None, kind='full', on_done=None):
        with self.lock:
            if self.state['status'] in ('running','cancelling'):
                raise ValueError('A full scan is already running')
            roots = list(local_roots() if roots is None else roots)
            self.cancel.clear()
            self.state = {'id':uuid.uuid4().hex, 'kind':kind, 'status':'running','started':time.time(),'scanned':0,'skipped':0,'errors':0,'findings':[],'finding_count':0,'roots':[str(p) for p in roots],'current':'','limit':limit,'diagnostics':[], 'auto_quarantined':0, 'scope':'Accessible local fixed-drive files. Recycle Bin, protected volume data, links and runtime data excluded. Automatic quarantine only for confirmed threats in current-user folders when enabled.'}
            threading.Thread(target=self._run,args=(scanner,roots,exclusions,limit,vault,automatic,journal,react,on_done),name='aureon-fullscan',daemon=True).start()
            return self.snapshot()

    def stop(self):
        with self.lock:
            if self.state['status']=='running':
                self.cancel.set();self.state['status']='cancelling'
        return self.snapshot()

    def _run(self, scanner, roots, exclusions, limit, vault=None, automatic=False, journal=None, react=None, on_done=None):
        excluded=[Path(p).resolve() for p in exclusions]
        count=0
        def blocked(p):
            try:
                return p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) or any(p.resolve().is_relative_to(x) for x in excluded)
            except OSError:
                return True
        def record(kind, path, reason):
            with self.lock:
                self.state['skipped' if kind=='skipped' else 'errors']+=1
                if len(self.state['diagnostics'])<100:
                    self.state['diagnostics'].append({'kind':kind,'path':str(path),'reason':str(reason)})
        def error(ex):
            expected=isinstance(ex,(PermissionError,FileNotFoundError)) or getattr(ex,'winerror',None) in (2,3,5,32,33)
            record('skipped' if expected else 'error',getattr(ex,'filename',''),ex)
        done=[]                                   # roots already walked: a later drive root skips them
        try:
            for root in roots:
                if self.cancel.is_set() or count>=limit:break
                for folder, dirs, files in os.walk(root, followlinks=False, onerror=error):
                    if self.cancel.is_set() or count>=limit:break
                    keep=[]
                    for d in dirs:
                        dp=Path(folder)/d
                        if os.path.normcase(str(dp)) in done:
                            continue
                        if d.lower() in ('$recycle.bin','system volume information') or blocked(dp):
                            record('skipped',dp,'Folder excluded from this scan: protected storage, link or configured exclusion')
                        else:keep.append(d)
                    dirs[:]=keep
                    for name in files:
                        if self.cancel.is_set() or count>=limit:break
                        p=Path(folder)/name
                        if blocked(p):
                            with self.lock:self.state['skipped']+=1
                            continue
                        with self.lock:self.state['current']=str(p)
                        try:
                            # Detect first; only confirmed, unchanged user files may be automatically isolated.
                            result=scanner.scan(p)
                        except Exception as ex:
                            result={'verdict':'error','reasons':[str(ex)]}
                        count+=1
                        with self.lock:
                            self.state['scanned']=count
                            verdict=result.get('verdict')
                            if verdict in ('error','skipped'):
                                record(verdict,p,'; '.join(result.get('reasons',[])) or result.get('skip_reason') or 'File could not be scanned')
                            if verdict in ('malicious','suspicious'):
                                self.state['finding_count']+=1
                                if len(self.state['findings'])<1000:
                                    item={**result,'id':uuid.uuid4().hex,'recommendation':'Review evidence; uncertain matches are not deleted. Confirmed threats can be reversibly quarantined.','action':'pending'}
                                    engines=result.get('engines',{})
                                    confirmed=engines.get('reputation')=='bad' or engines.get('defender')=='threat' or engines.get('clamav')=='threat'
                                    user_owned=p.resolve().is_relative_to(Path.home().resolve())
                                    if react is not None:
                                        # engine autopilot: remove unless the hardware needs it (hwguard.decide)
                                        try:
                                            ev=react(p,result) or {}
                                        except Exception as ex:
                                            ev={'detail':str(ex)}
                                        item.update(action='removed' if ev.get('blocked') else 'kept',recommendation=ev.get('detail') or '',quarantine_id=ev.get('quarantine_id'))
                                        if ev.get('blocked'):self.state['auto_quarantined']+=1
                                        if journal and ev:journal(ev)
                                    elif automatic and vault is not None and verdict=='malicious' and confirmed and user_owned:
                                        try:
                                            from .scanner import sha256
                                            if not result.get('sha256') or sha256(p)!=result['sha256']:
                                                raise ValueError('File changed since scanning; rescan required')
                                            entry=vault.put(p,result)
                                            item.update(action='quarantined',quarantine_id=entry['id'],recommendation='Automatically isolated. Restore from Quarantine if this was a false positive.')
                                            self.state['auto_quarantined']+=1
                                            if journal:journal.add('high','threat','Confirmed threat automatically quarantined',str(p),quarantine_id=entry['id'])
                                        except (OSError,ValueError) as ex:
                                            item['remediation_error']=str(ex)
                                            item['recommendation']='Automatic isolation failed: '+str(ex)+'. No deletion performed.'
                                    self.state['findings'].append(item)
                done.append(os.path.normcase(str(root)))
            with self.lock:
                self.state.update(status='cancelled' if self.cancel.is_set() else 'limited' if count>=limit else 'completed',finished=time.time(),current='')
        except Exception as ex:
            with self.lock:self.state.update(status='failed',error=str(ex),finished=time.time())
        if on_done:
            try:on_done(self.snapshot())
            except Exception:pass

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
