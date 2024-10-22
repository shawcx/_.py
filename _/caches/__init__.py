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
    async def _(cls, component_name, **kwds):
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
        _.caches[component_name] = self
        await self.init(component_name, **kwds)

    async def init(self, **kwds):
        pass

    async def close(self):
        pass

    async def cookie_secret(self):
        raise NotImplementedError

    def save_session(self, session):
        raise NotImplementedError

    def load_session(self, session_id):
        raise NotImplementedError

    def clear_session(self, session_id):
        raise NotImplementedError


class Handler(_.handlers.Protected):
    pass
