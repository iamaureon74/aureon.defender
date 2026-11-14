import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aureon import security_node as node


class SecurityNode(unittest.TestCase):
    def test_usb_export_hides_raw_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root/'1-2'; d.mkdir()
            for k,v in {'idVendor':'1234','idProduct':'abcd','serial':'PRIVATE-SERIAL','authorized':'1'}.items():
                (d/k).write_text(v)
            first = node.usb_inventory(root)
            self.assertTrue(first[0]['authorized'])
            self.assertNotIn('PRIVATE-SERIAL', json.dumps(first))
            self.assertEqual(first, node.usb_inventory(root))
            (d/'idProduct').write_text('0000')
            changes = node.compare(node.usb_inventory(root), first)
            self.assertEqual(len(changes['added']), 1)
            self.assertEqual(len(changes['removed']), 1)

    def test_missing_bus_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(node.usb_inventory(Path(tmp)/'missing'))

    def test_bad_baseline_rejected(self):
        with self.assertRaises(ValueError): node.compare([], [{'port':'1-2'}])

    def test_windows_is_not_claimed_as_linux_coverage(self):
        with patch.object(node.platform, 'system', return_value='Windows'):
            r=node.collect()
        self.assertEqual(r['usb_status'], 'unavailable')
        self.assertEqual(r['services'], {})

    def test_service_failure_is_visible(self):
        with patch.object(node.shutil, 'which', return_value='/bin/systemctl'), patch.object(node.subprocess, 'run', side_effect=OSError):
            self.assertEqual(node.service_status('usbguard'), 'collection_failed')

    def test_import_marks_old_report_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'node.json'
            p.write_text(json.dumps(dict(version=1, mode='read_only', generated_at='2020-01-01T00:00:00Z', findings=[])))
            self.assertTrue(node.load_report(p)['stale'])
            p.write_text('{}')
            with self.assertRaises(ValueError): node.load_report(p)


if __name__ == '__main__': unittest.main()
