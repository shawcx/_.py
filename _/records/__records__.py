#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import importlib
import datetime
import json
import uuid

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
        except ModuleNotFoundError:
            raise _.error('Unknown module: %s', module)

        if database is None:
            if 1 == len(_.databases):
                database = list(_.databases.keys())[0]
            else:
                raise _.error('%s requires a database to be specified', name)

        self.db = _.databases[database]
        self.schema = self.db.schema(module)
        await _.wait(self.load(imported))
        await self.schema.apply()

    def load(self, module):
        raise NotImplementedError


class Interface:
    def __init__(self, *args, **kwds):
        self.__dict__['_record'] = self._record_cls()
        for kwd in kwds:
            setattr(self._record, kwd, kwds[kwd])

    class Json(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, bytes):
                return base64.b64encode(obj).decode('ascii')
            if hasattr(obj, '_record_cls'):
                return obj.as_dict(obj)
            if isinstance(obj, datetime.datetime):
                return str(obj)
            if isinstance(obj, uuid.UUID):
                return str(obj)
            return json.JSONEncoder.default(self, obj)

    @classmethod
    def from_json(cls, msg):
        raise NotImplementedError

    @classmethod
    def as_dict(cls, obj):
        raise NotImplementedError

    def json(self, **kwds):
        return json.dumps(self, cls=self.Json, separators=(',',':'), **kwds)

    def dict(self):
        return self.as_dict(self)

    def __getattr__(self, name):
        return getattr(self._record, name)

    def __setattr__(self, name, value):
        self._record.__setattr__(name, value)

    def __str__(self):
        return self._record.__str__()

    def __repr__(self):
        return self._record.__repr__()


class DatabaseInterface:
    @classmethod
    async def find(cls, params=None, sort=None):
        rows = await cls._db.find(cls._name)
        return [cls(**r) for r in rows]

    @classmethod
    async def find_one(cls, value):
        row = await cls._db.find_one(cls._name, cls._primary_key, value)
        return cls(**row) if row else None

    @classmethod
    async def count(cls, field=None, value=None):
        return await cls._db.count(cls._name, field, value)

    async def insert(self):
        values = self.dict()
        row = await self._db.insert(self._name, self._primary_key, values)
        return row

    async def update(self):
        values = self.dict()
        row = await self._db.update(self._name, self._primary_key, values)
        return row

    async def upsert(self):
        values = self.dict()
        row = await self._db.upsert(self._name, values)

    async def delete(self):
        await self._db.delete(self._name, self._primary_key, getattr(self, self._primary_key))


class HandlerInterface(_.handlers.Protected):
    def initialize(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')

    @_.auth.protected
    async def get(self, record, record_id):
        if hasattr(self._record_cls, 'get'):
            return self._record_cls.get(self, record, record_id)

        if not record_id:
            records = await self._db.find(record)
            self.write(dict(data=[dict(r) for r in records]))
        else:
            record = await self._db.find_one(record, self._record._primary_key, record_id)
            if record is None:
                raise _.HTTPError(404)
            self.write(record)

    @_.auth.protected
    async def put(self, record, record_id):
        if hasattr(self._record_cls, 'put'):
            return self._record_cls.put(self, record, record_id)

        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise _.HTTPError(500)

        await _.wait(self._record.put(record_id, data, self.request))
        self.set_status(204)

    @_.auth.protected
    async def delete(self, record, record_id):
        if hasattr(self._record_cls, 'delete'):
            return self._record_cls.delete(self, record, record_id)

        if not record_id:
            raise _.HTTPError(500)

        data = await self._db.find_one(record, self._record._primary_key, record_id)
        if not data:
            raise _.HTTPError(404)

        await self._db.delete(record, self._record._primary_key, record_id)
        await _.wait(self._record.delete(record_id, data, self.request))
        self.set_status(204)
