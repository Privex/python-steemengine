import functools
import logging
from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Union, List, Dict, Set, Optional
from privex.jsonrpc import SteemEngineRPC
from privex.steemengine import exceptions
from privex.steemengine.SteemEngineHistory import SteemEngineHistory
from privex.steemengine.exceptions import NoResults, WrongNetwork
from privex.steemengine.objects import SEBalance, SETransaction, Token, SETrade, SEOrder, SETransactionInfo, conv_dec, AnyNum, \
    SEPlacedOrder, SETicker
from privex.helpers import empty, empty_if, dec_round, r_cache, DictObject
from privex.helpers.black_magic import caller_name

log = logging.getLogger(__name__)
getcontext().rounding = ROUND_DOWN


def round_str(amount: AnyNum, dp: AnyNum = 2) -> str:
    """Round ``amount`` to ``dp`` decimal places as a string"""
    return ('{0:.' + str(int(dp)) + 'f}').format(conv_dec(amount))


def _cache_blacklisted(skip=3) -> bool:
    try:
        from privex.helpers.black_magic import calling_module, calling_function, caller_name
        
        # Exact module + function/method path match
        if caller_name(skip=skip) in SteemEngineToken.CACHE_BLACKLIST:
            return True
        # Plain function name match
        if calling_function(skip=skip) in SteemEngineToken.CACHE_BLACKLIST_FUNCS:
            return True
        
        _mod = calling_module(skip=skip)
        # Exact module path match
        if _mod in SteemEngineToken.CACHE_BLACKLIST_MODS:
            return True
        # Sub-modules path match (e.g. if hello.world is blacklisted, then hello.world.example is also blacklisted)
        for _m in SteemEngineToken.CACHE_BLACKLIST_MODS:
            if _mod.startswith(_m + '.'):
                return True
    
    except Exception:
        log.exception("Failed to check blacklist for _cache_blacklisted. Falling back to standard r_cache.")
    
    return False


def se_cache(cache_key: Union[str, callable], cache_time=300, *c_args, **c_kwargs):
    """
    Sometimes the :func:`.r_cache` decorator can cause problems, especially within an AsyncIO application.
    
    This wrapper allows :func:`.r_cache` to be disabled either globally by setting :attr:`.SteemEngineToken.CACHE` to ``False``,
    or per function/method/module using caller blacklists such as :attr:`.SteemEngineToken.CACHE_BLACKLIST`
    """
    def _decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if _cache_blacklisted():
                log.debug("caller is cache blacklisted! not using cache key '%s' - calling '%s' directly!", cache_key, f.__name__)
                return f(*args, **kwargs)
            if SteemEngineToken.CACHE:
                log.debug("caching enabled! wrapped func '%s' - accessing cache key '%s' via r_cache", f.__name__, cache_key)
                return r_cache(cache_key, cache_time, *c_args, **c_kwargs)(f)(*args, **kwargs)
            log.debug("caching disabled! not using cache key '%s' - calling '%s' directly!", cache_key, f.__name__)
            return f(*args, **kwargs)
        return wrapper
    return _decorator

BEEM = Union["beem.steem.Steem", "beem.hive.Hive"]

