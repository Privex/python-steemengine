import json
from datetime import datetime
from typing import Union, List, Generator
from decimal import Decimal
from privex.helpers import empty

AnyNum = Union[Decimal, float, str]


class ObjBase:
    """
    A base class to be extended by data storage classes, allowing their attributes to be
    accessed as if the class was a dict/list.
    
    Also allows the class to be converted into a dict/list if raw_data is filled, like so: ``dict(SomeClass())``
    """

    def __init__(self, raw_data: Union[list, tuple, dict] = None, *args, **kwargs):
        self.raw_data = {} if not raw_data else raw_data  # type: Union[list, tuple, dict]
        super(ObjBase, self).__init__(raw_data, *args, **kwargs)
    
    def __iter__(self):
        r = self.raw_data
        if type(r) is dict:
            for k, v in r.items(): yield (k, v,)
            return
        for k, v in enumerate(r): yield (k, v,)

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

    def __repr__(self):
        return self.__str__()


class TokenMetadata(ObjBase):
    """
    Represents the ``metadata`` field on a token object on SteemEngine
    
    :ivar str url: The official website for the token
    :ivar str icon: A full URL to the icon for the token
    :ivar str desc: A long description explaining the token
    """
    def __init__(self, url="", icon="", desc="", **kwargs):
        self.url, self.icon, self.desc = url, icon, desc
        self.raw_data = {**kwargs, **dict(url=url,icon=icon,desc=desc)}


class Token(ObjBase):
    """
    Represents a token's information on SteemEngine

    :ivar str symbol: The short symbol for the token, e.g. ``ENG``
    :ivar str name: The full name for the token, e.g. ``Steem Engine Token``
    :ivar str issuer: The username of the issuer/owner of the token on SteemEngine, e.g. ``someguy123``
    :ivar TokenMetadata metadata: Metadata for the token, including the ``url``, ``icon`` and ``desc`` (description)
    :ivar int precision: The precision / amount of decimal places the token uses
    :ivar Decimal max_supply: The maximum amount of tokens that can ever be printed
    :ivar Decimal circulating_supply: Amount of tokens that are circulating, i.e. have not been burned
    :ivar Decimal supply: Amount of tokens in existance

    """

    def __init__(self, symbol, name="", issuer="", metadata: Union[str, dict] = None, **kwargs):
        self.raw_data = {**kwargs, **dict(symbol=symbol,issuer=issuer,name=name, metadata=metadata)}
        self.issuer, self.name, self.symbol = issuer, name, symbol   # type: str
        meta = metadata
        meta = {} if empty(meta, itr=True) else (json.loads(meta) if type(meta) is str else meta)
        self.metadata = TokenMetadata(**meta)   # type: TokenMetadata
        self.precision = int(kwargs.get('precision', 0))    # type: int

        _circ = _maxs = Decimal(0)
        if 'maxSupply' in kwargs: _maxs = Decimal(kwargs['maxSupply'])
        if 'max_supply' in kwargs: _maxs = Decimal(kwargs['max_supply'])
        self.max_supply = self.maxSupply = _maxs   # type: Decimal

        if 'circulatingSupply' in kwargs: _circ = Decimal(kwargs['circulatingSupply'])
        if 'circulating_supply' in kwargs: _circ = Decimal(kwargs['circulating_supply'])
        self.circulating_supply = self.circulatingSupply = _circ    # type: Decimal

        self.supply = Decimal(kwargs.get('supply', '0'))     # type: Decimal
    
    def __str__(self):
        return f"<Token symbol='{self.symbol}' name='{self.name}' issuer='{self.issuer}'>"


class SETransaction(ObjBase):
    """
    Represents a standard transaction from account history on SteemEngine
    
    :ivar int block: The block number of the transaction
    :ivar str timestamp: The time the transaction occured, as a UTC-formatted string ``2019-07-04T06:18:09.000Z``
    :ivar str txid: The unique transaction ID of the transaction, as a string
    :ivar str symbol: The short symbol for the token being sent/received, e.g. ``ENG``
    :ivar str sender: The Steem username that sent/issued the tokens
    :ivar str to: The Steem username that received the tokens
    :ivar str to_type: Either ``user`` (normal send/receive TX) or ``contract`` (issues/stakes etc.)
    :ivar str from_type: Either ``user`` (normal send/receive TX) or ``contract`` (issues/stakes etc.)
    :ivar str memo: A short message describing the purpose of the transaction
    :ivar Decimal quantity: The amount of tokens that were sent/issued etc.

    """

    def __init__(self, **kwargs):
        # block, txid, timestamp, symbol, from, from_type, to, to_type, memo, quantity
        self.raw_data = kwargs
        k = kwargs.get
        self.block = int(k('block', 0))   # type: int
        self.txid, self.symbol, self.sender = k('txid'), k('symbol'), k('from')  # type: str
        self.from_type, self.to, self.to_type = k('from_type'), k('to'), k('to_type')  # type: str
        self.memo, self.timestamp = k('memo'), k('timestamp')   # type: str
        self.quantity = Decimal(k('quantity', '0'))   # type: Decimal
    
    def __str__(self):
        return f"<SETransaction symbol='{self.symbol}' sender='{self.sender}' to='{self.to}' quantity='{self.quantity}'>"
    

