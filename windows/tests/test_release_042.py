import io
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[1])]
from aureon_defender.scan_jobs import ScanJobs
from aureon_defender import clean, telemetry


class NewWorkflows(unittest.TestCase):
    def wait(self,j):
        for _ in range(100):
            if j.snapshot()['status'] not in ('running','cancelling'):return
            time.sleep(.01)
        self.fail('Fixture scan did not finish')

    def test_read_only_scan_limit_findings_and_changed_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.txt';p.write_text('fixture')
            from aureon_defender.scanner import sha256
            class Fake:
                def scan(self,path):return {'path':str(path),'sha256':sha256(path),'verdict':'suspicious','reasons':['fixture'],'engines':{}}
            j=ScanJobs();j.start(Fake(),[Path(d)],limit=1);self.wait(j)
            st=j.snapshot();self.assertEqual(st['status'],'limited');self.assertEqual(st['finding_count'],1);self.assertEqual(p.read_text(),'fixture')
            p.write_text('changed')
            result=j.quarantine([st['findings'][0]['id']],None)
            self.assertIn('changed',result[0]['error'])

    def test_excluded_directory_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);private=root/'private';private.mkdir();(private/'x.txt').write_text('x');(root/'y.txt').write_text('y')
            calls=[]
            class Fake:
                def scan(self,path):calls.append(path);return {'verdict':'clean'}
            j=ScanJobs();j.start(Fake(),[root],exclusions=[private]);self.wait(j)
            self.assertEqual([p.name for p in calls],['y.txt'])

    def test_metadata_original_and_existing_copy_retained(self):
        from PIL import Image,PngImagePlugin
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.png';meta=PngImagePlugin.PngInfo();meta.add_text('Author','fixture-person')
            Image.new('RGB',(3,3),'red').save(p,pnginfo=meta);before=p.read_bytes()
            result=clean.clean_batch([str(p)]);self.assertEqual(len(result['results']),1);self.assertEqual(p.read_bytes(),before)
            out=Path(result['results'][0]['written']);self.assertNotIn(b'fixture-person',out.read_bytes())
            result2=clean.clean_batch([str(p)]);self.assertNotEqual(result2['results'][0]['written'],str(out));self.assertTrue(out.exists())

    def test_unsupported_and_corrupt_files_visible(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.gif';p.write_bytes(b'GIF');(Path(d)/'other.bin').write_bytes(b'x')
            result=clean.clean_batch([d]);self.assertTrue(result['errors']);self.assertEqual(result['skipped'],1);self.assertEqual(p.read_bytes(),b'GIF')

    def test_video_metadata_payload_actually_removed(self):
        payload=b'secret-location';udta=struct.pack('>I4s',8+len(payload),b'udta')+payload
        data=struct.pack('>I4s',8+len(udta),b'moov')+udta
        out,removed=clean._mp4(data);self.assertEqual(len(out),len(data));self.assertNotIn(payload,out);self.assertTrue(removed)

    def test_battery_keeps_reported_precision_network_is_observed(self):
        from types import SimpleNamespace as N
        with patch('psutil.sensors_battery',return_value=N(percent=98,power_plugged=True,secsleft=-1)),patch('psutil.net_io_counters',return_value=N(bytes_sent=100,bytes_recv=200)),patch('psutil.net_if_stats',return_value={}):
            telemetry._last=None;a=telemetry.collect()
            self.assertEqual(a['battery']['percent'],98);self.assertIsNone(a['network']['download_mbps']);self.assertIn('Not internet',a['network']['scope'])

    def test_optional_clamav_has_no_remediation_and_reports_missing(self):
        from aureon_defender.integrations import clamav_scan
        with patch('shutil.which',return_value=None):self.assertEqual(clamav_scan('fixture')[0],'unavailable')
        from types import SimpleNamespace as N
        with patch('shutil.which',return_value='trusted-clamscan'),patch('subprocess.run',return_value=N(returncode=1,stdout='fixture FOUND',stderr='')) as run:
            self.assertEqual(clamav_scan(Path('fixture').resolve())[0],'threat')
            args=run.call_args.args[0];self.assertNotIn('--remove',args);self.assertNotIn('--move',args);self.assertFalse(run.call_args.kwargs.get('shell',False))

    def test_fix_all_preview_cannot_modify_settings(self):
        from aureon_defender.agent import Api
        from aureon_defender.leaks import USER_FIXABLE
        api=object.__new__(Api);api.studio=None;api.readonly=False
        key=next(iter(USER_FIXABLE))
        checks=[{'id':key,'ok':False,'title':'fixture'},{'id':'manual-example','ok':False,'title':'manual'}]
        with patch('aureon_defender.leaks.audit',return_value=checks),patch('aureon_defender.leaks.fix') as fix:
            status,result=api.post('/api/leaks/fix-all',{})
            self.assertEqual(status,200);self.assertTrue(result['preview']);fix.assert_not_called();self.assertEqual(len(result['unresolved']),1)
            status,result=api.post('/api/leaks/fix-all',{'confirm':True});fix.assert_called_once_with(key);self.assertEqual(status,200)
