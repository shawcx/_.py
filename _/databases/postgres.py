#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import typing

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

    TYPE_ANNOTATION_MAP = {
        int:                         sqlalchemy.BIGINT,
        dict[str, typing.Any]:       sqlalchemy.dialects.postgresql.JSONB,
        list[dict[str, typing.Any]]: sqlalchemy.dialects.postgresql.JSONB,
        }

    def array(self, item_type):
        return self.ARRAY(item_type)
