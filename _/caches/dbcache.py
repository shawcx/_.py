#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import json
import logging
import os

import _


class DbCache(_.caches.Cache):
    _config  = 'config'
    _key_col = 'key'
    _key     = 'cookie'
    _val_col = 'value'

    _table      = 'sessions'
    _session_id = 'session_id'

    async def init(self, name, database=None, table=None, **kwds):
        if not hasattr(_.application, 'is_session_expired'):
            raise _.error('Application does not have is_session_expired function defined')

        if database is None:
            if 1 == len(_.databases):
                database = list(_.databases.keys())[0]
            else:
                raise _.error('dbcache requires a database to be specified')
        self.db = _.databases[database]

        schema = self.db.schema('config')
        table = schema.table(self._config)
        table.column(self._key_col).primary_key()
        table.column(self._val_col)
        await schema.apply()

        schema = self.db.schema('sessions')
        table = schema.table(self._table)
        table.column(self._session_id).primary_key()
        for col,dbtype in kwds.items():
            table.column(col).type(dbtype)
        await schema.apply()

        # interval comes from the [sessions] section of the ini
        _.application.periodic(self._interval, self.clear_stale_sessions)

        members = dict(
            name       = name,
            db         = self.db,
            table      = self._table,
            session_id = self._session_id,
            )
        subclass = type(name, (DbCacheSessions,), _.prefix(members))
        _.application._record_handler('sessions', subclass)

    async def cookie_secret(self):
        secret = await self.db.find_one(self._config, self._key_col, self._key)
        if secret:
            secret = secret['value']
        else:
            secret = base64.b64encode(os.urandom(32))
            record = {
                self._key_col : self._key,
                self._val_col : secret,
            }
            await self.db.upsert(self._config, record)
        return secret

    async def save_session(self, session):
        super().save_session(session)
        await self.db.upsert(self._table, session)

    async def load_session(self, session_id):
        record = await self.db.find_one(self._table, self._session_id, session_id)
        if not record:
            return None
        if await _.wait(_.application.is_session_expired(record, self._expires)):
            return None
        return record

    async def clear_stale_sessions(self):
        for record in await self.db.find(self._table):
            if await _.wait(_.application.is_session_expired(record, self._expires)):
                logging.debug('Removing expired session: %s', record[self._session_id])
                await self.db.delete(self._table, self._session_id, record[self._session_id])


class DbCacheSessions(_.handlers.Protected):
    @_.auth.protected
    async def get(self, session_id=None):
        if session_id:
            record = await self._db.find_one(self._table, self._session_id, session_id)
            self.write(record)
        else:
            records = await self._db.find(self._table)
            data = []
            for record in records:
                data.append(dict(record))
            self.write({'data':data})

    @_.auth.protected
    async def delete(self, session_id=None):
        self.set_status(204)
        if session_id:
            await self._db.delete(self._table, self._session_id, session_id)

            callback = getattr(_.application, f'on_{self._name}_delete', None)
            if callback is None:
                callback = getattr(_.application, 'on_dbcache_delete', None)
            if callback:
                await _.wait(callback(self._name, record))
