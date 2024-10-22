#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import tornado.auth
import tornado.httpclient

import _


# for Google and Gitlab the GoogleOAuth2Mixin is a good starting point
class OAuth2(tornado.auth.GoogleOAuth2Mixin):
    extra = None

    @classmethod
    async def init(cls, component_name, client_id, client_secret, **kwds):
        _.application.settings[cls._OAUTH_SETTINGS_KEY] = {
            'key'    : client_id,
            'secret' : client_secret,
        }

    async def get(self):
        code = self.get_argument('code', None)
        if not code:
            # make the initial request to the OAuth2 service
            self.authorize_redirect(
                redirect_uri  = self.redirect_uri,
                client_id     = self._client_id,
                scope         = self.scope,
                response_type = 'code',
                extra_params  = self.extra
                )
        else:
            try:
                # the OAuth2 service will callback with a code
                # pass it to the get_authenticated_user function defined
                # in GitLabAuthMixin
                self.oauth = await self.get_authenticated_user(
                    redirect_uri = self.redirect_uri,
                    code         = code,
                    )
                user = await self.oauth2_request(
                    self._OAUTH_USERINFO_URL,
                    access_token = self.oauth["access_token"]
                    )
                await self.on_login_success(user)
            except tornado.httpclient.HTTPClientError as e:
                await self.on_login_failure(str(e))
