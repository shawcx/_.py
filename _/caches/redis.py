#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import json
import os

import _

try:
    import redis.asyncio as redis
except ImportError:
    raise _.error('Missing redis module with asyncio support')


class Redis(_.caches.Cache):
    async def init(self, name, **kwds):
        if 'socket_connect_timeout' not in kwds:
            kwds['socket_connect_timeout'] = 3

        if 'socket_timeout' not in kwds:
            kwds['socket_timeout'] = 3

        self.redis = redis.Redis(**kwds)
        await self.redis.ping()

        members = dict(
            name  = name,
            redis = self.redis,
            )
        subclass = type(name, (RedisSessions,), _.prefix(members))
        _.application._record_handler('sessions', subclass)

    async def close(self):
        await self.redis.close()
        self.redis = None

    async def cookie_secret(self):
        secret = await self.redis.get('cookie_secret')
        if not secret:
            secret = base64.b64encode(os.urandom(32))
            await self.redis.set('cookie_secret', secret)
        return secret

    async def save_session(self, session):
        session_id = super().save_session(session)
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.set(f'session/{session_id}', json.dumps(session))
            await pipe.expire(f'session/{session_id}', self._expires * 3600)
            await pipe.execute()

    async def load_session(self, session_id):
        session = await self.redis.get(f'session/{session_id}')
        if not session:
            return None
        return json.loads(session)

    # fall through for calling redis functions directly
    def __getattr__(self, attr):
        return getattr(self.redis, attr)


class RedisSessions(_.handlers.Protected):
    @_.auth.protected
    async def get(self, session_id=None):
        if session_id:
            session = await self._redis.get(f'session/{session_id}')
            if not session:
                raise _.HTTPError(404)
            session = json.loads(session)
            self.write(session)
        else:
            data = []
            session_ids = await self._redis.keys('session/*')
            for session_id in session_ids:
                session = await self._redis.get(session_id)
                data.append(json.loads(session))
            data.sort(key=lambda d: d['time'])
            self.write({'data':data})

    @_.auth.protected
    async def delete(self, session_id=None):
        self.set_status(204)
        if session_id:
            await self._redis.delete(f'session/{session_id}')
            callback = getattr(_.application, f'on_{self._name}_delete', None)
            if callback is None:
                callback = getattr(_.application, 'on_redis_delete', None)
            if callback:
                await _.wait(callback(self._name, session_id))
