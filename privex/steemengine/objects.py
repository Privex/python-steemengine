"""
This file contains various classes used to represent different dictionaries returned from the Steem/HiveEngine APIs,
making the data easier to handle::
 
 * IDE attribute assistance (aka IntelliSense),
 * converting certain attributes into more sensible types, e.g. from :class:`.str` / :class:`.float` into :class:`.Decimal`
 * new properties / methods to automate certain data queries and ease conversion to/from different types.


"""
import json
import logging
from dataclasses import field, dataclass
from datetime import datetime
from typing import Union, List, Generator, Type, Iterable, Optional
from decimal import Decimal
from privex.helpers import empty, construct_dict, T, empty_if, DictObject, convert_datetime, DictDataClass

from privex.steemengine.exceptions import NoSteemEngineInstance, SteemEngineException

__all__ = [
    'AnyNum', 'conv_dec', 'ObjBase', 'TokenMetadata', 'Token', 'SETransaction', 'SEPlacedOrder', 'SEBalance', 'SETrade',
    'SEOrder', 'SEContractTransfer', 'SETransactionLogEvent', 'SETransactionInfo'
]

log = logging.getLogger(__name__)
AnyNum = Union[Decimal, float, str]


def conv_dec(number: AnyNum) -> Optional[Decimal]:
    """Convert an object into a :class:`.Decimal`, but only if it isn't already a :class:`.Decimal`"""
    if empty(number):
        return None
    return number if isinstance(number, Decimal) else Decimal(str(number))


class ObjBase:
    """
    A base class to be extended by data storage classes, allowing their attributes to be
    accessed as if the class was a dict/list.

    Also allows the class to be converted into a dict/list if raw_data is filled, like so: ``dict(SomeClass())``
    """

    def __init__(self, raw_data: Union[list, tuple, dict] = None, *args, **kwargs):
        self.raw_data = {} if not raw_data else raw_data  # type: Union[list, tuple, dict]
        super(ObjBase, self).__init__(raw_data=raw_data, *args, **kwargs)

    def __iter__(self):
        r = self.raw_data
        itr = r.items() if type(r) is dict else enumerate(r)
        for k, v in itr:
            yield (k, v,)

    def __getitem__(self, key):
        """
        When the instance is accessed like a dict, try returning the matching attribute.
        If the attribute doesn't exist, or the key is an integer, try and pull it from raw_data
        """
        if type(key) is int: return self.raw_data[key]
        if hasattr(self, key): return getattr(self, key)
        if key in self.raw_data: return self.raw_data[key]
        raise KeyError(key)

    @classmethod
    def from_list(cls, obj_list: List[dict]):
        """
        Converts a ``list`` of ``dict`` 's into a ``Generator[cls]`` of instances of the class you're calling this from.

        **Example:**

            >>> _balances = [dict(account='someguy123', symbol='SGTK', balance='1.234')]
            >>> balances = list(SEBalance.from_list(_balances))
            >>> type(balances[0])
            <class 'privex.steemengine.objects.SEBalance'>
            >>> balances[0].account
            'someguy123'

        """
        for tx in obj_list:
            yield cls(**tx)

    @classmethod
    def contruct_self(cls: Type[T], *args, **kwargs) -> T:
        return construct_dict(cls, kwargs=kwargs, args=args)

    def __repr__(self):
        return self.__str__()


# noinspection PyUnresolvedReferences
class SteemEngineInstanceInject(DictDataClass):
    _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken"

    class DictConfig:
        dict_exclude = ['_seng_instance']
    
    def set_seng_instance(self, seng_ins: "privex.steemengine.SteemEngineToken.SteemEngineToken"):
        self._seng_instance = seng_ins
    
    @classmethod
    def from_dict(cls: Type[dataclass], obj, seng_ins=None):
        if seng_ins:
            obj = dict(obj)
            obj['_seng_instance'] = seng_ins
        # if seng_ins:
        # s._seng_instance = seng_ins
        return super().from_dict(obj)
    
    @classmethod
    def from_list(cls: Type[T], obj_list: Iterable[dict], seng_ins=None) -> Generator[T, None, None]:
        for o in obj_list:
            yield cls.from_dict(o, seng_ins=seng_ins)


