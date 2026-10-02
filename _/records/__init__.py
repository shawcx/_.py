#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import dataclasses
import importlib
import json
import logging

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

    # records modules can swap in an encoder for their own field types
    _json_encoder = _.JSONEncoder

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
        return json.dumps(self, cls=self._json_encoder, separators=(',',':'), **kwds)


class HandlerInterface(_.handlers.Protected):
    def initialize(self):
        self.content_type = self.get_argument('type', 'json')
        if self.content_type == 'json':
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
        else:
            self.set_header('Content-Type', 'application/octet-stream')

    async def prepare(self):
        await super().prepare()
        # parse here rather than initialize so errors become HTTP responses
        self.record = None
        if self.request.body:
            try:
                if self.content_type == 'json':
                    self.record = self._record._from_json(self.request.body)
                else:
                    self.record = self._record._from_binary(self.request.body)
            except (_.error,ValueError) as e:
                raise _.HTTPError(400, str(e)) from None

    def _record_id(self, record_id):
        'convert the id from the URL to the primary key column type'
        column = getattr(self._record, self._record.__primary_key__)
        try:
            python_type = column.type.python_type
        except (AttributeError,NotImplementedError):
            return record_id
        try:
            return python_type(record_id)
        except ValueError:
            raise _.HTTPError(404) from None

    @_.auth.records
    async def get(self, record_id):
        if not record_id:
            records = await self._db.find(self._record)
            if self.content_type == 'json':
                self.write(dict(data=records))
            else:
                self.write(dict(data=records))
        else:
            record_id = self._record_id(record_id)
            record = await self._db.find_one(self._record, record_id)
            if record is None:
                raise _.HTTPError(404)
            if self.content_type == 'json':
                self.write(record._as_dict())
            else:
                self.write(record._as_binary())

    @_.auth.records
    async def post(self, record_id, record=None):
        record = record or self.record
        if record is None:
            raise _.HTTPError(400, 'Missing record')
        try:
            await self._db.insert(record)
        except _.error as e:
            raise _.HTTPError(409, e) from None
        self.set_status(204)
        #self.write(record._as_dict())

    @_.auth.records
    async def put(self, record_id, record=None):
        record = record or self.record
        if record is None:
            raise _.HTTPError(400, 'Missing record')
        try:
            await self._db.upsert(record)
        except _.error as e:
            raise _.HTTPError(500, e) from None
        self.set_status(204)

    @_.auth.records
    async def delete(self, record_id):
        if record_id is None:
            raise _.HTTPError(500)
        count = await self._db.delete(self._record, self._record_id(record_id))
        if not count:
            raise _.HTTPError(404)
        self.set_status(204)
