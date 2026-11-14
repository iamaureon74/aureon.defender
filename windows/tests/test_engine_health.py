import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aureon_defender.engine import Engine

class FeedHealth(unittest.TestCase):
    def test_missing_key_is_partial_and_offline_is_explicit(self):
        e=Engine.__new__(Engine)
        e.s={};e.rep=None;e.feeds=Mock();e.feeds.update.return_value={'feodo':5,'urlhaus':'needs key'}
        e.state={'modules':{}};e.errors={};e.next={'feeds':0};e.j=Mock();e.write_status=Mock()
        e.tasks=[('feeds',60,e.t_feeds,None)]
        with patch('aureon_defender.engine.feedmod.online',return_value=True),patch('aureon_defender.engine.mpcmdrun',return_value=None):
            e.run_once()
        self.assertEqual(e.state['modules']['feeds'],'partial')
        e.next['feeds']=0
        with patch('aureon_defender.engine.feedmod.online',return_value=False):e.run_once()
        self.assertEqual(e.state['modules']['feeds'],'offline_cached')

if __name__=='__main__':unittest.main()