@dataclass
class TokenMetadata(DictDataClass):
    """
    Represents the ``metadata`` field on a token object on SteemEngine
    """
    url: str = ''
    """The official website for the token"""
    icon: str = ''
    """A full URL to the icon for the token"""
    desc: str = ''
    """A long description explaining the token"""
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    

@dataclass
class Token(DictDataClass):
    """
    Represents a token's information on SteemEngine
    """
    symbol: str
    """The short symbol for the token, e.g. ``ENG``"""
    name: str = ''
    """The full name for the token, e.g. ``Steem Engine Token``"""
    issuer: str = ''
    """The username of the issuer/owner of the token on SteemEngine, e.g. ``someguy123``"""
    metadata: Union[TokenMetadata, str, dict, list] = None
    """Metadata for the token, including the ``url``, ``icon`` and ``desc`` (description)"""
    precision: int = 0
    """The precision / amount of decimal places the token uses"""
    max_supply: Decimal = field(default_factory=Decimal)
    """The maximum amount of tokens that can ever be printed"""
    circulating_supply: Decimal = field(default_factory=Decimal)
    """Amount of tokens that are circulating, i.e. have not been burned"""
    supply: Decimal = field(default_factory=Decimal)
    """Amount of tokens in existence"""
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""

    def __post_init__(self):
        kwargs = DictObject(self.raw_data)
        _maxs, _circ = self.max_supply, self.circulating_supply

        self.max_supply = conv_dec(kwargs.get('maxSupply', self.max_supply))
        self.max_supply = conv_dec(kwargs.get('max_supply', self.max_supply))

        self.circulating_supply = conv_dec(kwargs.get('circulatingSupply', self.circulating_supply))
        self.circulating_supply = conv_dec(kwargs.get('circulating_supply', self.circulating_supply))

        self.supply = Decimal(kwargs.get('supply', self.supply))
        
        meta = self.metadata
        try:
            meta = {} if empty(meta, itr=True) else (json.loads(meta) if isinstance(meta, str) else meta)
        except json.JSONDecodeError:
            log.warning("Failed to decode Token metadata as JSON: %s", meta)
            meta = {}
        self.metadata = TokenMetadata.from_dict(meta)


@dataclass
class SETransaction(DictDataClass):
    """
    Represents a standard transaction from account history on SteemEngine
    """
    block: int = 0
    """The block number of the transaction"""
    txid: str = None
    """The unique transaction ID of the transaction, as a string"""
    symbol: str = None
    """The short symbol for the token being sent/received, e.g. ``ENG``"""
    sender: str = None
    """The Hive/Steem username that sent/issued the tokens"""
    from_type: str = None
    """Either ``user`` (normal send/receive TX) or ``contract`` (issues/stakes etc.)"""
    to: str = None
    """The Hive/Steem username that received the tokens"""
    to_type: str = None
    """Either ``user`` (normal send/receive TX) or ``contract`` (issues/stakes etc.)"""
    memo: str = None
    """A short message describing the purpose of the transaction"""
    timestamp: str = None
    """The time the transaction occured, as a UTC-formatted string ``2019-07-04T06:18:09.000Z``"""
    quantity: Decimal = field(default_factory=Decimal)
    """The amount of tokens that were sent/issued etc."""
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    def __post_init__(self):
        self.quantity = conv_dec(self.quantity)
        self.sender = self.raw_data.get('from', self.sender)


