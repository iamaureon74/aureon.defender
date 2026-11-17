import json,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from portable.app import handler,snapshot

class PortableTests(unittest.TestCase):
    def test_snapshot_scope(self):
        value=snapshot();self.assertTrue(value['platform']);self.assertIn('No quarantine',value['scope'])
    def test_token_host_and_bounded_post(self):
        state={'device':snapshot(),'busy':False};port=[0]
        server=ThreadingHTTPServer(('127.0.0.1',0),handler('local-test-token',state,threading.Lock(),port));port[0]=server.server_port
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        base=f'http://127.0.0.1:{port[0]}'
        try:
            with urllib.request.urlopen(base+'/?t=local-test-token') as r:self.assertIn(b'aureon',r.read())
            for headers in ({},{'Host':'untrusted.example','X-Aureon-Token':'local-test-token'}):
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers=headers))
                self.assertEqual(e.exception.code,403)
            with urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers={'X-Aureon-Token':'local-test-token'})) as r:self.assertIn('device',json.load(r))
        finally:server.shutdown();server.server_close();t.join()

class AutomationTests(unittest.TestCase):
    def test_new_download_gets_clean_copy_and_old_trash_goes(self):
        import tempfile,time,pathlib
        from portable.automation import Automation
        d=pathlib.Path(tempfile.mkdtemp());(d/'old.svg').write_text('<svg><!-- a --></svg>')
        t=pathlib.Path(tempfile.mkdtemp());(t/'info').mkdir();(t/'files').mkdir();(t/'files'/'x').write_text('x')
        (t/'info'/'x.trashinfo').write_text('[Trash Info]\nDeletionDate=2020-01-01T00:00:00\n')
        a=Automation(downloads=d,trash_days=30)
        a.tick_downloads()
        (d/'new.svg').write_text('<svg><!-- secret --><rect/></svg>')
        a.tick_downloads();a.tick_downloads();a.tick_downloads()
        self.assertFalse((d/'old.clean.svg').exists())
        self.assertNotIn('secret',(d/'new.clean.svg').read_text())
        self.assertIn('secret',(d/'new.svg').read_text())
        self.assertEqual(len(list(d.glob('*.clean*'))),1)
        with patch('aureon_defender.trash.linux_trash_dirs',return_value=[t]):a.tick_trash()
        self.assertFalse((t/'files'/'x').exists())
        self.assertTrue(a.report()['method'])

if __name__=='__main__':unittest.main()
