import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aureon_defender.integrity import check

class Integrity(unittest.TestCase):
    def test_change_and_removal_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); p=root/'rule'; p.write_bytes(b'trusted')
            (root/'integrity.json').write_text(json.dumps({'files':{'rule':hashlib.sha256(b'trusted').hexdigest()}}))
            self.assertEqual(check(root)['status'], 'matches_baseline')
            p.write_bytes(b'changed')
            self.assertEqual(check(root)['findings'][0]['reason'], 'changed')
            p.unlink()
            self.assertEqual(check(root)['findings'][0]['reason'], 'missing')
    def test_path_escape_and_missing_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(check(root)['status'], 'unavailable')
            (root/'integrity.json').write_text(json.dumps({'files':{'../outside':'a'*64}}))
            self.assertEqual(check(root)['status'], 'collection_failed')

if __name__=='__main__':unittest.main()