@dataclass
class SEPlacedOrder(SteemEngineInstanceInject):
    symbol: str
    """The token symbol being bought/sold"""
    quantity: Decimal
    """Amount of ``symbol`` bought / sold"""
    price: Decimal
    """Amount of STEEMP/SWAP.HIVE per 1 ``symbol``"""
    direction: str
    """Either ``buy`` or ``sell``"""
    user: str
    """The account username which placed the order"""
    custom_tx: Optional[dict] = None
    """The dictionary payload which was used for the custom_json transaction"""
    txid: str = None
    """The Steem/Hive TXID for the transaction"""
    broadcast_result: Optional[dict] = None
    """Contains the result from Beem after broadcasting"""
    network_transaction: Optional[dict] = None
    """Contains the transaction as found on the Steem/Hive blockchain"""
    
    # noinspection PyUnresolvedReferences
    _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken" = field(default=None, repr=False)
    """SteemEngineToken Instance"""
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    def get_transaction(self) -> Optional["SETransactionInfo"]:
        """Lookup the transaction ID :attr:`.txid` and return a :class:`.SETransactionInfo` object."""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return None if empty(self.txid) else self._seng_instance.get_transaction_info(self.txid)
    
    def get_trades(self, **find_args) -> Optional[List["SETrade"]]:
        """Returns the opposing orders which fulfilled this placed order as a list of :class:`.SETrade`"""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        if empty(self.txid): return None
        if self.direction == 'sell': return self._seng_instance.find_fulfilled_sells(txid=self.txid, **find_args)
        if self.direction == 'buy': return self._seng_instance.find_fulfilled_buys(txid=self.txid, **find_args)
        raise SteemEngineException(f"Direction was neither sell nor buy - direction was: {self.direction}")
    
    @property
    def transaction(self) -> Optional["SETransactionInfo"]:
        return self.get_transaction()
    
    @property
    def trades(self) -> Optional[List["SETrade"]]:
        """The opposing orders which fulfilled this placed order as a list of :class:`.SETrade`"""
        return self.get_trades()
    
    @property
    def logs(self):
        return self.transaction.logs
    
    @property
    def events(self) -> List["SETransactionLogEvent"]:
        return self.transaction.events
    
    def __post_init__(self):
        self.quantity = conv_dec(self.quantity)
        self.price = conv_dec(self.price)
    

@dataclass
class SEBalance(SteemEngineInstanceInject):
    """
    Represents an account token balance on SteemEngine
    """
    account: str
    """The Hive/Steem username whom this balance belongs to"""
    symbol: str
    """The short symbol for the token held, e.g. ``ENG``"""
    balance: Union[Decimal, float, str]
    """The amount of :attr:`.symbol` that :attr:`.account` holds"""
    
    # noinspection PyUnresolvedReferences
    _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken" = field(default=None, repr=False)
    """SteemEngineToken Instance"""
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    _token = None
    
    @property
    def token(self) -> Optional[Token]:
        """Returns a :class:`.Token` instance for the :attr:`.symbol` on SteemEngine"""
        if not self._token:
            if not self._seng_instance:
                raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
            self._token = self._seng_instance.get_token(self.symbol)
        return self._token

    def __post_init__(self):
        self.balance = conv_dec(self.balance)


