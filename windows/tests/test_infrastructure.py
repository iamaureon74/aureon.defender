import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
from aureon.infrastructure import audit, validate
from aureon_defender import wifi_shield, powerline


class Infrastructure(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        self.data = dict(version=1, circuits=[dict(id='c1')], outlets=[dict(
            id='o1', circuit_id='c1', mapping='user_label', topic='tele/test/SENSOR', monitor_limit_w=100)])

    def obs(self, stamp='2026-11-14T12:00:00Z', watts=150):
        return dict(topic='tele/test/SENSOR', received_at=stamp, payload={'ENERGY': {'Power': watts}})

    def test_load_and_uncertain_mapping(self):
        r = audit(self.data, [self.obs()], self.now)
        self.assertEqual({f['code'] for f in r['findings']}, {'pmf_unverified','load_threshold','unverified_mapping'})
        self.assertFalse(r['control_available'])

    def test_stale_never_triggers_current_load_alert(self):
        r = audit(self.data, [self.obs('2026-11-13T12:00:00Z')], self.now)
        self.assertIn('stale_sensor', [f['code'] for f in r['findings']])
        self.assertNotIn('load_threshold', [f['code'] for f in r['findings']])

    def test_reject_invalid_and_future_data(self):
        r = audit(self.data, [self.obs(watts=float('nan')), self.obs('2027-01-01T00:00:00Z'), self.obs(watts=True)], self.now)
        self.assertEqual(r['rejected_observations'], 3)
        self.assertIsNone(r['outlets'][0]['measurement'])

    def test_latest_receipt_wins(self):
        r = audit(self.data, [self.obs(watts=40), self.obs('2026-11-14T11:59:00Z')], self.now)
        self.assertEqual(r['outlets'][0]['measurement']['watts'], 40)

    def test_tracing_requires_evidence(self):
        self.data['outlets'][0]['mapping'] = 'traced'
        with self.assertRaises(ValueError): validate(self.data)

    def test_duplicates_rejected(self):
        self.data['outlets'].append(dict(self.data['outlets'][0]))
        with self.assertRaises(ValueError): validate(self.data)

    def test_pmf_negative_is_not_supported(self):
        with patch.object(wifi_shield, '_run', return_value='802.11w Management Frame Protection supported : Not supported'):
            self.assertIs(wifi_shield.pmf_supported(), False)

    def test_homeplug_discovery_without_nic_name(self):
        with patch.object(powerline, 'toolkit', return_value='/usr/bin/amplist'), patch.object(powerline, '_run', return_value=('AA:BB:CC:DD:EE:FF\nAA:BB:CC:DD:EE:FF', 0)):
            r = powerline.audit()
        self.assertTrue(r['present'])
        self.assertEqual(len(r['nodes']['nodes']), 1)
        self.assertEqual(r['nodes']['nodes'][0]['circuit'], 'unknown')

    def test_tool_failure_visible(self):
        with patch.object(powerline, 'toolkit', return_value='amplist'), patch.object(powerline, '_run', return_value=('', 1)):
            self.assertEqual(powerline.audit()['nodes']['status'], 'collection_failed')


if __name__ == '__main__': unittest.main()
