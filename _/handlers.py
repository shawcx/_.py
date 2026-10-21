#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import os

import tornado.web

import _


class Handler(tornado.web.RequestHandler):
    '''base for _ handlers, writes dicts and lists as JSON with _.JSONEncoder so
       records, bytes and datetimes can be written directly'''
    def write(self, chunk):
        if isinstance(chunk, (dict, list)):
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            # like tornado, escape </ so the JSON is safe inside a script tag
            chunk = _.json_encode(chunk).replace('</', '<\\/')
        super().write(chunk)


class Template(Handler):
    def initialize(self, template='index', **kwds):
        self.kwds = kwds
        self.template = template + '.html'

    def get(self, template=None, *args):
        template = template + '.html' if template else self.template
        # the template name can come from the URL, so a missing one is not found
        if not os.path.exists(os.path.join(self.get_template_path(), template)):
            raise _.HTTPError(404)
        self.render(template, extra=args, **self.kwds)


class Protected(Template):
    async def prepare(self):
        if _.sessions is None:
            raise _.HTTPError(500, 'No session component specified')

        self.session = None
        session_id = self.get_signed_cookie('session_id', max_age_days=1)
        if session_id:
            session_id = session_id.decode('utf-8')
            self.session = await _.wait(_.sessions.load_session(session_id))

    def get_current_user(self):
        return self.session

    @_.auth.current_user
    def get(self, template=None, *args):
        super().get(template, *args)
