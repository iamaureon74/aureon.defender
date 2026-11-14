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

if __name__=='__main__':unittest.main()
