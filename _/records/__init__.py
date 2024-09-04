#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import importlib
import json

import sqlalchemy
import sqlalchemy.ext.asyncio

import _


class Record:
    @classmethod
    async def _(cls, name, **kwds):
        self = cls()
        self.name = name
        try:
            await self.init(**kwds)
        except TypeError as e:
            raise _.error('%s', e)
        _.records[name] = self

    async def init(self, module, database=None):
        try:
            imported = importlib.import_module(module)
        except ModuleNotFoundError as e:
            raise _.error('Unknown module: %s: %s', module, e)

        self.db = _.databases[database] if database else None

        await _.wait(self.load(imported))

        if self.db:
            await self.db.create_tables()

    def load(self, module):
        raise NotImplementedError


class DatabaseInterface:
    @classmethod
    async def find(cls, params=None, order=None):
        print('FIND!!!!', cls, params, order)
        print(dir(cls._orm))
        print()
        #rows = await cls._db.find(cls._name, params, order)
        #return [cls(**r) for r in rows]
        stmt = sqlalchemy.select(cls._orm)
        async with cls._db.session() as session:
            async with session.begin() as connection:
                print(dir(session))
                r = await session.scalar(stmt)
                print(r)
                print()

    @classmethod
    async def find_one(cls, value, col=None, order=None):
        print('hi', cls, value)
        #if col is None:
        #    col = cls._primary_key
        #row = await cls._db.find_one(cls._name, col, value, order)
        #return cls(**row) if row else None
        pass

    @classmethod
    async def count(cls, field=None, value=None):
        #return await cls._db.count(cls._name, field, value)
        pass

    def select(self):
        return sqlalchemy.select(self._orm)

    async def insert(self):
        #values = self.dict()
        #obj = self._table(**self.dict())
        #await self._db.insert(obj)

        stmt = sqlalchemy.select(self._orm)
        async with self._db.session() as session:
            print('%' * 50)
            print(self)
            print('%' * 50)
            #async with session.begin() as connection:
            #    print(dir(session))
            #    r = await session.scalar(stmt)
            #    print(r)
            #    print()
        #print()
        #print(dir(self))
        #print(self._db)
        #for c in self._table.c:
        #    print(c)
        #print(values)
        #print()
        #row = await self._db.insert(self._name, self._primary_key, values)
        #return row

    async def update(self):
        values = self.dict()
        #row = await self._db.update(self._name, self._primary_key, values)
        #return row

    async def upsert(self):
        values = self.dict()
        #row = await self._db.upsert(self._name, values)

    async def delete(self):
        obj = self._table(**self.dict())
        await self._db.delete(obj)


class HandlerInterface(_.handlers.Protected):
    def initialize(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if self.request.body:
            try:
                self.json = json.loads(self.request.body)
            except:
                raise _.HTTPError(500)
        else:
            self.json = None

    def load(self, kwds=None):
        return self._record(kwds or self.json)

    @_.auth.protected
    async def get(self, record_id):
        if not hasattr(self, '_db'):
            raise _.HTTPError(405)

        if not record_id:
            records = await self._record.find()
            self.write(dict(data=[r.dict() for r in records]))
        else:
            record = await self._record.find_one(record_id)
            if record is None:
                raise _.HTTPError(404)
            self.write(record)

    @_.auth.protected
    async def post(self, record_id, record=None):
        if not hasattr(self, '_db'):
            raise _.HTTPError(405)
        if record is None:
            record = self._record(**self.json)
        try:
            await record.insert()
        except _.error as e:
            raise _.HTTPError(409, e) from None
        self.set_status(204)
        return record

    @_.auth.protected
    async def put(self, record_id, record=None):
        if not hasattr(self, '_db'):
            raise _.HTTPError(405)
        if record is None:
            record = self._record(**self.json)
        try:
            await record.upsert()
        except _.error as e:
            raise _.HTTPError(500, e) from None
        self.set_status(204)
        return record

    @_.auth.protected
    async def delete(self, record_id):
        if not hasattr(self, '_db'):
            raise _.HTTPError(405)

        if not record_id:
            raise _.HTTPError(500)

        record = await self._record.find_one(record_id)
        if not record:
            raise _.HTTPError(404)

        await record.delete()
        self.set_status(204)
        return record
