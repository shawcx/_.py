#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import binascii
import functools
import hashlib
import urllib.parse

import _


# based on tornado.web.authenticated
def _next(handler):
    if handler.request.method in ("GET","HEAD"):
        url = handler.get_login_url()
        if "?" not in url:
            if urllib.parse.urlsplit(url).scheme:
                next_url = handler.request.full_url()
            else:
                next_url = handler.request.uri
            url += "?" + urllib.parse.urlencode(dict(next=next_url))
        handler.redirect(url)
    else:
        raise _.HTTPError(403)


# generic decorator to callback to a function
# return true to allow the method to be called
# return false to block the method
def filter(filter_func):
    def _filter(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwds):
            if filter_func(self):
                return method(self, *args, **kwds)
            _next(self)
        return wrapper
    return _filter


# same as above but pass the current_user session to the function
# blocks when no session is associated with the request
# return true to allow the method to be called
# return false to block the method
def filter_user(filter_func):
    def _filter_user(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwds):
            if self.current_user:
                if filter_func(self.current_user):
                    return method(self, *args, **kwds)
            _next(self)
        return wrapper
    return _filter_user


# inteded to be used by underscore apps to check that any user is logged in
current_user = filter_user(lambda current_user: True)

# intended to be over-ridden before components are loaded for more fine-grain
# control over access to component handlers
protected    = filter_user(lambda current_user: True)


# implement old school user/name password prompt
# useful for command-line tools to pass as part of the URL
def basic(realm='Authentication'):
    def basic_auth(method):
        @functools.wraps(method)
        async def wrapper(self, *args, **kwds):
            auth = self.request.headers.get('Authorization', '')
            if auth.startswith('Basic '):
                auth = binascii.a2b_base64(auth[6:]).decode('utf-8')
                username,password = auth.split(':', 1)
                component = _.config.get(_.name, 'basic', fallback=None)
                if not component:
                    raise _.HTTPError(500, 'No component specified for basic auth')
                try:
                    login = _.logins[component]
                except KeyError:
                    raise _.HTTPError(500, 'Invalid component specified for basic auth')
                success = await login.check(username, password)
                if success:
                    return method(self, *args, **kwds)
            self.set_status(401)
            self.set_header('WWW-Authenticate', f'Basic realm={realm}')
            self.finish()
        return wrapper
    return basic_auth


def simple_hash(value):
    value = value.encode('utf-8')
    for i in range(99999):
        value = hashlib.sha512(value).digest()
    return base64.b64encode(value).decode('ascii')


__all__ = _.all()
