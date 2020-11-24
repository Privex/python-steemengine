from decimal import Decimal
import unittest
from tests.base import *

class SteemTokenTest(SteemBaseTests):

    def test_get_token(self):
        """Get REAL_TOKEN and confirm the object returned is valid"""
        res = self.stoken.get_token(REAL_TOKEN)
        self.assertEqual(res['symbol'].upper(), REAL_TOKEN)
        self.assertEqual(res['issuer'], TEST_ACC)
    
    def test_get_all_balances(self):
        """Get all balances for user TEST_ACC, and verify that REAL_TOKEN is in there"""
        res = list(self.stoken.get_balances(TEST_ACC))
        self.assertIs(type(res), list)
        self.assertGreater(len(res), 0)
        syms = [t['symbol'].upper() for t in res]
        self.assertTrue(REAL_TOKEN in syms)
    
    def test_get_balance(self):
        """Get a single balance from TEST_ACC for REAL_TOKEN which should be positive"""
        res = self.stoken.get_token_balance(TEST_ACC, REAL_TOKEN)
        self.assertIs(type(res), Decimal)
        self.assertGreater(res, Decimal('0'))
    
    def test_get_token_no_exist(self):
        """Get non-existant FAKE_TOKEN and confirm the object is None"""
        self.assertEqual(self.stoken.get_token(FAKE_TOKEN), None)
    
    def test_get_balance_noexist(self):
        """Get the TEST_ACC balance for non-existant FAKE_TOKEN and confirm it's zero"""
        self.assertEqual(self.stoken.get_token_balance(TEST_ACC, FAKE_TOKEN), Decimal('0'))
    
    def test_account_exists(self):
        """Test account_exists returns true for TEST_ACC"""
        self.assertTrue(self.stoken.account_exists(TEST_ACC))
    
    def test_account_no_exists(self):
        """Test account_exists returns false for non-existant FAKE_ACC"""
        self.assertFalse(self.stoken.account_exists(FAKE_ACC))


class HiveTokenTest(SteemTokenTest, HiveBaseTests):
    pass

