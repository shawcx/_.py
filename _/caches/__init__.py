#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import _


class Cache:
    @classmethod
    async def _(cls, name, **kwds):
        # create a dynamic child class with kwds from the ini file
        try:
            members = dict(_.config['sessions'])
        except KeyError:
            members = {}

        members['expires']  = int(members.get('expires',  24))
        members['interval'] = int(members.get('interval', 60))
        members.update(kwds)

        # instantiate the derived class
        self = type(cls.__name__, (cls,), _.prefix(members))()
        _.caches[name] = self
        await self.init(name, **kwds)

    async def init(self, **kwds):
        pass

    async def close(self):
        pass

    async def cookie_secret(self):
        raise NotImplementedError

    def save_session(self, session):
        try:
            return session['session_id']
        except KeyError:
            raise _.error('No session_id defined in session')

    async def load_session(self, session_id):
        raise NotImplementedError


class Handler(_.handlers.Protected):
    pass