@dataclass
class SETrade(SteemEngineInstanceInject):
    """
    Represents a past trade on the SE market.
    """

    symbol: str
    """The token symbol this order is buying/selling"""
    quantity: AnyNum
    """The amount of tokens being bought/sold"""
    price: AnyNum
    """The price per token ( :py:attr:`.symbol` ) in STEEMP or SWAP.HIVE"""
    timestamp: Union[datetime, str, int]
    """The date/time which the order was placed"""
    volume: AnyNum = field(default_factory=Decimal)
    direction: str = None
    """The type of order as a string, either ``'buy'`` or ``'sell'``"""
    buyer: str = None
    seller: str = None
    
    buyTxId: str = None
    sellTxId: str = None

    # noinspection PyUnresolvedReferences
    _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken" = field(default=None, repr=False)
    """SteemEngineToken Instance"""
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    @property
    def type(self):
        """Alias for ``direction`` - either ``'buy'`` or ``'sell'``"""
        return self.direction
    
    @type.setter
    def type(self, value):
        self.direction = value

    def get_sell_transaction(self) -> Optional["SETransactionInfo"]:
        """Lookup the transaction ID :attr:`.sellTxId` and return a :class:`.SETransactionInfo` object."""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return None if empty(self.sellTxId) else self._seng_instance.get_transaction_info(self.sellTxId)

    def get_buy_transaction(self) -> Optional["SETransactionInfo"]:
        """Lookup the transaction ID :attr:`.buyTxId` and return a :class:`.SETransactionInfo` object."""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return None if empty(self.buyTxId) else self._seng_instance.get_transaction_info(self.buyTxId)
    
    def __post_init__(self):
        if not self.direction and 'type' in self.raw_data:
            self.direction = self.raw_data.get('type')
        if self.direction not in ['buy', 'sell']:
            raise AttributeError('SETrade.type must be either buy or sell')
        self.timestamp = convert_datetime(self.timestamp)
        self.quantity, self.price, self.volume = conv_dec(self.quantity), conv_dec(self.price), conv_dec(self.volume)


@dataclass
class SEOrder(SteemEngineInstanceInject):
    """
    Represents an open order on the SE market.
    """

    symbol: str
    """The token symbol this order is buying/selling"""
    quantity: AnyNum
    """The amount of tokens being bought/sold"""
    price: AnyNum
    """The price per token ( :py:attr:`.symbol` ) in STEEMP or SWAP.HIVE"""
    timestamp: Union[datetime, str, int]
    """The date/time which the order was placed"""
    account: str
    """The username of the person who placed the order"""
    expiration: Union[datetime, str, int]
    txid: str = None
    """The transaction ID of the order"""
    tokens_locked: AnyNum = field(default_factory=Decimal)
    """The amount of STEEMP or SWAP.HIVE locked into the order"""
    
    # noinspection PyUnresolvedReferences
    _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken" = field(default=None, repr=False)
    """SteemEngineToken Instance"""
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""

    @property
    def tokensLocked(self):
        return self.tokens_locked
    
    @tokensLocked.setter
    def tokensLocked(self, value):
        self.tokens_locked = value

    def get_transaction(self) -> Optional["SETransactionInfo"]:
        """Lookup the transaction ID :attr:`.txid` and return a :class:`.SETransactionInfo` object."""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return None if empty(self.txid) else self._seng_instance.get_transaction_info(self.txid)
    
    def __post_init__(self):
        if not self.tokens_locked and 'tokensLocked' in self.raw_data:
            self.tokens_locked = self.raw_data.tokensLocked
        self.tokens_locked = conv_dec(self.tokens_locked)
        self.quantity, self.price = conv_dec(self.quantity), conv_dec(self.price)
        self.timestamp = convert_datetime(self.timestamp)
        self.expiration = convert_datetime(self.expiration)
        self.symbol = self.symbol.upper()
        self.account = str(self.account).lower()
        self.txid = self.raw_data.get('txId', self.txid) if not self.txid else str(self.txid)


@dataclass
class SEContractTransfer(DictDataClass):
    """
    Represents the data for a ``transferToContract`` / ``transferFromContract`` :class:`.SETransactionLogEvent`
    """
    sender: str = None
    to: str = None
    symbol: str = None
    quantity: AnyNum = None
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    def __post_init__(self):
        self.sender = empty_if(self.sender, self.raw_data.get('from'))
        self.quantity = None if empty(self.quantity) else conv_dec(self.quantity)


@dataclass
class SETransactionLogEvent(DictDataClass):
    """
    Represents events contained within the list :class:`.SETransactionInfo` ``.logs['events']``
    """
    contract: str = None
    event: str = None
    data: Union[str, int, DictObject, SEContractTransfer, dict, list] = field(default_factory=DictObject)
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    def __post_init__(self):
        if self.event in ['transferToContract', 'transferFromContract'] and isinstance(self.data, (dict, DictObject)):
            self.data = SEContractTransfer.from_dict(self.data)


