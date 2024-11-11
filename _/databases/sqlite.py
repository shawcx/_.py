#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import typing
import uuid

import _

try:
    import aiosqlite
except ImportError:
    raise _.error('Missing aiosqlite module')

logging.getLogger("aiosqlite").setLevel(logging.WARNING)

import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.dialects.sqlite

#aiosqlite.register_adapter(bool, int)
#aiosqlite.register_converter('BOOLEAN', lambda v: bool(int(v)))

#aiosqlite.register_adapter(uuid.UUID, str)
#aiosqlite.register_converter('UUID', lambda v: uuid.UUID(v))


class UUID(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.CHAR

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return '%.32x' % uuid.UUID(value).int
        return '%.32x' % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value

# TODO: test if calling this in init is sufficient
#@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
#def set_sqlite_pragma(conn, record):
#    if 'sqlite' in conn.__module__:
#        cursor = conn.cursor()
#        cursor.execute("PRAGMA foreign_keys=ON")
#        cursor.close()


class SQLite(_.databases.Database):
    DRIVER = 'sqlite+aiosqlite'

    ARRAY  = sqlalchemy.dialects.sqlite.JSON
    JSON   = sqlalchemy.dialects.sqlite.JSON
    BYTES  = sqlalchemy.dialects.sqlite.BLOB
    BOOL   = sqlalchemy.dialects.sqlite.BOOLEAN
    UUID   = UUID

    class Base(
            sqlalchemy.ext.asyncio.AsyncAttrs,
            sqlalchemy.orm.MappedAsDataclass,
            sqlalchemy.orm.DeclarativeBase,
            ):
        'base class for _.records'

        type_annotation_map = {
            int:                         sqlalchemy.BIGINT,
            dict[str, typing.Any]:       sqlalchemy.dialects.sqlite.JSON,
            list[dict[str, typing.Any]]: sqlalchemy.dialects.sqlite.JSON,
            }

    async def init(self, component_name, **kwds):
        logging.getLogger('aiosqlite').setLevel(logging.WARNING)
        await super(SQLite, self).init(component_name, **kwds)
        async with self.engine.begin() as conn:
            await conn.run_sync(lambda conn: 'PRAGMA foreign_keys=ON')
