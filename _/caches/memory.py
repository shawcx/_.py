#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import os
import json

import _


class Memory(_.caches.Cache):
    async def init(self, name, **kwds):
        if not hasattr(_.application, 'is_session_expired'):
            raise _.error('Application does not have is_session_expired function defined')

        self.mem = {}

        members = dict(
            name = name,
            mem  = self.mem,
            )
        subclass = type(name, (MemorySessions,), _.prefix(members))
        _.application._record_handler('sessions', subclass)

    def cookie_secret(self):
        return os.urandom(32)

    def save_session(self, session):
        session_id = super().save_session(session)
        self.mem[session_id] = json.dumps(session)

    async def load_session(self, session_id):
        session = self.mem.get(session_id, None)
        if not session:
            return None
        if await _.wait(_.application.is_session_expired(session, self.expires)):
            return None
        return json.loads(session)



class MemorySessions(_.handlers.Protected):
    @_.auth.protected
    async def get(self, session_id=None):
        if session_id:
            session = self._mem[session_id]
            if not session:
                raise _.HTTPError(404)
            session = json.loads(session)
            self.write(session)
        else:
            data = []
            for session_id in self._mem:
                session = self._mem[session_id]
                data.append(json.loads(session))
            self.write({'data':data})

    @_.auth.protected
    async def delete(self, session_id=None):
        self.set_status(204)
        if session_id:
            del self._mem[session_id]
            callback = getattr(_.application, f'on_{self._name}_delete', None)
            if callback is None:
                callback = getattr(_.application, 'on_memory_delete', None)
            if callback:
                await _.wait(callback(self._name, session_id))
