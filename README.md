# Python SteemEngine

[![Documentation Status](https://readthedocs.org/projects/python-steemengine/badge/?version=latest)](https://python-steemengine.readthedocs.io/en/latest/?badge=latest) 
[![Build Status](https://travis-ci.com/Privex/python-steemengine.svg?branch=master)](https://travis-ci.com/Privex/python-steemengine) 
[![Codecov](https://img.shields.io/codecov/c/github/Privex/python-steemengine)](https://codecov.io/gh/Privex/python-steemengine)
[![PyPi Version](https://img.shields.io/pypi/v/privex-steemengine.svg)](https://pypi.org/project/privex-steemengine/)
![License Button](https://img.shields.io/pypi/l/privex-steemengine) 
![PyPI - Downloads](https://img.shields.io/pypi/dm/privex-steemengine)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/privex-steemengine) 
![GitHub last commit](https://img.shields.io/github/last-commit/Privex/python-steemengine)

A small library for querying and interfacing with the [SteemEngine](https://steem-engine.com) network, including
sending and issuing tokens.

**Official Repo:** https://github.com/privex/python-steemengine

# Information

This Python SteemEngine library has been developed at [Privex Inc.](https://www.privex.io) by @someguy123 for 
both simple querying, as well as transaction signing (sending, issuing) on the SteemEngine network.

It uses the following libraries:
 
 - [Python Requests](http://docs.python-requests.org/en/master/) for requests to SteemEngine History
 - [Beem](https://github.com/holgern/beem) by @holgern (holger80 on Steem) for Steem queries and transaction signing
 - [Privex's JsonRPC library](https://github.com/Privex/python-jsonrpc) for interacting with the SteemEngine RPC API.


```
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
```


# Quick Install / Usage

```bash
pip3 install privex-steemengine
```

```python
from decimal import Decimal
from privex.steemengine import SteemEngineToken

# The default network is "steem"
s = SteemEngineToken()
# For interacting with and broadcasting transactions on HiveEngine, set network="hive"
s = SteemEngineToken(network="hive")

# Get all SteemEngine transactions for @someguy123 
for tx in s.list_transactions('someguy123'):
    print(tx['timestamp'], tx['symbol'], tx['quantity'], tx['memo'])

# Get the amount of ENG that @someguy123 owns, as a Decimal()
print(s.get_token_balance('someguy123', 'ENG'))
# 0.00

# Issue 1.234 SGTK to @someguy123 - automatically detects the issuing account
s.issue_token('SGTK', 'someguy123', Decimal('1.234'))

# Send 10 ENG to @privex from @someguy123 with the memo 'hello memo'
s.send_token('ENG', 'someguy123', 'privex', Decimal('10'), 'hello memo')

```

For full parameter documentation, IDEs such as PyCharm and even Visual Studio Code should show our PyDoc
comments when you try to use the class.

![Screenshot of PyCharm SteemEngine Help](https://i.imgur.com/R9oewTY.png)

For PyCharm, press F1 with your keyboard cursor over the class to see full function documentation, including
return types, parameters, and general usage information. You can also press CMD-P with your cursor inside of 
a method's brackets (including the constructor brackets) to see the parameters you can use.

Alternatively, just view the files inside of `privex/steemengine/` - most methods and constructors
are adequately commented with PyDoc.

# Documentation

[![Read the Documentation](https://read-the-docs-guidelines.readthedocs-hosted.com/_images/logo-wordmark-dark.png)](
https://python-steemengine.readthedocs.io/en/latest/)

Full documentation for this project is available above (click the Read The Docs image), including:

 - How to install the application and it's dependencies 
 - How to use the various functions and classes
 - General documentation of the modules and classes for contributors

**To build the documentation:**

```bash
git clone https://github.com/Privex/python-steemengine
cd python-steemengine/docs
pip3 install -r requirements.txt

# It's recommended to run make clean to ensure old HTML files are removed
# `make html` generates the .html and static files in docs/build for production
make clean && make html

# After the files are built, you can live develop the docs using `make live`
# then browse to http://127.0.0.1:8100/
# If you have issues with content not showing up correctly, try make clean && make html
# then run make live again.
make live
```

# Signing Transactions

For signing transactions, you will need a Beem wallet, with the password specified as the environmental variable
`UNLOCK`. In most Python web apps, you can place this in your application's `.env` file for automatic loading.

Install Beem globally to use the `beempy` command, create a wallet, then import the active keys of the Steem accounts
you'll be using to transact on SteemEngine.

```bash
# Install beem globally (not in a virtualenv) for the `beempy` command to manage wallets
pip3 install -U beem
# Create a wallet, keep the password safe, you'll need to pass it to your script
beempy createwallet
# Import any active keys for accounts that you'll be transacting with
beempy addkey
```

Example Python script:

```python
#!/usr/bin/env python3
from decimal import Decimal
from beem import Steem
from beem.instance import set_shared_steem_instance

# Create an instance of Steem, and set it as the shared instance, so that it can be used by the library
steem_ins = Steem()
steem_ins.set_password_storage('environment')   # Tell Beem to use the `UNLOCK` env variable to unlock the wallet
set_shared_steem_instance(steem_ins)

from privex.steemengine import SteemEngineToken
s = SteemEngineToken()
# Replace the below parameters as needed. 
# Send 10 ENG to @privex from @someguy123 with the memo 'hello memo'
s.send_token('ENG', 'someguy123', 'privex', Decimal('10'), 'hello memo')
```

Save the above as `app.py`.

```bash
# Make your script executable
chmod +x app.py
# Run the script, passing in your wallet password with the UNLOCK env variable.
UNLOCK="YourWalletPassword" ./app.py
```

Beem will now be able to automatically unlock your wallet to sign a Steem transaction, such as when sending or 
issuing tokens. 

We recommend using something like [python-dotenv](https://github.com/theskumar/python-dotenv) in your Python projects
so that you can store the password in a `.env` file (make sure to use secure file permissions for `.env`)

# Install

We recommend that you use at least Python 3.4+ due to the usage of parameter and return type hinting.

### Install from PyPi using `pip`

You can install this package via pip:

```sh
pip3 install privex-steemengine
```

### (Alternative) Manual install from Git

If you don't want to PyPi (e.g. for development versions not on PyPi yet), you can install the 
project directly from our Git repo.

Unless you have a specific reason to manually install it, you **should install it using pip3 normally**
as shown above.

**Option 1 - Use pip to install straight from Github**

```sh
pip3 install git+https://github.com/Privex/python-steemengine
```

**Option 2 - Clone and install manually**

```bash
# Clone the repository from Github
git clone https://github.com/Privex/python-steemengine
cd python-steemengine

# RECOMMENDED MANUAL INSTALL METHOD
# Use pip to install the source code
pip3 install .

# ALTERNATIVE INSTALL METHOD
# If you don't have pip, or have issues with installing using it, then you can use setuptools instead.
python3 setup.py install
```


# Logging

By default, this package will log anything >=WARNING to the console. You can override this by adjusting the
`privex.steemengine` logger instance. 

We recommend checking out our Python package [Python Loghelper](https://github.com/Privex/python-loghelper) which
makes it easy to manage your logging configuration, and copy it to other logging instances such as this one.

```python
# Without LogHelper
import logging
l = logging.getLogger('privex.steemengine')
l.setLevel(logging.ERROR)

# With LogHelper (pip3 install privex-loghelper)
from privex.loghelper import LogHelper
# Set up logging for **your entire app**. In this case, log only messages >=error
lh = LogHelper('myapp', handler_level=logging.ERROR)
lh.add_file_handler('test.log')        # Log messages to the file `test.log` in the current directory
lh.copy_logger('privex.steemengine')   # Easily copy your logging settings to any other module loggers
log = lh.get_logger()                  # Grab your app's logging instance, or use logging.getLogger('myapp')
log.error('Hello World')
```

# Unit Tests

Unit tests are available in `tests.py`. We also have the project set up with [Travis CI](https://travis-ci.com/Privex/python-steemengine)
to alert us when new releases cause the tests to break.

To run the tests manually, either simply run `tests.py` directly (or with python3), or use pytest:

```sh
git clone https://github.com/Privex/python-steemengine
pip3 install .
./tests.py
# Verbose mode (shows the name of the test, and the comment under it)
./tests.py -v

# You can also use pytest - which is used by our Travis CI setup.
pip3 install pytest
pytest tests.py
# Verbose mode
pytest tests.py
```

# Contributing

We're very happy to accept pull requests, and work on any issues reported to us. 

Here's some important information:

**Reporting Issues:**

 - For bug reports, you should include the following information:
     - Version of `privex-steemengine`, `beem` and `requests` tested on - use `pip3 freeze`
        - If not installed via a PyPi release, git revision number that the issue was tested on - `git log -n1`
     - Your python3 version - `python3 -V`
     - Your operating system and OS version (e.g. Ubuntu 18.04, Debian 7)
 - For feature requests / changes
     - Please avoid suggestions that require new dependencies. This tool is designed to be lightweight, not filled with
       external dependencies.
     - Clearly explain the feature/change that you would like to be added
     - Explain why the feature/change would be useful to us, or other users of the tool
     - Be aware that features/changes that are complicated to add, or we simply find un-necessary for our use of the tool 
       may not be added (but we may accept PRs)
    
**Pull Requests:**

 - We'll happily accept PRs that only add code comments or README changes
 - Use 4 spaces, not tabs when contributing to the code
 - You can use features from Python 3.4+ (we run Python 3.7+ for our projects)
    - Features that require a Python version that has not yet been released for the latest stable release
      of Ubuntu Server LTS (at this time, Ubuntu 18.04 Bionic) will not be accepted. 
 - Clearly explain the purpose of your pull request in the title and description
     - What changes have you made?
     - Why have you made these changes?
 - Please make sure that code contributions are appropriately commented - we won't accept changes that involve 
   uncommented, highly terse one-liners.

**Legal Disclaimer for Contributions**

Nobody wants to read a long document filled with legal text, so we've summed up the important parts here.

If you contribute content that you've created/own to projects that are created/owned by Privex, such as code or 
documentation, then you might automatically grant us unrestricted usage of your content, regardless of the open source 
license that applies to our project.

If you don't want to grant us unlimited usage of your content, you should make sure to place your content
in a separate file, making sure that the license of your content is clearly displayed at the start of the file 
(e.g. code comments), or inside of it's containing folder (e.g. a file named LICENSE). 

You should let us know in your pull request or issue that you've included files which are licensed
separately, so that we can make sure there's no license conflicts that might stop us being able
to accept your contribution.

If you'd rather read the whole legal text, it should be included as `privex_contribution_agreement.txt`.

# License

This project is licensed under the **X11 / MIT** license. See the file **LICENSE** for full details.

Here's the important bits:

 - You must include/display the license & copyright notice (`LICENSE`) if you modify/distribute/copy
   some or all of this project.
 - You can't use our name to promote / endorse your product without asking us for permission.
   You can however, state that your product uses some/all of this project.



# Thanks for reading!

**If this project has helped you, consider [grabbing a VPS or Dedicated Server from Privex](https://www.privex.io) - 
prices start at as little as US$8/mo (we take cryptocurrency!)**