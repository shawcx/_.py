#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import tornado.web
import tornado.websocket

import _

class Broadcast(tornado.websocket.WebSocketHandler):
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

    def on_message(self, msg):
        for ws in self.websockets:
            if ws is self:
                continue
            ws.write_message(msg)


class Protected(Broadcast):
    def open(self):
        self.session_id = self.get_secure_cookie('session_id')
        if not self.session_id:
            self.close(4004)
            return

        self.set_nodelay(True)
        self.websockets[self.session_id] = self

    def on_close(self):
        self.websockets.pop(self.session_id, None)