class SEBalance(ObjBase):
    """
    Represents an account token balance on SteemEngine
    
    :ivar str account: The Steem username whom this balance belongs to
    :ivar str symbol: The short symbol for the token held, e.g. ``ENG``
    :ivar Decimal balance: The amount of ``symbol`` that ``account`` holds.
    """
    def __init__(self, account: str, symbol: str, balance: Union[Decimal, float, str], **kwargs):
        self.raw_data = {**kwargs, **dict(account=account, symbol=symbol, balance=balance)}
        self.account, self.symbol = account, symbol   # type: str
        self.balance = Decimal(balance)    # type: Decimal
    
    def __str__(self):
        return f"<SEBalance account='{self.account}' symbol='{self.symbol}' balance='{self.balance}'>"
        

class SETrade(ObjBase):
    """
    Represents a past trade on the SE market.

    :ivar str symbol: The symbol this order is for
    :ivar Decimal quantity: The amount of tokens being bought/sold
    :ivar Decimal price: The price per token ( :py:attr:`.symbol` ) in STEEM
    :ivar datetime timestamp: The date/time which the order was placed
    :ivar str direction: The type of order as a string, either ``'buy'`` or ``'sell'``
    :ivar str type: Alias for ``direction`` - either ``'buy'`` or ``'sell'``
    """

    def __init__(self, symbol: str, quantity: AnyNum, price: AnyNum, timestamp: int, volume: AnyNum,
                 direction: str = None, **kwargs):

        direction = kwargs.get('type') if not direction else direction
        self.raw_data = {
            **kwargs,
            **dict(symbol=symbol, quantity=quantity, price=price, timestamp=timestamp,
                   volume=volume, direction=direction)
        }
        self.volume = Decimal(volume)
        self.price = Decimal(price)
        self.quantity = Decimal(quantity)
        self.timestamp = datetime.utcfromtimestamp(int(timestamp))
        self.symbol = symbol.upper()
        self.direction = self.type = direction.lower()
        if self.type not in ['buy', 'sell']:
            raise AttributeError('SEOrder.type must be either buy or sell')

    def __str__(self):
        return f"<SETrade type='{self.type}' price='{self.price}' symbol='{self.symbol}' quantity='{self.quantity}'>"


class SEOrder(ObjBase):
    """
    Represents an open order on the SE market.

    :ivar str symbol: The symbol this order is for
    :ivar Decimal quantity: The amount of tokens being bought/sold
    :ivar Decimal price: The price per token ( :py:attr:`.symbol` ) in STEEM
    :ivar Decimal tokens_locked: The amount of STEEM locked into the order
    :ivar Decimal tokensLocked: Alias of ``tokens_locked``
    :ivar datetime timestamp: The date/time which the order was placed
    :ivar datetime expiration: ?????
    :ivar str account: The username of the person who placed the order
    :ivar str txid: The transaction ID of the order
    """
    def __init__(self, symbol: str, quantity: AnyNum, price: AnyNum, timestamp: int, account: str, expiration: int,
                 txid: str = None, tokens_locked: AnyNum = None, **kwargs):
        txid = kwargs.get('txId') if not txid else txid
        tokens_locked = kwargs.get('tokensLocked') if not tokens_locked else tokens_locked
        self.raw_data = {
            **kwargs,
            **dict(symbol=symbol, quantity=quantity, price=price, timestamp=timestamp, account=account,
                   tokens_locked=tokens_locked, expiration=expiration, txid=txid)
        }
        self.tokens_locked = self.tokensLocked = None if not tokens_locked else Decimal(tokens_locked)
        self.price = Decimal(price)
        self.quantity = Decimal(quantity)
        self.timestamp = datetime.utcfromtimestamp(int(timestamp))
        self.expiration = datetime.utcfromtimestamp(int(expiration))
        self.symbol = symbol.upper()
        self.account = str(account).lower()
        self.txid = str(txid)

        pass

    def __str__(self):
        return f"<SEOrder account='{self.account}' price='{self.price}' symbol='{self.symbol}' quantity='{self.quantity}'>"

