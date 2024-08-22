#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import collections
import os

from .utils import *

from . import version
from . import settings
from . import auth
from . import handlers
from . import components

from .application import Application


class error(Exception):
    '''generic error class for throwing exceptions'''

    def __init__(self, fmt, *args):
        self.message = fmt % args

    def __str__(self):
        return self.message


class Container(collections.UserDict):
    '''helper class to hold the loadable components'''
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

# placeholder for comonents
caches    = Container()
databases = Container()
logins    = Container()
records   = Container()
supports  = Container()
