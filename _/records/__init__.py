#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import dataclasses
import datetime
import importlib
import json
import logging
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

import _


class Record:
    @classmethod
    async def _(cls, component_name, **kwds):
        self = cls()
        self.component_name = component_name
        _.records[component_name] = self
        try:
            await self.init(**kwds)
        except TypeError as e:
            raise _.error('%s', e)

    async def init(self, module, **kwds):
        try:
            imported = importlib.import_module(module)
        except ModuleNotFoundError as e:
            raise _.error('Unknown module: %s: %s', module, e)

        database = kwds.get('database', None)
        self.db = _.databases[database] if database else None

        await _.wait(self.load(imported))

        if self.db:
            await self.db.create_tables()

    @classmethod
    async def args(cls, component_name):
        pass

    def load(self, module):
        raise NotImplementedError


class RecordsInterface:
    'base class for _.records'

    def __call__(self, **kwds):
        for k,v in kwds.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

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
        _dict = dataclasses.asdict(self)
        if hasattr(self, '__primary_key__'):
            _dict[self.__primary_key__] = getattr(self, self.__primary_key__)
        return _dict

    def _as_json(self, **kwds):
        return json.dumps(self, cls=_Json, separators=(',',':'), **kwds)


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

json._default_encoder = _Json()


class HandlerInterface(_.handlers.Protected):
    def initialize(self):
        self.content_type = self.get_argument('type', 'json')
        if self.content_type == 'json':
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
        else:
            self.set_header('Content-Type', 'application/octet-stream')

        if self.request.body:
            try:
                if self.content_type == 'json':
                    self.data = json.loads(self.request.body)
                else:
                    self.data = self._record._from_binary(self.request.body)

            except:
                raise _.HTTPError(500)
        else:
            self.data = None

    @_.auth.records
    async def get(self, record_id):
        if not record_id:
            records = await self._db.find(self._record)
            if self.content_type == 'json':
                self.write(dict(data=records))
            else:
                self.write(dict(data=records))
        else:
            record_id = int(record_id)
            record = await self._db.find_one(self._record, record_id)
            if record is None:
                raise _.HTTPError(404)
            if self.content_type == 'json':
                self.write(record._as_dict())
            else:
                self.write(record._as_binary())

    @_.auth.records
    async def post(self, record_id, record=None):
        if record is None:
            record = self._record._from_binary(self.request.body)
        try:
            await self._db.insert(record)
        except _.error as e:
            raise _.HTTPError(409, e) from None
        self.set_status(204)
        #self.write(record._as_dict())

    @_.auth.records
    async def put(self, record_id, record=None):
        if record is None:
            record = self._record._from_dict(self.data)
        try:
            await self._db.upsert(record)
        except _.error as e:
            raise _.HTTPError(500, e) from None
        self.set_status(204)

    @_.auth.records
    async def delete(self, record_id):
        if record_id is None:
            raise _.HTTPError(500)
        count = await self._db.delete(self._record, record_id)
        if not count:
            raise _.HTTPError(404)
        self.set_status(204)