@dataclass
class SETransactionInfo(DictDataClass):
    """
    Represents transaction data from ``/rpc/blockchain`` JSON-RPC method ``getTransactionInfo``
    """

    blockNumber: int = 0
    refHiveBlockNumber: int = 0
    transactionId: str = None
    contract: str = None
    sender: str = None
    action: str = None
    payload: Union[str, int, DictObject, dict, list] = field(default_factory=DictObject)
    executedCodeHash: str = None
    hash: str = None
    databaseHash: str = None
    logs: Union[str, int, DictObject, dict, list] = field(default_factory=DictObject)
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""
    
    @property
    def txid(self): return self.transactionId
    
    @txid.setter
    def txid(self, value): self.transactionId = value

    @property
    def block(self):
        return self.blockNumber

    @block.setter
    def block(self, value):
        self.blockNumber = value
    
    @property
    def events(self) -> List[SETransactionLogEvent]:
        if isinstance(self.logs, (dict, DictObject)):
            return list(SETransactionLogEvent.from_list(self.logs.get('events', [])))
        return []
    
    def __post_init__(self):
        if isinstance(self.logs, str):
            try:
                self.logs = json.loads(self.logs)
            except json.JSONDecodeError as e:
                log.warning("Failed to JSON decode SETransactionInfo.logs: %s %s", type(e), str(e))
                log.debug("Content of logs: %s", self.logs)
        if isinstance(self.payload, str):
            try:
                self.payload = json.loads(self.payload)
            except json.JSONDecodeError as e:
                log.warning("Failed to JSON decode SETransactionInfo.payload: %s %s", type(e), str(e))
                log.debug("Content of payload: %s", self.payload)


@dataclass
class SETicker(SteemEngineInstanceInject):
    symbol: str
    volume: Decimal
    lastPrice: Decimal
    lowestAsk: Decimal
    highestBid: Decimal
    volumeExpiration: int = 0
    lastDayPrice: Decimal = field(default_factory=Decimal)
    lastDayPriceExpiration: int = 0
    priceChange: Decimal = field(default_factory=Decimal)
    priceChangePercent: str = "0%"
    _id: int = 0
    
    raw_data: Union[dict, DictObject] = field(default_factory=DictObject, repr=False)
    """The raw, unmodified data that was passed as kwargs, as a dictionary"""

    # _seng_instance: "privex.steemengine.SteemEngineToken.SteemEngineToken" = field(default=None, repr=False)
    """SteemEngineToken Instance"""
    
    def __post_init__(self):
        self.volume = conv_dec(self.volume)
        self.lastPrice = conv_dec(self.lastPrice)
        self.lowestAsk = conv_dec(self.lowestAsk)
        self.highestBid = conv_dec(self.highestBid)
        self.lastDayPrice = conv_dec(self.lastDayPrice)
        if empty(self.priceChange, zero=True):
            if 'priceChangeSteem' in self.raw_data:
                self.priceChange = conv_dec(self.raw_data['priceChangeSteem'])
            elif 'priceChangeHive' in self.raw_data:
                self.priceChange = conv_dec(self.raw_data['priceChangeHive'])

    @property
    def token(self) -> Optional[Token]:
        """Returns a :class:`.Token` instance for the :attr:`.symbol` on SteemEngine"""
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return self._seng_instance.get_token(self.symbol)
    
    @property
    def order_book_buy(self):
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return self._seng_instance.get_orderbook(self.symbol, direction='buy')

    @property
    def order_book_sell(self):
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return self._seng_instance.get_orderbook(self.symbol, direction='sell')

    @property
    def order_history(self):
        if not self._seng_instance:
            raise NoSteemEngineInstance(f"{self.__class__.__name__}._seng_instance SteemEngine instance isn't initialised.")
        return self._seng_instance.order_history(self.symbol, limit=100)

