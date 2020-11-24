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


class SteemEngineException(Exception):
    """Base exception for all :mod:`privex.steemengine` exceptions"""


class TokenNotFound(SteemEngineException):
    """The token requested doesn't exist"""


class AccountNotFound(SteemEngineException):
    """The Steem account requested doesn't exist"""


class NotEnoughBalance(SteemEngineException):
    """Not enough token/steem/sbd balance for this operation"""


class NoResults(SteemEngineException):
    """The server returned an empty response such as ``None`` ..."""


class NoSteemEngineInstance(SteemEngineException):
    """Raised when :attr:`._seng_instance` on a :class:`.SteemEngineInstanceInject` based object is ``None``"""

class WrongNetwork(SteemEngineException):
    """The current RPC is on the wrong network, high risk of broadcasting or receiving data to/from the wrong blockchain network"""

