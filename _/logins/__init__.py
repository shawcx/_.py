
import urllib

import tornado.web

import _


class Login(tornado.web.RequestHandler):
    @classmethod
    async def _(cls, component_name, **kwds):
        # create a dynamic child class with kwds from the ini file
        # add a reference to the component name accessible by the new type
        members = _.prefix(kwds)
        members['_component'] = component_name
        login_cls = type(cls.__name__, (cls,), members)
        try:
            await login_cls.init(component_name, **kwds)
        except TypeError as e:
            raise _.error('%s', e)
        _.logins[component_name] = login_cls
        _.application._login_handler('login', login_cls)

    @classmethod
    async def init(cls, component_name, **kwds):
        pass

    @classmethod
    async def args(cls, component_name):
        pass

    @classmethod
    async def check(cls, username, password):
        raise NotImplementedError

    def initialize(self):
        self.next_url = self.get_argument('next', '/')
        self.redirect_uri = f'{self.request.protocol}://{self.request.host}/login/{self._component}?next={self.next_url}'

    async def on_login_success(self, user):
        fn = getattr(self.application, f'on_{self._component}_login_success', self.application.on_login_success)
        try:
            session = await _.wait(fn(self, user))
            await _.wait(_.sessions.save_session(session))
            self.set_secure_cookie('session_id', session['session_id'], expires_days=1)
        except NotImplementedError:
            raise _.HTTPError(500, 'on_login_success method not implemented') from None
        self.redirect(self.next_url)

    async def on_login_failure(self, message='Invalid Login'):
        fn = getattr(self.application, f'on_{self._component}_login_failure', self.application.on_login_failure)
        await _.wait(fn(self._component))

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
    async def get(self):
        session_id = self.get_secure_cookie('session_id', max_age_days=1)

        if session_id:
            session_id = session_id.decode('utf-8')
            await _.wait(self.application.on_logout(session_id))
            self.session = await _.wait(_.sessions.clear_session(session_id))

        self.clear_cookie('session_id')
        self.redirect(self.get_argument('next', '/'))
