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
    async def _(cls, component_name, **kwds):
        self = cls()
        self.component_name = component_name
        try:
            print('????', kwds)
            await self.init(**kwds)
        except TypeError as e:
            raise _.error('%s', e)
        _.records[component_name] = self

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
