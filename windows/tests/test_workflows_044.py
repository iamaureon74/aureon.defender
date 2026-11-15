import unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from aureon_defender.scan_jobs import ScanJobs
from aureon_defender.scanner import sha256
from aureon_defender.agent import Api
from aureon_defender.core import Settings
class Workflows(unittest.TestCase):
 def wait(self,j):
  for _ in range(200):
   if j.snapshot()['status'] not in ('running','cancelling'):return j.snapshot()
   time.sleep(.01)
  self.fail('Scan stuck')
 def test_confirmed_only_auto_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'bad.txt').write_text('bad');(root/'uncertain.txt').write_text('uncertain');(root/'locked.txt').write_text('x');recycle=root/'$Recycle.Bin';recycle.mkdir();(recycle/'ignored.txt').write_text('x');calls=[]
   class Fake:
    def scan(self,p):
     if p.name=='locked.txt':return {'path':str(p),'verdict':'skipped','reasons':['File locked']}
     return {'path':str(p),'sha256':sha256(p),'verdict':'malicious' if p.name=='bad.txt' else 'suspicious','engines':{'reputation':'bad' if p.name=='bad.txt' else 'unknown'}}
   class Vault:
    def put(self,p,r):calls.append(p.name);return {'id':'fixture'}
   j=ScanJobs()
   with patch('pathlib.Path.home',return_value=root):j.start(Fake(),[root],vault=Vault(),automatic=True);st=self.wait(j)
   self.assertEqual(calls,['bad.txt']);self.assertEqual(st['auto_quarantined'],1);self.assertEqual(st['errors'],0);self.assertEqual(st['skipped'],2);self.assertTrue(any('locked' in x['path'] for x in st['diagnostics']));self.assertEqual(st['findings'][1]['action'] if st['findings'][1]['path'].endswith('uncertain.txt') else st['findings'][0]['action'],'pending')
 def test_cleanup_preference_needs_no_elevation(self):
  with tempfile.TemporaryDirectory() as d:
   a=Api.__new__(Api);a.settings=Settings(Path(d)/'machine.json');a.readonly=False;a.studio=None
   with patch('aureon_defender.agent.user_dir',return_value=Path(d)):
    # Invoke real authenticated dispatch beneath HTTP transport.
    method=getattr(a,'post',None) or getattr(a,'action',None)
    self.assertIsNotNone(method)
    code,result=method('/api/cleanup-policy',{'enabled':True});self.assertEqual(code,200);self.assertTrue(a.cleanup_enabled());self.assertFalse(a.settings.path.exists())
