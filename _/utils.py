#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import asyncio
import base64
import datetime
import json
import inspect
import logging
import os
import time
import uuid

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
        if _.args.debug:
            trace = []
            for f in inspect.stack()[:0:-1]:
                if not f.code_context:
                    continue
                context = '\n'.join(c.strip() for c in f.code_context)
                msg = f'  File "{f.filename}", line {f.lineno}, in {f.function}\n    {context}'
                trace.append(msg)
            logging.exception(f'Unhandled exception:\n%s', '\n'.join(trace))
        raise


class Paths:
    def __init__(self, root, ns=None):
        self.root = root
        self.ns   = ns

    def __call__(self, *args):
        if self.ns is None:
            return os.path.join(self.root, *args)
        else:
            return os.path.join(self.root, self.ns, *args)

    # support / as a path joiner
    def __truediv__(self, other):
        return Paths(self(other))

    def __str__(self):
        return self()


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '_as_dict'):
            return obj._as_dict()
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('ascii')
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

json._default_encoder = JSONEncoder()
