#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import tornado.websocket

import _


class WebSocket(tornado.websocket.WebSocketHandler):
    '''Tweak the default WebSocket behavior for more responsive behavior'''

    def initialize(self, websockets):
        self.websockets = websockets

    def check_origin(self, origin):
        if _.args.debug:
            return True
        # TODO: let app specify origin policy
        return True

    def open(self):
        self.set_nodelay(True)
        self.websockets[id(self)] = self

    def on_close(self):
        self.websockets.pop(id(self), None)


class Protected(WebSocket):
    '''Require a valid user session to establish WebSocket connection'''

    async def prepare(self):
        self.session_id = self.get_secure_cookie('session_id')
        if not self.session_id:
            raise _.HTTPError(403)
        self.session_id = self.session_id.decode('utf-8')

        self.session = await _.wait(_.sessions.load_session(self.session_id))
        if not self.session:
            raise _.HTTPError(403)


class EchoMixin:
    '''Reflect incoming messages to all other connected WebSockets'''

    def on_message(self, msg):
        for ws in self.websockets.values():
            if ws is self:
                continue
            ws.write_message(msg)
