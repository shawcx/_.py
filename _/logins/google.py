#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import _

from .oauth2 import OAuth2


class Google(OAuth2, _.logins.Login):
    @classmethod
    async def init(cls, name, **kwds):
        cls.scope = ['email']
        cls.extra = {'approval_prompt': 'auto'}

        await super().init(name, **kwds)
