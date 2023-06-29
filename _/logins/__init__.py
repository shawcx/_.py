
import urllib

import tornado.web

import _


class Login(tornado.web.RequestHandler):
    @classmethod
    async def _(cls, name, **kwds):
        # create a dynamic child class with kwds from the ini file
        # add a reference to the component name accessible by the new type
        members = _.prefix(kwds)
        members['_name'] = name
        cls = type(name, (cls,), members)
        try:
            await cls.init(name, **kwds)
        except TypeError as e:
            raise _.error('%s', e)
        _.logins[name] = cls
        _.application._login_handler('login', cls)

    @classmethod
    async def init(cls, name):
        pass

    @classmethod
    async def args(cls, name):
        pass

    @classmethod
    async def check(cls, username, password):
        raise NotImplementedError

    def initialize(self):
        self.next_url = self.get_argument('next', '/')
        self.redirect_uri = f'{self.request.protocol}://{self.request.host}/login/{self._name}?next={self.next_url}'

    async def on_login_success(self, record):
        fn = getattr(self.application, f'on_{self._name}_login', self.application.on_login)
        try:
            session = await _.wait(fn(self, record))
            await _.wait(_.sessions.save_session(session))
            self.set_secure_cookie('session_id', session['session_id'], expires_days=1)
        except NotImplementedError:
            raise _.HTTPError(500, 'on_login method not implemented') from None
        self.redirect(self.next_url)

    async def on_login_failure(self, message='Invalid Login'):
        url = self.get_login_url()
        url += "?" + urllib.parse.urlencode(dict(message=message, next_url=self.next_url))
        self.clear_cookie('session_id')
        self.redirect(url)


class LoginPage(tornado.web.RequestHandler):
    def initialize(self, template='login', **kwds):
        self.kwds = kwds
        self.template = template + '.html'

    def get(self, template=None):
        template = template + '.html' if template else self.template
        message  = self.get_argument('message', None)
        next_url = self.get_argument('next',    '/')
        self.render(template, message=message, next_url=next_url, **self.kwds)


class Logout(tornado.web.RequestHandler):
    def get(self):
        self.clear_cookie('session_id')
        self.redirect(self.get_argument('next', '/'))
