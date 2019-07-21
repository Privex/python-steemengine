#!/usr/bin/env python3
"""
Unit tests for Privex's SteemEngine library.

To run them, either just run tests.py directly, or use pytest

.. code-block:: bash
    ./tests.py
    # Verbose mode
    ./tests.py

    # With pytest
    pip3 install pytest
    pytest tests.py
    # Verbose mode
    pytest tests.py -v


"""
import unittest
from decimal import Decimal
from privex.steemengine import SteemEngineToken, SteemEngineHistory

SteemEngineToken.custom_beem(node=['https://steemd.privex.io', 'https://api.steemit.com'])

st = SteemEngineToken()
FAKE_TOKEN = 'NONEXISTANTTOKEN'
REAL_TOKEN = 'SGTK'
TEST_ACC = 'someguy123'
FAKE_ACC = 'non-existant-account999'

class TokenTest(unittest.TestCase):

    def test_get_token(self):
        """Get REAL_TOKEN and confirm the object returned is valid"""
        res = st.get_token(REAL_TOKEN)
        self.assertEqual(res['symbol'].upper(), REAL_TOKEN)
        self.assertEqual(res['issuer'], TEST_ACC)
    
    def test_get_all_balances(self):
        """Get all balances for user TEST_ACC, and verify that REAL_TOKEN is in there"""
        res = st.get_balances(TEST_ACC)
        self.assertIs(type(res), list)
        self.assertGreater(len(res), 0)
        syms = [t['symbol'].upper() for t in res]
        self.assertTrue(REAL_TOKEN in syms)
    
    def test_get_balance(self):
        """Get a single balance from TEST_ACC for REAL_TOKEN which should be positive"""
        res = st.get_token_balance(TEST_ACC, REAL_TOKEN)
        self.assertIs(type(res), Decimal)
        self.assertGreater(res, Decimal('0'))
    
    def test_get_token_no_exist(self):
        """Get non-existant FAKE_TOKEN and confirm the object is None"""
        self.assertEqual(st.get_token(FAKE_TOKEN), None)
    
    def test_get_balance_noexist(self):
        """Get the TEST_ACC balance for non-existant FAKE_TOKEN and confirm it's zero"""
        self.assertEqual(st.get_token_balance(TEST_ACC, FAKE_TOKEN), Decimal('0'))
    
    def test_account_exists(self):
        """Test account_exists returns true for TEST_ACC"""
        self.assertTrue(st.account_exists(TEST_ACC))
    
    def test_account_no_exists(self):
        """Test account_exists returns false for non-existant FAKE_ACC"""
        self.assertFalse(st.account_exists(FAKE_ACC))
        
    

class HistoryTest(unittest.TestCase):
    def test_history(self):
        """Get REAL_TOKEN history for TEST_ACC and confirm there are results"""
        res = st.list_transactions(TEST_ACC, REAL_TOKEN)
        self.assertGreater(len(res), 0)
    
    def test_history_noexist(self):
        """Get FAKE_TOKEN history for TEST_ACC and confirm it's empty"""
        res = st.list_transactions(TEST_ACC, FAKE_TOKEN)
        self.assertEqual(len(res), 0)


if __name__ == '__main__':
    unittest.main()
