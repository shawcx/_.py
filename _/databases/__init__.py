#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import collections
import logging
import os

import _

try:
    import sqlalchemy
    import sqlalchemy.orm
except ImportError:
    raise _.error('Missing sqlalchemy module')

from sqlalchemy.ext.asyncio import create_async_engine

meta = sqlalchemy.MetaData()


class Database:
    TEXT    = sqlalchemy.TEXT
    INTEGER = sqlalchemy.INTEGER
    BIGINT  = sqlalchemy.BIGINT
    DOUBLE  = sqlalchemy.DOUBLE_PRECISION
    NUMERIC = sqlalchemy.NUMERIC
    REAL    = sqlalchemy.REAL
    BOOLEAN = sqlalchemy.BOOLEAN
    JSON    = None
    BYTES   = None
    UUID    = None

    @classmethod
    async def _(cls, name, **kwds):
        self = cls()
        _.databases[name] = self
        await self.init(name, **kwds)

    async def init(self, name, **kwds):
        kwds['drivername'] = self.DRIVER
        url = sqlalchemy.engine.URL.create(**kwds)
        logging.debug('Database URL: %s: %s', name, url)
        self.engine = create_async_engine(url, echo=False)

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(meta.create_all)
            await conn.commit()

    async def close(self):
        await self.engine.dispose()

    async def find(self, table, params=None, order=None):
        raise NotImplementedError

    async def find_one(self, table, id_column, _id, order=None):
        raise NotImplementedError

    async def insert(self, table, id_column, values):
        raise NotImplementedError

    async def insert_unique(self, table, id_column, values):
        raise NotImplementedError

    async def upsert(self, table, id_column, values):
        raise NotImplementedError

    async def update(self, table, id_column, values):
        raise NotImplementedError

    async def delete(self, table, id_column, value):
        raise NotImplementedError
