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
    async def init(self, component_name, **kwds):
        if not hasattr(_.application, 'is_session_expired'):
            raise _.error('Application does not have is_session_expired function defined')

        self.sessions = {}

        members = dict(
            component = component_name,
            sessions  = self.sessions,
            )
        subclass = type(component_name, (MemorySessions,), _.prefix(members))
        _.application._record_handler('sessions', subclass)

    def cookie_secret(self):
        return os.urandom(32)

    def save_session(self, session):
        try:
            session_id = session['session_id']
        except KeyError:
            raise _.error('No session_id defined in session')
        self.sessions[session_id] = json.dumps(session)

    async def load_session(self, session_id):
        session = self.sessions.get(session_id, None)
        if not session:
            return None
        session = json.loads(session)
        if await _.wait(_.application.is_session_expired(session, self._expires)):
            return None
        return session

    def clear_session(self, session_id):
        self.sessions.pop(session_id, None)


class MemorySessions(_.handlers.Protected):
    @_.auth.protected
    async def get(self, session_id=None):
        if session_id:
            session = self._sessions[session_id]
            if not session:
                raise _.HTTPError(404)
            session = json.loads(session)
            self.write(session)
        else:
            data = []
            for session_id in self._sessions:
                session = self._sessions[session_id]
                data.append(json.loads(session))
            self.write({'data':data})

    @_.auth.protected
    async def delete(self, session_id=None):
        self.set_status(204)
        if session_id:
            del self._sessions[session_id]
            callback = getattr(_.application, f'on_{self._component}_delete', None)
            if callback is None:
                callback = getattr(_.application, 'on_memory_delete', None)
            if callback:
                await _.wait(callback(self._component, session_id))
