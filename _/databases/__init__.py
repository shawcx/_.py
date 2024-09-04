#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import dataclasses
import datetime
import json
import logging
import os
import uuid

import _

try:
    import sqlalchemy
    import sqlalchemy.orm
    from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
except ImportError:
    raise _.error('Missing sqlalchemy module')


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
        self.session = sqlalchemy.orm.sessionmaker(self.engine, class_=AsyncSession)

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()

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
    async def find(self, cls, where=None):
        statement = sqlalchemy.select(cls)
        async with self.session() as session:
            results = await session.execute(statement)
            return results.unique().scalars().all()

    async def find_one(self, cls, value=None, column=None):
        statement = sqlalchemy.select(cls)
        if value:
            if not column:
                column = getattr(cls, cls.__primary_key__)
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
    async def delete(self, obj):
        async with self.session() as session:
            async with session.begin():
                await session.delete(obj)


class Base(
        sqlalchemy.ext.asyncio.AsyncAttrs,
        sqlalchemy.orm.MappedAsDataclass,
        sqlalchemy.orm.DeclarativeBase,
        ):
    'base class for _.records'

    type_annotation_map = {
        int: sqlalchemy.BIGINT,
    }

    def __call__(self, **kwds):
        for k,v in kwds.items():
            setattr(self, k, v)

    @classmethod
    def _from_dict(cls, **kwds):
        self = cls()
        for k,v in kwds.items():
            setattr(self, k, v)
        return self

    @classmethod
    def _from_json(cls, msg):
        return cls._from_dict(**json.loads(msg))

    def _as_dict(self):
        return dataclasses.asdict(self)

    def _as_json(self, **kwds):
        return json.dumps(self, cls=_Json, separators=(',',':'), **kwds)

    def __getitem__(self, name):
        return getattr(self, name)

class _Json(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '_as_dict'):
            return obj._as_dict()
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('ascii')
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime.datetime):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
