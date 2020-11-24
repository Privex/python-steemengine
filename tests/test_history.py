import unittest
from tests.base import *

class HistoryTest(SteemBaseTests):
    def test_history(self):
        """Get REAL_TOKEN history for TEST_ACC and confirm there are results"""
        res = self.stoken.list_transactions(TEST_ACC, REAL_TOKEN)
        self.assertGreater(len(res), 0)
    
    def test_history_noexist(self):
        """Get FAKE_TOKEN history for TEST_ACC and confirm it's empty"""
        res = self.stoken.list_transactions(TEST_ACC, FAKE_TOKEN)
        self.assertEqual(len(res), 0)

class HiveHistoryTest(HistoryTest, HiveBaseTests):
    pass

