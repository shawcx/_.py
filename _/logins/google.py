#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import _


class Google( _.logins.OAuth2, _.logins.Login):
    @classmethod
    async def init(cls, name, **kwds):
        cls.scope = ['email']
        cls.extra = {'approval_prompt': 'auto'}

        await super(Google, cls).init(name, **kwds)
