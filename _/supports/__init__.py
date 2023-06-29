#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import os

import _


class Support:
    @classmethod
    async def _(cls, name, **kwds):
        self = cls()
        _.supports[name] = self
        self.root = os.path.dirname(__file__)
        self.root = os.path.abspath(self.root)
        await self.init(name, **kwds)

    @classmethod
    async def init(cls, name):
        pass

    @classmethod
    async def args(cls, name):
        pass
