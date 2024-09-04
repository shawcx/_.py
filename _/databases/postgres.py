#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import re

import _

try:
    import asyncpg
except ImportError:
    raise _.error('Missing asyncpg module')

import sqlalchemy
import sqlalchemy.dialects.postgresql


class Postgres(_.databases.Database):
    DRIVER = 'postgresql+asyncpg'

    ARRAY  = sqlalchemy.dialects.postgresql.ARRAY
    JSON   = sqlalchemy.dialects.postgresql.JSONB
    BYTES  = sqlalchemy.dialects.postgresql.BYTEA
    UUID   = sqlalchemy.dialects.postgresql.UUID

    async def init(self, name, **kwds):
        await super(Postgres, self).init(name, **kwds)