class SteemEngineToken:
    """
    SteemEngineToken - a wrapper class around :py:class:`privex.jsonrpc.SteemEngineRPC`, with support
    for signing transactions, including issuing/sending tokens.
    
    Copyright::

        +===================================================+
        |                 © 2019 Privex Inc.                |
        |               https://www.privex.io               |
        +===================================================+
        |                                                   |
        |        Python Steem Engine Library                |
        |        License: X11/MIT                           |
        |                                                   |
        |        Core Developer(s):                         |
        |                                                   |
        |          (+)  Chris (@someguy123) [Privex]        |
        |                                                   |
        +===================================================+


    **Basic usage**:

        >>> from privex.steemengine import SteemEngineToken
        >>> s = SteemEngineToken()
        >>> # Send 10 ENG to @privex from @someguy123 with the memo 'hello memo'
        >>> s.send_token('ENG', 'someguy123', 'privex', Decimal('10'), 'hello memo')

    """

    _steem = None   # type: beem.steem.Steem
    """Static attribute to be initialised by :py:meth:`.steem` to hold :class:`beem.steem.Steem`"""

    _steem_ins: Dict[str, "beem.steem.Steem"] = {
        "steem": None, "hive": None
    }

    network: str
    native_coin: str
    default_nodes: Union[Dict[str, List[str]], DictObject] = DictObject(
        steem=[
            'https://api.steemit.com',
            'https://api.steemdb.online',
            'https://api.justyy.com',
            'https://api.steemitdev.com',
            'https://api.steem.buzz',
        ],
        hive=[
            'https://hived.privex.io',
            'https://anyx.io',
            'https://hived.hive-engine.com',
            'https://api.openhive.network',
            'https://fin.hive.3speak.co',
            'https://api.hive.blog',
        ],
    )
    """
    This is a class-level attribute (shared by all instances, instead of specific to one instance),
    which contains a list of RPC nodes to be used by default for each network.

    To add additional nodes to the list for a network::

        >>> from privex.steemengine import SteemEngineToken
        >>> SteemEngineToken.default_nodes.hive.append("https://hived.example.com")
        >>> # Or if you want to add nodes in bulk
        >>> SteemEngineToken.default_nodes.hive += ['https://hived.example.com', 'https://api.example.hive', 'https://another.example']

    To remove a specific RPC node for a network::
        
        >>> SteemEngineToken.default_nodes.hive.remove('https://anyx.io')

    If you want to entirely replace the list of default nodes for a network (or both), we recommend that you DON'T attempt
    to overwrite ``default_nodes`` or one of the lists contained within it - otherwise there's a risk that some instances 
    of :class:`.SteemEngineToken` might still be referencing the original DictObject / list objects.

    Instead, you should clear the list, and then inject the nodes you want to use::
        
        >>> SteemEngineToken.default_nodes.steem.clear()
        >>> SteemEngineToken.default_nodes.steem += ['https://steemd.example.com', 'https://api.example.steem', 'https://another.example']


    """

    use_shared_instances: bool = False
    """
    This is a class-level attribute that controls whether instances of :class:`.SteemEngineToken` should use Beem's shared instances.
    
    To prevent issues when dealing with more than one network in the same application, only the network that the
    first :class:`.SteemEngineToken` instance uses, will use / create a shared instance.

    If this is disabled, then new instances will instead automatically create a brand new instance of Beem, instead of
    trying to use a shared instance.
    """

    DEFAULT_BLOCKCHAIN_URL = '/rpc/blockchain'
    
    CACHE = True
    """Global cache switch. Set ``SteemEngineToken.CACHE = False`` to disable the :func:`.se_cache` caching decorator"""
    CACHE_BLACKLIST = []
    """A list of fully qualified module paths to functions/methods which always bypass :func:`.se_cache`"""
    CACHE_BLACKLIST_FUNCS = []
    """A list of plain function names which always bypass :func:`.se_cache`"""
    CACHE_BLACKLIST_MODS = []
    """A list of fully qualified module names which always bypass :func:`.se_cache`"""

    @property
    def steem(self) -> Union["beem.steem.Steem", "beem.hive.Hive"]:
        """
        When a method calls ``self.steem`` , this property will first try to return :py:attr:`._steem`
        if it was previously called. Otherwise, it will automatically initialise :py:attr:`._steem`
        with an instance of :class:`beem.steem.Steem` and then return it.
        
        This ensures that Beem isn't initialised unless it's actually needed, preventing un-necessary
        slowdowns of the application using this library due to Beem attempting to find a working RPC node.

        :return beem.steem.Steem steem: An instance of :class:`beem.steem.Steem`
        """
        cls = SteemEngineToken
        if not self._steem_ins[self.network]:
            from beem.instance import SharedInstance, shared_steem_instance
            nodes = cls.default_nodes[self.network]
            if cls.use_shared_instances:
                if SharedInstance.instance is None:
                    SharedInstance.instance = self.custom_beem(nodes, network=self.network)
                else:
                    # Check to make sure no other network is already using a shared instance before we try to use the shared instance.
                    for k, v in cls._steem_ins:
                        if v == SharedInstance.instance:
                            log.debug(f"One or more networks are already using a shared instance. Network {k} appears to be using one.")
                            log.debug(f"For safety, we're going to create a new instance for the network '{self.network}' instead "
                                      f"of using a shared instance that may be on the wrong network.")
                            cls._steem_ins[self.network] = self.custom_beem(nodes, network=self.network)
                            return cls._steem_ins[self.network]

                cls._steem_ins[self.network] = SharedInstance.instance
                return cls._steem_ins[self.network]

            cls._steem_ins[self.network] = self.custom_beem(nodes, network=self.network)
        return cls._steem_ins[self.network]

    @steem.setter
    def steem(self, value: BEEM):
        """
        This is a property setter which allows a user to override the instance used by ``.steem``

        To manually set the Beem instance used by a :class:`.SteemEngineToken` instance::
            
            >>> st = SteemEngineToken(network="hive")
            >>> st.steem = st.custom_beem(['https://hived.privex.io', 'https://anyx.io'], "hive")

        """

        SteemEngineToken._steem_ins[self.network] = value

    def set_beem(self, nodes: Union[str, List[str]] = None, network: str = None, *args, **kwargs) -> BEEM:
        """
        Create and override the Beem instance used by this instance::

            >>> st = SteemEngineToken(network="hive")
            >>> st.set_beem(["https://hived.privex.io", "https://anyx.io"])

        """
        network = empty_if(network, self.network)
        
        SteemEngineToken._steem_ins[network] = s = self.custom_beem(nodes, *args, network=network, **kwargs)
        return s

    def verify_network(self, network: str = None, inst: Optional[BEEM] = None):
        """
        Check that the current RPC node is on the correct blockchain network.

        :raises WrongNetwork: When the current RPC node of :attr:`.steem` or ``inst``'s network doesn't match ``network`` / ``self.network``
        """
        network = empty_if(network, self.network).lower()
        inst = empty_if(inst, self.steem)
        ins_net = inst.get_blockchain_name().lower()
        if ins_net != network:
            raise WrongNetwork(f"The RPC node '{inst.rpc.url}' is on the WRONG NETWORK. '{inst.rpc.url}' is a '{ins_net}' node - but your network is set to: {network}")
        return True
        

    def __init__(self, network_account='ssc-mainnet1', history_conf: dict = None, network="steem", **rpc_args):
        """
        Initialises the class with various configuration options. All parameters are optional.

        Pass a dict in ``history_conf`` to override the SteemEngine history node used
        Pass extra kwargs such as ``hostname='api.example.com'`` ot override the SteemEngine RPC node used.

        :param network_account: The Steem account that operates the SteemEngine network, e.g. ssc-mainnet1 for the
                                Steem Smart Contracts Main Network
        :param history_conf:    A dictionary containing kwargs to pass to :py:class:`.SteemEngineHistory` constructor
        :param rpc_args:        Any additional kwargs will be passed to the :py:class:`privex.jsonrpc.SteemEngineRPC` constructor

        :keyword str|list nodes: If the ``nodes`` kwarg is specified, e.g. ``nodes=['https://api.something.com']``, then
                                 Beem will be configured during ``__init__`` to use those specific RPC nodes.

        """
        rpc_args = dict(rpc_args)
        history_conf = {} if history_conf is None else history_conf
        network = network.lower()
        self.network = network

        if 'nodes' in rpc_args:
            nodes = rpc_args.pop('nodes')
            self.set_beem(nodes)

        native_coin = 'STEEMP'
        if network == "hive":
            rpc_args['hostname'] = rpc_args.get('hostname', 'api.hive-engine.com')
            rpc_args['url'] = rpc_args.get('url', '/rpc/contracts')
            network_account = 'ssc-mainnet-hive'
            history_conf['hostname'] = history_conf.get('hostname', 'accounts.hive-engine.com')
            history_conf['url'] = history_conf.get('url', 'accountHistory')
            native_coin = 'SWAP.HIVE'
        
        self.native_coin = rpc_args.pop('native_coin', native_coin).upper()
        
        self.rpc = SteemEngineRPC(**dict(rpc_args))
        if 'url' in rpc_args:
            del rpc_args['url']
        self.block_rpc = SteemEngineRPC(**rpc_args, url=self.DEFAULT_BLOCKCHAIN_URL)
        self.network_account = network_account
        self.history_rpc = SteemEngineHistory(**history_conf)
        log.debug('Initialized SteemEngineToken with args: %s %s %s', network_account, history_conf, rpc_args)

    @property
    @se_cache(lambda self: f"pvx_seng:token:{self.native_coin}")
    def native_token(self) -> Token:
        """Returns the :class:`.Token` object for the native coin :attr:`.native_coin`"""
        return self.get_token(self.native_coin)

    @staticmethod
    def custom_beem(node: Union[str, list] = "", *args, network="steem", **kwargs) -> BEEM:
        """
        Generates a new Beem :class:`.Steem` / :class:`.Hive` instance

        Example usage::

            >>> from privex.steemengine import SteemEngineToken
            >>> steem = SteemEngineToken.custom_beem(node=['https://steemd.privex.io', 'https://api.steemit.com'])
            >>> steem.get_blockchain_name()
            'steem'

        This can be used to manually set the Beem instance used by a :class:`.SteemEngineToken` instance::
            
            >>> st = SteemEngineToken(network="hive")
            >>> st.steem = st.custom_beem(['https://hived.privex.io', 'https://anyx.io'], "hive")

        """
        from beem.steem import Steem
        from beem.hive import Hive
        network = network.lower()
        #SteemEngineToken._steem = Steem(node, *args, **kwargs)
        if network == "hive":
            return Hive(node, *args, **kwargs)
        return Steem(node, *args, **kwargs)

    def get_balances(self, user) -> List[SEBalance]:
        """
        Get all token balances for a user.

        **Example:**

            >>> balances = SteemEngineToken().get_balances('someguy123')
            >>> for bal in balances:
            ...     print(f"{bal.symbol} balance is: {bal.balance}")
            ENG balance is: 12.345
            SGTK balance is: 51235
            STEEMP balance is: 102.437

        :param user: Username to find all token balances for
        :return list<SEBalance> balances: All balances of a user [{account:str, symbol:str, balance:str}...]
        """
        log.debug('Finding all token balances for user %s', user)
        return list(SEBalance.from_list(self.rpc.find(
            contract='tokens',
            table='balances',
            query=dict(account=user)
        ), seng_ins=self))

    def get_token_balance(self, user, symbol) -> Decimal:
        """
        Find a specific token balance of a user.

        **Example:**

            >>> SteemEngineToken().get_token_balance('someguy123', 'ENG')
            Decimal(12.345)


        :param str user: Username to find given ``symbol`` balance for
        :param str symbol: Symbol of the token to lookup, such as 'ENG'
        :return Decimal balance: The user's balance. ``Decimal(0)`` if their balance is empty, or they don't have the token.
        """
        balances = self.get_balances(user)
        for bal in balances:
            if bal.symbol == symbol.upper():
                log.debug('Found token balance matching %s, returning %s', symbol, bal.balance)
                return bal.balance
        log.debug('Did not find token balance matching %s, returning 0', symbol)
        return Decimal(0)

    @se_cache(lambda self, user: f"pvx_seng:account_exists:{user}", 30)
    def account_exists(self, user) -> bool:
        """
        Helper function to verify if a given user exists on Steem.

        **Example:**

            >>> st = SteemEngineToken()
            >>> if st.account_exists('someguy123'):
            ...     print('someguy123 exists')
            someguy123 exists
        

        :param str user: Steem username to lookup
        :return bool exists: True if the user exists, False if they don't
        """
        # Make sure we're on the correct network before checking
        self.verify_network()
        log.debug('Checking if user %s exists', user)
        return len(self.steem.rpc.get_account(user)) > 0

    @se_cache(lambda self, limit=1000, offset=0: f"pvx_seng:list_tokens:{limit}:{offset}", 120)
    def list_tokens(self, limit=1000, offset=0) -> List[Token]:
        """
        Returns a list of all tokens as :class:`.Token` objects.

        **Example:**

            >>> for t in SteemEngineToken().list_tokens():
            ...     print(f"Token {t.symbol} has a max supply of {t.max_supply} and issued by {t.issuer}")
            Token ENG has a max supply of 9007199254740991 and issued by null
            Token STEEMP has a max supply of 1000000000000 and issued by steem-peg
            Token BTCP has a max supply of 1000000000000 and issued by btcpeg
            Token LTCP has a max supply of 1000000000000 and issued by ltcp

        :param limit: Amount of token objects to retrieve
        :param offset: Amount of token objects to skip (for pagination)
        :return List<Token> tokens: Each :class:`.Token` list item formatted like this:

        .. code-block:: js

            {
                issuer:str, 
                symbol:str,
                name:str,
                metadata:str,
                precision:int,
                maxSupply: int,
                supply: int,
                circulatingSupply:int
            }
        
        """
        return list(Token.from_list(self.rpc.find(
            contract='tokens',
            table='tokens',
            query={},
            limit=limit, offset=offset
        )))

    def query_order_history(self, limit=30, offset=0, indexes: List[dict] = None, **query) -> List[SETrade]:
        """
        Used internally by methods such as :meth:`.order_history` and :meth:`.find_fulfilled_sells` etc.
        
        Queries the ``market`` contract table ``tradeHistory`` using the query params passed as kwargs via ``query``.
        
        :param int limit: Amount of orders to retrieve
        :param int offset: Offset selection by this many rows (for pagination)
        :param list indexes: A list of dictionary indexes, e.g. ``[dict(descending=False, index='timestamp')]``
        :param query: Query parameters to filter order history
        :return List[SETrade] orders: A list of :py:class:`.SETrade` objects
        """
        indexes = [dict(descending=False, index='_id')] if empty(indexes) else indexes
        data = dict(
            contract='market', table='tradesHistory',
            query=dict(query), indexes=indexes,
            limit=limit, offset=offset
        )
        res = self.rpc.find(**data)
        if empty(res):
            raise NoResults("query_order_history got empty (None) response from API...")
        return list(SETrade.from_list(res, seng_ins=self))
    
    def order_history(self, symbol, limit=30, offset=0, indexes: List[dict] = None, **query) -> List[SETrade]:
        """
        Get a list of recent Steem Engine orders for a given symbol.

        **Example:**

            >>> st = SteemEngineToken()
            >>> o = SteemEngineToken().order_history('ENG')
            >>> o[0]
            <SETrade type='buy' price='0.99' symbol='ENG' quantity='0.80405854'>
            >>> o[0].timestamp
            '2019-07-27 01:06:09'
            
            >>> st = SteemEngineToken(network='hive')
            >>> ht = st.order_history('BEE', sellTxId='d442b0156ccddb0d6fca381fa0a8ea027b318d17')
            >>> dict(ht[0])
            {'_id': 61528, 'type': 'sell',
             'buyer': 'arquitectojm', 'seller': 'cryptomancer', 'symbol': 'BEE',
             'quantity': Decimal('3'), 'price': Decimal('0.94900000'),
             'timestamp': datetime.datetime(2020, 6, 21, 8, 0, 9, tzinfo=tzutc()),
             'volume': Decimal('2.84700000'),
             'buyTxId': '6e0d09cd45e94eaf4fb2b85cdc0b9d3a28401cbd',
             'sellTxId': 'd442b0156ccddb0d6fca381fa0a8ea027b318d17',
             'direction': 'sell'
             }


        :param str symbol: The symbol to get historic orders for
        :param int limit: Amount of orders to retrieve
        :param int offset: Offset selection by this many rows (for pagination)
        :param query: Additional query parameters to filter order history
        :param list indexes: A list of dictionary indexes, e.g. ``[dict(descending=False, index='timestamp')]``
        :return List[SETrade] orders: A list of :py:class:`.SETrade` objects
        """
        return self.query_order_history(
            limit=limit, offset=offset, indexes=indexes, symbol=symbol, **query
        )

    trade_history = order_history

    def find_fulfilled_sells(self, txid: str, limit=30, offset=0, indexes: List[dict] = None, **query) -> List[SETrade]:
        return self.query_order_history(
            limit=limit, offset=offset, indexes=indexes, sellTxId=txid, **query
        )

    def find_fulfilled_buys(self, txid: str, limit=30, offset=0, indexes: List[dict] = None, **query) -> List[SETrade]:
        return self.query_order_history(
            limit=limit, offset=offset, indexes=indexes, buyTxId=txid, **query
        )

    def find_fulfilled(self, txid: str, limit=30, offset=0, indexes: List[dict] = None, **query) -> List[SETrade]:
        buys = self.find_fulfilled_buys(txid=txid, limit=limit, offset=offset, indexes=indexes, **query)
        sells = self.find_fulfilled_sells(txid=txid, limit=limit, offset=offset, indexes=indexes, **query)
        return buys + sells
    
    def get_orderbook(self, symbol, direction='buy', user=None, limit=200, offset=0,
                      indexes: list = None, sort_by: str = 'price', sort_reverse=None, **query) -> List[SEOrder]:
        """
        Get a list of open Steem/Hive Engine orders for a given symbol, by default will display ``'buy'`` orders unless
        you set ``direction`` to ``'sell'``
        
        NOTE: By default, if ``direction`` is ``'buy'``, then the orders will be returned sorted by price - descending (highest first),
              and for ``sell`` - ascending (lowest first).
        
        **Example**::
            
            >>> st = SteemEngineToken()
            >>> o = st.get_orderbook('ENG', direction='sell')
            >>> o[0]
            <SEOrder account='someguy123' price='0.99' symbol='ENG' quantity='885.40249121'>
            >>> str(o[0].timestamp)
            '2019-07-26 10:46:18'
        
        **Sort by highest quantity first**::
            
            >>> st.get_orderbook('BEE', 'sell', sort_by='quantity', sort_reverse=True)
        
        **Sort by oldest order first**::
            
            >>> st.get_orderbook('BEE', 'sell', sort_by='timestamp')

        :param bool sort_reverse:   ``True`` to reverse sort ``sort_by`` (descending), ``False`` to NOT reverse (ascending). The default
                                    ``None`` will sort descending (reversed) when ``direction`` is ``buy``, and ascending for ``sell``
                                    (direction-based sorting only applies when ``sort_by`` is ``'price'``)
        
        :param str sort_by:         (Default: ``price``) The attribute of :class:`.SEOrder` to sort by.
        :param str symbol:          The symbol to get the open orders for
        :param int limit:           Amount of orders to retrieve
        :param int offset:          Offset selection by this many rows (for pagination)
        :param list indexes:        A list of dictionary indexes, e.g. ``[dict(descending=False, index='timestamp')]``
        :param str user:            If ``None`` , get all orders, otherwise only get orders by this user. Default: ``None``
        :param str direction:       The direction of orders to get, either ``buy`` or ``sell`` Default: ``buy``
        
        :raises NoResult:           Raised when ``None`` is returned by ``rpc.find``
        
        :return List[SEOrder] orders: A list of :py:class:`.SEOrder` objects
        """
        direction = direction.lower()
        if direction not in ['buy', 'sell']:
            raise AttributeError('get_orderbook direction must be either "buy" or "sell"')

        # indexes = [dict(descending=direction == 'sell', index='price')] if empty(indexes) else indexes
        indexes = [] if empty(indexes) else indexes

        q = dict(symbol=symbol, **query)
        if not empty(user):
            q['account'] = user
        res = self.rpc.find(
            contract='market',
            table=f'{direction.lower()}Book',
            query=q,
            indexes=indexes,
            limit=limit, offset=offset
        )
        if empty(res):
            raise NoResults("get_orderbook got empty (None) response from API...")
        orders = list(SEOrder.from_list(res, seng_ins=self))
        
        if len(indexes) == 0 and sort_by == 'price' and sort_reverse is None:
            sort_reverse = False if direction == 'sell' else True
        sort_reverse = False if sort_reverse is None else sort_reverse
        if not empty(sort_by):
            orders = sorted(orders, key=lambda p: getattr(p, sort_by), reverse=sort_reverse)
        
        return list(orders)
    
    def get_tickers(self, limit=1000, offset=0, indexes=None, **query) -> List[SETicker]:
        """
        Retrieve a list of market tickers from Hive/SteemEngine as a list of :class:`.SETicker` objects.
        
        **Example**::
        
            >>> st = SteemEngineToken()
            >>> tickers = st.get_tickers()
            [
                SETicker(
                    symbol='ENG', volume=Decimal('72.08939798'), lastPrice=Decimal('0.02100000'), lowestAsk=Decimal('0.05998799'),
                    highestBid=Decimal('0.02150500'), volumeExpiration=1593730710, lastDayPrice=Decimal('0.06196000'),
                    lastDayPriceExpiration=1593646239, priceChange=Decimal('-0.04096000'), priceChangePercent='-66.11%', _id=1
                ),
                ...
            ]
            >>> tickers[0].lastPrice
            Decimal('0.02100000')
        

        :param int limit:       Amount of tickers to retrieve
        :param int offset:      Offset selection by this many rows (for pagination)
        :param list indexes:    A list of dictionary indexes, e.g. ``[dict(descending=False, index='timestamp')]``
        :param query: Query parameters as keyword arguments, e.g. ``symbol="ENG"`` or ``_id=5``
        :return List[SETicker] tickers: Market tickers as a list of :class:`.SETicker` objects.
        """
        query = dict(query)
        
        res = self.rpc.find(
            contract='market',
            table=f'metrics',
            query=query,
            indexes=[] if empty(indexes, True, True) else indexes,
            limit=limit, offset=offset
        )

        if empty(res):
            raise NoResults("get_tickers got empty (None) response from API...")
        
        return list(SETicker.from_list(res, seng_ins=self))

    def get_ticker(self, symbol: str, **query) -> SETicker:
        """
        Retrieve a ticker for a single symbol as a :class:`.SETicker` object.
        
        **Example**::
        
            >>> st = SteemEngineToken(network='hive')
            >>> tk = st.get_ticker('BEE')
            >>> tk.lastPrice
            Decimal('0.79650010')
            >>> tk.lowestAsk
            Decimal('0.88000000')
        
        :param str symbol: The token symbol to retrieve the ticker for, e.g. ``ENG`` or ``SGTK``
        :param query: Additional query parameters as keyword arguments, e.g. ``_id=5``
        :return SETicker ticker: The ticker data as a :class:`.SETicker` object.
        """
        symbol = symbol.upper()
        tickers = self.get_tickers(symbol=symbol, **query)
        
        if empty(tickers, True, True):
            raise NoResults(f"No ticker found for symbol {symbol}")
        
        return tickers[0]

    def find_steem_tx(self, tx_data: dict, last_blocks=15) -> Optional[dict]:
        """
        Used internally to get the transaction ID after a Steem transaction has been broadcasted.

        See :py:meth:`.send_token` and :py:meth:`.issue_token` for how this is used.

        :param dict tx_data:      Transaction data returned by a beem broadcast operation, must include ``signatures``
        :param int last_blocks:   Amount of previous blocks to search for the transaction
        :return dict:             Transaction data from the blockchain, see below.
        
        **Return format:**

        .. code-block:: js

            {
                transaction_id, ref_block_num, ref_block_prefix, expiration,
                operations, extensions, signatures, block_num, transaction_num
            }
        
        :return None:             If the transaction wasn't found, ``None`` will be returned.
        """
        from beem.blockchain import Blockchain
        # Code taken/based from @holgern/beem blockchain.py
        chain = Blockchain(steem_instance=self.steem, mode='head')
        current_num = chain.get_current_block_num()
        for block in chain.blocks(start=current_num - last_blocks, stop=current_num + 5):
            for tx in block.transactions:
                if sorted(tx["signatures"]) == sorted(tx_data["signatures"]):
                    return tx
        return None

    def list_transactions(self, user, symbol=None, limit=100, offset=0) -> List[SETransaction]:
        """
        Get the Steem Engine transaction history for a given account

        **Example:**

            >>> for tx in SteemEngineToken().list_transactions('someguy123'):
            ...     print(tx.timestamp, tx.sender, 'sent', tx.quantity, tx.symbol, 'to', tx.to)
            2019-07-04T06:18:09.000Z market sent 100 SGTK to someguy123
            2019-07-04T01:01:15.000Z minnowsupport sent 0.924 PAL to someguy123
            2019-07-03T17:10:36.000Z someguy123 sent 1 BTSP to btsp
        
        :param str user: Account name to filter by
        :param str symbol: Symbol to filter by, e.g. ENG (optional)
        :param int limit: Return this many transactions (optional)
        :param int offset: Skip this many transactions (for pagination) (optional)
        :return List<SETransaction> txs: A list of :class:`.SETransaction` containing 
        
            block, txid, timestamp, symbol, sender, from_type, to, to_type, memo, quantity
        
        """
        symbol = None if empty(symbol) else symbol.upper()
        log.debug('Getting TX history for user %s, symbol %s, limit %s, offset %s', user, symbol, limit, offset)
        return list(SETransaction.from_list(self.history_rpc.get_history(account=user, symbol=symbol, limit=limit, offset=offset)))

    @se_cache(lambda self, symbol: f"pvx_seng:token:{symbol}", 60)
    def get_token(self, symbol) -> Optional[Token]:
        """
        Get the token object for an individual token.

        **Example:**

            >>> token = SteemEngineToken().get_token('SGTK'):
            >>> print(token.issuer, token.name)
            someguy123 SomeToken
        

        :param str symbol: Symbol of the token to lookup, such as 'ENG'
        :return Token token_data: An object containing data about the token (see below)
        
        A :class:`.Token` object can be accessed either via attributes ``token.issuer`` or as a dict.

        They contain the fields below:
        
        .. code-block:: js

            {
                issuer:str,
                symbol:str,
                name:str,
                metadata:str,
                precision:int,
                maxSupply: int,
                supply: int,
                circulatingSupply:int
            }
        
        :return None: If token not found, ``None`` is returned.
        """
        log.debug('Getting token object for symbol %s', symbol)
        tk = self.rpc.findone(
            contract='tokens',
            table='tokens',
            query=dict(symbol=symbol.upper())
        )
        return None if empty(tk) else Token.from_dict(tk)

    def send_token(self, symbol, from_acc, to_acc, amount: Decimal, memo="", find_tx=True) -> dict:
        """
        Sends a given ``amount`` of ``symbol`` from ``from_acc`` to ``to_acc`` with the memo ``memo``.
        You must have the active key for ``from_acc`` in your Beem wallet.

            >>> SteemEngineToken().send_token('SGTK', 'someguy123', 'privex', Decimal('1.234'), 'my memo')

        :param str symbol:     The symbol of the token you want to send
        :param str from_acc:   The account name you want to send from
        :param str to_acc:     The account name you want to send to
        :param Decimal amount: The amount of tokens to send. Will be casted to Decimal()
        :param memo:           The memo to send with. If not specified, will sent with blank memo
        :param find_tx:        If you don't care about info such as the TXID, and what block it's in, set to False.
        :raises ArithmeticError:  When the amount is lower than the lowest amount allowed by the token's precision
        :raises NotEnoughBalance: When ``from_acc`` does not have enough token balance to send this `amount`
        :raises AccountNotFound:  When either the ``from_acc`` or ``to_acc`` does not exist
        :raises TokenNotFound:    When the requested token `symbol` does not exist
        :raises beem.exceptions.MissingKeyError: No active key found for the ``from_acc`` in beem wallet

        :return dict: If TX was found on chain, more in-depth data including TXID, see below

        .. code-block:: js

            {
                transaction_id,
                ref_block_num,
                ref_block_prefix,
                expiration,
                operations,
                extensions,
                signatures,
                block_num,
                transaction_num
            }

        :return dict: If TX not found on chain, returns broadcast info:

        .. code-block:: js

            {
                expiration,
                ref_block_num,
                ref_block_prefix,
                operations,
                extensions,
                signatures
            }
        
        """
        t = self.get_token(symbol)
        if t is None:
            log.warning('Symbol %s was requested, but token does not exist', symbol)
            raise exceptions.TokenNotFound('Token {} does not exist'.format(t))
        amount = Decimal(amount)
        if amount < Decimal(pow(10, -t['precision'])):
            log.warning('Amount %s was passed, but is lower than precision for %s', amount, symbol)
            raise ArithmeticError('Amount {} is lower than token {}s precision of {} DP'
                                  .format(amount, symbol, t['precision']))

        balance = self.get_token_balance(from_acc, symbol)
        if amount > balance:
            log.warning('Attempted to send %s %s from %s, but balance is only %s', amount, symbol, from_acc, balance)
            raise exceptions.NotEnoughBalance('Account {} has a balance of {} but {} is needed.'.format(
                from_acc, balance, amount)
            )

        if not self.account_exists(from_acc):
            log.warning('Attempted to send from %s but account does not exist', from_acc)
            raise exceptions.AccountNotFound('Cannot send because the sender {} does not exist'.format(to_acc))
        if not self.account_exists(to_acc):
            log.warning('Attempted to send to %s but account does not exist', to_acc)
            raise exceptions.AccountNotFound('Cannot send because the receiver {} does not exist'.format(to_acc))
        log.debug('Sending %s %s from %s to %s with memo %s', amount, symbol, from_acc, to_acc, memo)
        custom = dict(
            contractName="tokens",
            contractAction="transfer",
            contractPayload=dict(
                symbol=symbol.upper(),
                to=to_acc,
                quantity=('{0:.' + str(t['precision']) + 'f}').format(amount),
                memo=memo
            )
        )
        
        # Make sure we're on the correct network before broadcasting
        self.verify_network()

        j = self.steem.custom_json(self.network_account, custom, [from_acc])
        if find_tx:    # Find the transaction on the blockchain to get TXID and other data from it.
            tx = self.find_steem_tx(j)
            return j if tx is None else tx
        return j

    def issue_token(self, symbol: str, to: str, amount: Decimal, find_tx=True) -> dict:
        """
        Issues a specified amount ``amount`` of ``symbol`` to the Steem account ``to``.

        Automatically queries Steem Engine API to find issuer of the token, and broadcast using Beem.

        You must have the active key of the token issuer account in your Beem wallet.

        **Example:** Issue ``1.234 SGTK`` to ``privex`` (automatically looks up the issuer and uses that account)

            >>> SteemEngineToken().issue_token('SGTK', 'privex', Decimal('1.234'))

        :param symbol:   The symbol of the token to issue, e.g. ENG
        :param to:       The Steem username to issue the tokens to
        :param amount:   The amount of tokens to issue, will be casted to a Decimal
        :param find_tx:  If you don't care about info such as the TXID, and what block it's in, set to False.
        :raises ArithmeticError:  When the amount is lower than the lowest amount allowed by the token's precision
        :raises TokenNotFound: When a token does not exist
        :raises AccountNotFound: When the ``to`` account doesn't exist on Steem
        :raises beem.exceptions.MissingKeyError: No active key found for the issuer in beem wallet

        :return dict: If TX was found on chain, more in-depth data including TXID, see below

        .. code-block:: js

            {
                transaction_id,
                ref_block_num,
                ref_block_prefix,
                expiration,
                operations,
                extensions,
                signatures,
                block_num,
                transaction_num
            }

        :return dict: If TX not found on chain, returns broadcast info:

        .. code-block:: js

            {
                expiration,
                ref_block_num,
                ref_block_prefix,
                operations,
                extensions,
                signatures
            }
        
        """
        t = self.get_token(symbol)
        amount = Decimal(amount)
        if t is None:
            raise exceptions.TokenNotFound('Token {} does not exist'.format(t))
        if amount < Decimal(pow(10, -t['precision'])):
            log.warning('Amount %s was passed, but is lower than precision for %s', amount, symbol)
            raise ArithmeticError('Amount {} is lower than token {}s precision of {} DP'
                                  .format(amount, symbol, t['precision']))
        if not self.account_exists(to):
            log.warning('Attempted to issue %s %s to %s but account does not exist', amount, symbol, to)
            raise exceptions.AccountNotFound('Cannot issue because the account {} does not exist'.format(to))
        log.debug('Issuing %s %s to %s', amount, symbol, to)

        custom = dict(
            contractName="tokens",
            contractAction="issue",
            contractPayload=dict(
                symbol=symbol.upper(),
                to=to,
                quantity=('{0:.' + str(t['precision']) + 'f}').format(amount)
            )
        )
        # Make sure we're on the correct network before broadcasting
        self.verify_network()
        j = self.steem.custom_json(self.network_account, custom, [t['issuer']])
        if find_tx:    # Find the transaction on the blockchain to get TXID and other data from it.
            tx = self.find_steem_tx(j)
            return j if tx is None else tx
        return j
    
    def place_order(self, user: str, action: str, symbol: str, quantity: AnyNum, price: AnyNum, find_tx=True) -> SEPlacedOrder:
        """
        Place an order on the Steem/Hive Engine market
        
        **Placing a 0.01 BEE sell order for 0.9 SWAP.HIVE per BEE from the account someguy123**::
        
            >>> from privex.steemengine import SteemEngineToken
            >>> s = SteemEngineToken(network='hive')
            >>> order = s.place_order('someguy123', 'sell', 'BEE', '0.01', '0.9')
            >>> order.user
            'someguy123'
            >>> order.events
            [
                SETransactionLogEvent(contract='tokens', event='transferToContract',
                    data=SEContractTransfer(sender='someguy123', to='market', symbol='BEE', quantity=Decimal('0.01000000'))),
                SETransactionLogEvent(contract='tokens', event='transferFromContract',
                    data=SEContractTransfer(sender='market', to='everything-4you', symbol='BEE', quantity=Decimal('0.01000000'))),
                SETransactionLogEvent(contract='tokens', event='transferFromContract',
                    data=SEContractTransfer(sender='market', to='someguy123', symbol='SWAP.HIVE', quantity=Decimal('0.00902100'))),
                SETransactionLogEvent(contract='market', event='orderClosed',
                    data={'account': 'someguy123', 'type': 'sell', 'txId': '2c5993eacf37c16e9a34ba7a35a0a5efa7fbc729'})
            ]
        
        
        :param str user: The user to place the order with.
        :param str action: Either ``'buy'`` or ``'sell'``
        :param str symbol: The symbol of the token you want to ``'buy'`` or ``'sell'``
        :param Decimal|int|float|str quantity: The amount of ``symbol`` to buy/sell
        :param Decimal|int|float|str price: The price in STEEMP/SWAP.HIVE per 1 ``symbol``
        :param bool find_tx: (Default: ``True``) Verify the transaction was successful by searching for it on the blockchain
        :return SEPlacedOrder result: The details of the order which was placed
        """
        # {"contractName": "market", "contractAction": "sell", "contractPayload": {"symbol": "BEE", "quantity": "1", "price": "0.7"}}
        action, symbol = action.lower(), symbol.upper()
        if action not in ['buy', 'sell']:
            raise AttributeError("place_order expects action to be either 'buy' or 'sell'")
        
        t = self.get_token(symbol)
        quantity, price = conv_dec(quantity), conv_dec(price)
        
        if t is None:
            raise exceptions.TokenNotFound('Token {} does not exist'.format(t))
        prec = t.precision
        if quantity < Decimal(pow(10, -prec)):
            log.warning('Quantity %s was passed, but is lower than precision for %s', quantity, symbol)
            raise ArithmeticError(f'Quantity {quantity} is lower than token {symbol}s precision of {t["precision"]} DP')
        if price < Decimal(pow(10, -prec)):
            log.warning('Price %s was passed, but is lower than precision for %s', price, symbol)
            raise ArithmeticError(f'Price {price} is lower than token {symbol}s precision of {t["precision"]} DP')
        
        quantity, price = dec_round(quantity, prec), dec_round(price, prec)
        if action == 'sell':
            # For sell orders, the user is using 'symbol' for the order, so we check 'symbol' balance
            bal = self.get_token_balance(user=user, symbol=symbol)
            if bal < quantity:
                raise exceptions.NotEnoughBalance(
                    f"User {user} tried to place an sell order for {quantity} {symbol} but only has {bal} {symbol}"
                )
        else:
            # For buy orders, the user is using the native coin of the network (e.g. STEEMP or SWAP.HIVE),
            # so we have to check their balance of self.native_coin, and sum the amount of native_coin that would be needed.
            bal = self.get_token_balance(user=user, symbol=self.native_coin)
            total_native = dec_round(quantity * price, self.native_token.precision)
            if bal < total_native:
                raise exceptions.NotEnoughBalance(
                    f"User {user} tried to place an buy order for {quantity} {symbol} ({total_native} {self.native_coin}) "
                    f"but only has {bal} {self.native_coin}"
                )
            
        custom = DictObject(
            contractName="market",
            contractAction=action,
            contractPayload=DictObject(
                symbol=symbol,
                quantity=round_str(quantity, prec),
                price=round_str(price, self.native_token.precision)
            )
        )
        ctpayload = custom.contractPayload
        res = SEPlacedOrder(
            symbol=symbol, quantity=ctpayload.quantity, price=ctpayload.price, user=user,
            direction=action, custom_tx=custom, _seng_instance=self
        )
        log.debug("Broadcasting custom_json from %s to %s - data: %s", user, self.network_account, custom)
        # Make sure we're on the correct network before broadcasting
        self.verify_network()
        j = self.steem.custom_json(self.network_account, custom, [user])
        res.broadcast_result = j
        
        if find_tx:  # Find the transaction on the blockchain to get TXID and other data from it.
            log.debug("Finding transaction: %s", j)
            tx = self.find_steem_tx(j)
            j = j if tx is None else tx
            res.network_transaction = tx
            res.txid = j.get('transaction_id')
            
        return res

    @se_cache(lambda self, txid: f"pvx_seng:tx_info:{txid}", 30)
    def get_transaction_info(self, txid: str) -> SETransactionInfo:
        return SETransactionInfo.from_dict(self.block_rpc.getTransactionInfo(txid=txid))

    def __iter__(self):
        yield ()


"""
+===================================================+
|                 © 2020 Privex Inc.                |
|               https://www.privex.io               |
+===================================================+
|                                                   |
|        Python Steem Engine library                |
|        License: X11/MIT                           |
|                                                   |
|        Core Developer(s):                         |
|                                                   |
|          (+)  Chris (@someguy123) [Privex]        |
|                                                   |
+===================================================+

Python SteemEngine - A small library for querying and interacting with the SteemEngine network (https://steem-engine.com)
Copyright (c) 2020    Privex Inc. ( https://www.privex.io )

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation 
files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, 
modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE 
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS 
OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Except as contained in this notice, the name(s) of the above copyright holders shall not be used in advertising or 
otherwise to promote the sale, use or other dealings in this Software without prior written authorization.
"""
