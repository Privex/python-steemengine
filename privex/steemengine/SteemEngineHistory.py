import logging

import requests

"""
Copyright::

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

log = logging.getLogger(__name__)


class SteemEngineHistory:
    """
    Provides simple methods for querying a SteemEngine history node

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


    Basic Usage:

        >>> h = SteemEngineHistory()
        >>> for tx in h.get_history('someguy123'):
        >>>     print(tx['timestamp'], tx['symbol'], tx['quantity'], tx['memo'])

    """
    DEF_HOST = 'api.steem-engine.net'
    DEF_URL = 'accounts/history'
    # Using a python-requests session will help to encourage connection re-use, e.g. HTTP Keep-alive
    # Since this is a static attribute, it will be shared across ALL instances of the class.
    req = requests.Session()

    def __init__(self, hostname=DEF_HOST, port: int = 443, username=None, password=None, ssl=True, timeout=120,
                 url: str = DEF_URL):
        """
        Configure the remote SteemEngine history server settings. All parameters are optional.

        :param hostname: The hostname or IP address of the history server
        :param port:     The HTTP port to connect to
        :param username: If the RPC server needs a username, specify it here
        :param password: If the RPC server needs a password, specify it here (username must also be set)
        :param ssl:      If set to True, will use https for requests. Default is True - use SSL
        :param timeout:  If the server stops sending us data for this many seconds, abort and throw an exception
        :param url:      The URL to query, e.g. accounts/history (starting /'s will automatically be removed)
        """
        self.timeout = timeout
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.ssl = ssl
        self.endpoint = url

    @property
    def url(self):
        url = self.endpoint
        proto = 'https' if self.ssl else 'http'
        host = '{}:{}'.format(self.hostname, self.port)
        if self.username is not None:
            host = '{}:{}@{}:{}'.format(self.username, self.password, self.hostname, self.port)
        url = url[1:] if url[0] == '/' else url  # Strip starting / of URL

        return "{}://{}/{}".format(proto, host, url)

    def get_history(self, account, symbol=None, limit=100, offset=0, h_type='user') -> list:
        """
        Get the Steem Engine transaction history for a given account
        :param account: Account name to filter by
        :param symbol: Symbol to filter by, e.g. ENG
        :param limit: Return this many transactions
        :param offset: Skip this many transactions (for pagination)
        :param h_type: 'user' or 'contract' (default: user)
        :return: list of dict(block, txid, timestamp, symbol, from, from_type, to, to_type, memo, quantity)
        """
        payload = dict(
            account=account,
            symbol=symbol,
            limit=limit,
            offset=offset,
            type=h_type
        )
        log.debug('Calling URL %s with payload: %s', self.url, payload)
        r = self.req.get(self.url, params=payload)

        return r.json()
