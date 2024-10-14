#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
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


class SQLite(_.databases.Database):
    DRIVER = 'sqlite+aiosqlite'

    ARRAY  = sqlalchemy.dialects.sqlite.JSON
    JSON   = sqlalchemy.dialects.sqlite.JSON
    BYTES  = sqlalchemy.dialects.sqlite.BLOB
    BOOL   = sqlalchemy.dialects.sqlite.BOOLEAN
    UUID   = UUID

    async def init(self, component_name, **kwds):
        await super(SQLite, self).init(component_name, **kwds)
        logging.getLogger('aiosqlite').setLevel(logging.WARNING)


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
