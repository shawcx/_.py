#
# (c) 2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

# This is for logging into GitLab servers and serve as an example
# of implementing an OAuth2 handler for any service that supports it

# For admins go to http(s)://your.gitlab.server/admin/applications and click "New application"
# For users  go to http(s)://your.gitlab.server/-/profile/applications
# For groups go to http(s)://your.gitlab.server/groups/(group)/-/settings/applications
#
# Pick a "Name" for the application
#
# Set the "Redirect URI" to http(s)://your.underscore.app/login/gitlab
# (or replace gitlab at the end with whatever unique name assigned in the ini file)
#
# Select Trusted and Confidential
#
# "read_user" is the only scope required by this login plugin
#
# Click "Save application"
#
# Copy "Application ID" as client_id and copy "Secret" as client_secret in the ini
#
# Click "Continue"
#
# Your underscore app can now authenticate via your GitLab server


import _

from .oauth2 import OAuth2


class GitLab(OAuth2, _.logins.Login):
    @classmethod
    async def init(cls, name, gitlab, **kwds):
        cls.scope = ['read_user']

        cls._OAUTH_AUTHORIZE_URL    = f'{gitlab}/oauth/authorize'
        cls._OAUTH_ACCESS_TOKEN_URL = f'{gitlab}/oauth/token'
        cls._OAUTH_USERINFO_URL     = f'{gitlab}/api/v4/user'
        cls._OAUTH_SETTINGS_KEY     = f'{name}_oauth'

        await super().init(name, **kwds)
