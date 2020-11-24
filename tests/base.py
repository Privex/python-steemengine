import unittest
from decimal import Decimal

from privex.helpers import DictObject

from privex.steemengine import SteemEngineToken, SteemEngineHistory

__all__ = [
    'st', 'SEBase', 'SteemBaseTests', 'HiveBaseTests', 'NetworkBaseTests',
    'FAKE_TOKEN', 'REAL_TOKEN', 'ACTIVE_TOKENS', 'TEST_ACC', 'FAKE_ACC'
]

# SteemEngineToken.custom_beem(node=['https://api.steemit.com'])

st = SteemEngineToken()
FAKE_TOKEN = 'NONEXISTANTTOKEN'
REAL_TOKEN = 'SGTK'
ACTIVE_TOKENS = DictObject(steem='ENG', hive='BEE')
TEST_ACC = 'someguy123'
FAKE_ACC = 'non-existent-account999'

class SEBase(unittest.TestCase):
    s_nodes = ['https://api.steemit.com']
    s_kwargs = dict(network='steem')
    
    @classmethod
    def setUpClass(cls) -> None:
        cls.stoken = SteemEngineToken()


class SteemBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stoken = SteemEngineToken(nodes=['https://api.steemit.com'])

class HiveBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stoken = SteemEngineToken(network='hive')

class NetworkBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.steem = SteemEngineToken(network='steem')
        cls.hive = SteemEngineToken(network='hive')

