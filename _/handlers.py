#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import tornado.web

import _


class Template(tornado.web.RequestHandler):
    def initialize(self, template='index', **kwds):
        self.kwds = kwds
        self.template = template + '.html'

    def get(self, template=None, *args):
        template = template + '.html' if template else self.template
        self.render(template, extra=args, **self.kwds)


class Protected(Template):
    async def prepare(self):
        if _.sessions is None:
            raise _.HTTPError(500, 'No session component specified')

        self.session = None
        session_id = self.get_secure_cookie('session_id', max_age_days=1)
        if session_id:
            session_id = session_id.decode('utf-8')
            self.session = await _.wait(_.sessions.load_session(session_id))

    def get_current_user(self):
        return self.session

    @_.auth.current_user
    def get(self, template=None, *args):
        super().get(template, *args)
