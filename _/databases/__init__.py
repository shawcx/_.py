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
    import sqlalchemy
    import sqlalchemy.types
    import sqlalchemy.orm
    from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
except ImportError:
    raise _.error('Missing sqlalchemy module')


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
    async def upsert(self, obj):
        async with self.session() as session:
            async with session.begin():
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
