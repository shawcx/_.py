#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import time
import logging

import tornado.escape

import _


try:
    import ldap
except ImportError:
    raise _.error('Missing LDAP module')


class Slap(_.logins.Login):
    @classmethod
    async def init(cls, component_name, **kwds):
        _.argparser.add_argument(f'--{component_name}-list-users',
            action='store_true',
            help='list users'
            )

    @classmethod
    async def args(cls, component_name):
        pass

    @classmethod
    async def check(cls, username, password):
        try:
            dn = cls.dn.format(username)
            ldap_server = ldap.initialize(cls.uri)
            ldap_server.bind_s(dn, password)
            ldap_server.unbind()
            return True
        except ldap.NO_SUCH_OBJECT:
            logging.warn('Could not find record for user: %s', username)
        except ldap.INVALID_CREDENTIALS:
            logging.warn('Invalid credentials for user: %s', username)
        except ldap.SERVER_DOWN:
            logging.error('Could not connect to LDAP server: %s', cls.uri)
        return None

    async def post(self):
        username = self.get_argument('username', '')
        username = tornado.escape.xhtml_escape(username)
        password = self.get_argument('password', '')

        ok = await self.check(username, password)
        if ok:
            await self.on_login_success({'username':username})
        else:
            await self.on_login_failure()
