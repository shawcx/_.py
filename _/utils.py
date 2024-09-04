#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import asyncio
import logging
import os
import time

import tornado.web

import _


# alias so handlers don't have to import tornado.web directly
HTTPError = tornado.web.HTTPError

# return the current time in milliseconds
now = lambda: int(time.time() * 1000)

# add a prefix to dictionary names
prefix = lambda kwds,prepend='_': dict((f'{prepend}{k}',v) for k,v in kwds.items())

# pass _.function as a filter to the all function
function = type(lambda: None)


async def wait(result):
    '''wait on coroutines or return result of non-coroutines'''
    try:
        return result if not asyncio.iscoroutine(result) else await result
    except Exception as e:
        logging.exception("Unhandled exception")
        raise


class Paths:
    def __init__(self, root=None, ns=None):
        self.root = root
        self.ns   = ns

    def __call__(self, *args):
        return os.path.join(self.root, self.ns, *args)
