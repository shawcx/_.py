#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import logging
import typing

import _

try:
    import sqlalchemy
    import sqlalchemy.types
    import sqlalchemy.orm
    from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
except ImportError:
    raise _.error('Missing sqlalchemy module')


class UInt64(sqlalchemy.types.TypeDecorator):
    '''unsigned 64-bit integer: NUMERIC(20) on Postgres, otherwise stored in
       a BIGINT as its two's complement so values of 2**63 and up fit'''
    impl     = sqlalchemy.BIGINT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(sqlalchemy.NUMERIC(20, 0))
        return dialect.type_descriptor(sqlalchemy.BIGINT())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == 'postgresql':
            return value
        return value - (1 << 64) if value >= (1 << 63) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return int(value)
        return value + (1 << 64) if value < 0 else value


class JSONArray(sqlalchemy.types.TypeDecorator):
    'list stored as JSON for databases without arrays, bytes as base64'
    impl     = sqlalchemy.JSON
    cache_ok = True

    def __init__(self, binary=False):
        super().__init__()
        self.binary = binary

    def process_bind_param(self, value, dialect):
        if value is not None and self.binary:
            value = [base64.b64encode(v).decode('ascii') for v in value]
        return value

    def process_result_value(self, value, dialect):
        if value is not None and self.binary:
            value = [base64.b64decode(v) for v in value]
        return value


class Database:
    TEXT    = sqlalchemy.TEXT
    INTEGER = sqlalchemy.INTEGER
    BIGINT  = sqlalchemy.BIGINT
    #DOUBLE  = sqlalchemy.DOUBLE_PRECISION
    NUMERIC = sqlalchemy.NUMERIC
    REAL    = sqlalchemy.REAL
    BOOLEAN = sqlalchemy.BOOLEAN
    JSON    = None
    BYTES   = None
    UUID    = None

    @classmethod
    async def _(cls, component_name, **kwds):
        self = cls()
        self.component_name = component_name
        _.databases[component_name] = self
        setattr(_, component_name, self)
        await self.init(component_name, **kwds)

    async def init(self, component_name, **kwds):
        kwds['drivername'] = self.DRIVER
        url = sqlalchemy.engine.URL.create(**kwds)
        logging.debug('Database URL: %s: %s', component_name, url)
        self.engine = create_async_engine(url, echo=False)
        self.session = sqlalchemy.orm.sessionmaker(self.engine, class_=AsyncSession)

    def array(self, item_type):
        'column type for a list of item_type, overridden by databases with arrays'
        return JSONArray(binary=isinstance(item_type, sqlalchemy.LargeBinary))

    async def create_tables(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(self.Base.metadata.create_all)
                await conn.commit()
        except Exception as e:
            raise _.error('Database "%s": %s', self.component_name, e) from None

    async def close(self):
        await self.engine.dispose()

    # CREATE
    async def insert(self, *args):
        try:
            async with self.session() as session:
                async with session.begin():
                    session.add_all(args)
        except sqlalchemy.exc.IntegrityError as e:
            raise _.error('%s', e) from None

    # READ
    async def find(self, cls, value=None, column=None):
        statement = sqlalchemy.select(cls)
        if value:
            column = getattr(cls, column or cls.__primary_key__)
            statement = statement.where(column == value)
        async with self.session() as session:
            results = await session.execute(statement)
            return results.unique().scalars().all()

    async def find_one(self, cls, value, column=None):
        statement = sqlalchemy.select(cls)
        column = getattr(cls, column or cls.__primary_key__)
        statement = statement.where(column == value)
        async with self.session() as session:
            results = await session.execute(statement)
            return results.unique().scalars().first()

    # UPDATE
    async def upsert(self, *args):
        async with self.session() as session:
            async with session.begin():
                for obj in args:
                    await session.merge(obj)

    # DELETE
    async def delete(self, obj, value=None):
        async with self.session() as session:
            async with session.begin():
                if value is None:
                    # delete an ORM instance
                    await session.delete(obj)
                else:
                    # otherwise assume obj is the SQLalchemy table class
                    column = getattr(obj, obj.__primary_key__)
                    statement = sqlalchemy.delete(obj).where(column == value)
                    results = await session.execute(statement)
                    return results.rowcount
