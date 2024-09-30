#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import asyncio
import logging
import os
import signal
import socket
import sys
import traceback

import tornado.web

import _


class Application(_.Application):
    async def __listen(self, patterns, **kwds):
        '''call the Tornado Application init here to give children a chance
           to initialize patterns and settings'''
        logging.info('Would be listening on %s:%d', _.args.address, _.args.port)

_.Application = Application
