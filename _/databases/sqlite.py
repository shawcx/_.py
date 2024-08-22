#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import os
import sqlite3
import uuid

import _

try:
    import aiosqlite
except ImportError:
    raise _.error('Missing aiosqlite module')


logging.getLogger("aiosqlite").setLevel(logging.WARNING)

import sqlalchemy.dialects.sqlite

#aiosqlite.register_adapter(bool, int)
#aiosqlite.register_converter('BOOLEAN', lambda v: bool(int(v)))

#aiosqlite.register_adapter(uuid.UUID, str)
#aiosqlite.register_converter('UUID', lambda v: uuid.UUID(v))


class SQLite(_.databases.Database):
    DRIVER = 'sqlite+aiosqlite'

    JSON   = sqlalchemy.dialects.sqlite.JSON
    BYTES  = sqlalchemy.dialects.sqlite.BLOB

    async def init(self, name, **kwds):
        await super(SQLite, self).init(name, **kwds)
        logging.getLogger('aiosqlite').setLevel(logging.WARNING)
