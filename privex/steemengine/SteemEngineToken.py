import logging
from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Union, List
from privex.jsonrpc import SteemEngineRPC
from privex.steemengine import exceptions
from privex.steemengine.SteemEngineHistory import SteemEngineHistory
from privex.steemengine.objects import SEBalance, SETransaction, Token
from privex.helpers import empty

log = logging.getLogger(__name__)
getcontext().rounding = ROUND_DOWN


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

    @property
    def steem(self):
        """
        When a method calls ``self.steem`` , this property will first try to return :py:attr:`._steem`
        if it was previously called. Otherwise, it will automatically initialise :py:attr:`._steem`
        with an instance of :class:`beem.steem.Steem` and then return it.
        
        This ensures that Beem isn't initialised unless it's actually needed, preventing un-necessary
        slowdowns of the application using this library due to Beem attempting to find a working RPC node.

        :return beem.steem.Steem steem: An instance of :class:`beem.steem.Steem`
        """
        if not self._steem:
            from beem.instance import shared_steem_instance
            self._steem = shared_steem_instance()
        return self._steem

    def __init__(self, network_account='ssc-mainnet1', history_conf: dict = None, **rpc_args):
        """
        Initialises the class with various configuration options. All parameters are optional.

        Pass a dict in ``history_conf`` to override the SteemEngine history node used
        Pass extra kwargs such as ``hostname='api.example.com'`` ot override the SteemEngine RPC node used.

        :param network_account: The Steem account that operates the SteemEngine network, e.g. ssc-mainnet1 for the
                                Steem Smart Contracts Main Network
        :param history_conf:    A dictionary containing kwargs to pass to :py:class:`.SteemEngineHistory` constructor
        :param rpc_args:        Any additional kwargs will be passed to the :py:class:`privex.jsonrpc.SteemEngineRPC` constructor
        """
        self.rpc = SteemEngineRPC(**rpc_args)
        self.network_account = network_account
        history_conf = {} if history_conf is None else history_conf
        self.history_rpc = SteemEngineHistory(**history_conf)
        log.debug('Initialized SteemEngineToken with args: %s %s %s', network_account, history_conf, rpc_args)

    @staticmethod
    def custom_beem(node: Union[str, list] = "", *args, **kwargs):
        """
        Override the beem Steem instance (:py:attr:`._steem`) used by this class.

        Useful if you'd rather not configure beem's shared instance for some reason.

        Example usage:

        >>> from privex.steemengine import SteemEngineToken
        >>> SteemEngineToken.custom_beem(node=['https://steemd.privex.io', 'https://api.steemit.com'])

        """
        from beem.steem import Steem
        SteemEngineToken._steem = Steem(node, *args, **kwargs)
        return SteemEngineToken._steem

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
        )))

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
            if bal['symbol'] == symbol.upper():
                log.debug('Found token balance matching %s, returning %s', symbol, bal['balance'])
                return Decimal(bal['balance'])
        log.debug('Did not find token balance matching %s, returning 0', symbol)
        return Decimal(0)

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
        log.debug('Checking if user %s exists', user)
        return len(self.steem.rpc.get_account(user)) > 0

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

    def find_steem_tx(self, tx_data: dict, last_blocks=15) -> dict:
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

    def get_token(self, symbol) -> Token:
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
        return None if empty(tk) else Token(**tk)

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
        j = self.steem.custom_json(self.network_account, custom, [t['issuer']])
        if find_tx:    # Find the transaction on the blockchain to get TXID and other data from it.
            tx = self.find_steem_tx(j)
            return j if tx is None else tx
        return j



"""
+===================================================+
|                 © 2019 Privex Inc.                |
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
Copyright (c) 2019    Privex Inc. ( https://www.privex.io )

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
