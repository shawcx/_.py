#
# (c) 2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging

import _


class TestApplication(_.WebApplication):
    async def __listen(self, patterns, **kwds):
        '''call the Tornado Application init here to give children a chance
           to initialize patterns and settings'''
        logging.info('Would be listening on %s:%d', _.args.address, _.args.port)

_.Application = TestApplication
