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
    async def _(cls, component_name, **kwds):
        self = cls()
        _.supports[component_name] = self
        self.root = os.path.dirname(__file__)
        self.root = os.path.abspath(self.root)
        await self.init(component_name, **kwds)

    @classmethod
    async def init(cls, component_name):
        pass

    @classmethod
    async def args(cls, component_name):
        pass
