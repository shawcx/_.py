#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import datetime

import _

import tornado.auth
import tornado.web


class Facebook(_.logins.Login, tornado.auth.FacebookGraphMixin):
    @classmethod
    async def init(cls, component_name, **kwds):
        cls.extra = {"scope": "read_stream,offline_access"}

    async def get(self):
        try:
            code = self.get_argument('code', None)
            if not code:
                self.authorize_redirect(
                    redirect_uri  = self.redirect_uri,
                    client_id     = self.client_id,
                    extra_params  = self.extra
                    )
            else:
                user = await self.get_authenticated_user(
                    redirect_uri  = self.redirect_uri,
                    client_id     = self.client_id,
                    client_secret = self.client_secret,
                    code          = code,
                    )
            await self.on_login_success(user)
        except tornado.httpclient.HTTPClientError as e:
            await self.on_login_failure(str(e))
