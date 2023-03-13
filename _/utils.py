#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import asyncio
import collections
import inspect
import logging
import os
import sys
import textwrap
import time

import tornado.web

import _


HTTPError = tornado.web.HTTPError

# a generic error class for throwing exceptions
class error(Exception):
    def __init__(self, fmt, *args):
        self.message = fmt % args

    def __str__(self):
        return self.message


class Container(collections.UserDict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


def now():
    return int(time.time() * 1000)

async def wait(result):
    try:
        return result if not asyncio.iscoroutine(result) else await result
    except Exception as e:
        logging.exception("Unhandled exception")
        raise

prefix = lambda kwds,prepend='_': dict((f'{prepend}{k}',v) for k,v in kwds.items())

class Paths:
    def __init__(self, root=None, ns=None):
        self.root = root
        self.ns   = ns

    def __call__(self, *args):
        return os.path.join(self.root, self.ns, *args)

sql = lambda statement: textwrap.dedent(statement.strip())

# to pass _.function as a filter to the all function
function = type(lambda: None)


def all(instance=object, cls=None, prefix='', suffix=''):
    'overkill function for import * from module to limit what is imported'
    __all__ = []
    module = inspect.getmodule(inspect.currentframe().f_back)
    root = module.__name__.rsplit('.', 1)[0] + '.'
    for name in dir(module):
        # ignore built-ins
        if name.startswith('_'):
            continue
        # filter prefix and suffix if specified
        if not name.startswith(prefix):
            continue
        if not name.endswith(suffix):
            continue

        obj = getattr(module, name)

        # filter modules unless they are sub-modules
        if isinstance(obj, type(module)):
            if not obj.__name__.startswith(root):
                continue
        # a way to filter out "local" variables
        if not isinstance(obj, instance):
            continue
        # only include sub-classes if specified
        if cls and issubclass(obj, cls):
            continue

        __all__.append(name)
    return __all__

__all__ = all()
