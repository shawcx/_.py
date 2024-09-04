#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import os
import hashlib
import base64

import _


# this is opening the file and scanning it for every login, which is fine
# for small projects with a limited number of users.
#
# Passwords can be managed with Apache's htpasswd program


class Htpasswd(_.logins.Login):
    @classmethod
    async def init(cls, name, **kwds):
        pass

    @classmethod
    async def args(cls, name):
        pass

    async def post(self):
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')
        password = password.encode('utf-8')
        password = b'{SHA}' + base64.b64encode(hashlib.sha1(password).digest())
        password = password.decode('ascii')

        path = _.paths(_.config.get('simple', 'path'))

        fp = open(path, 'r')
        for line in fp:
            if not line:
                continue
            entry,hash = line.split(':', 1)

            if entry != username:
                continue

            if hash.rstrip() != password:
                break

            await self.on_login_success(user)
            return

        await self.on_login_failure()
