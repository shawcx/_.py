
import logging

import _.websockets


class Socket(_.websockets.Protected):
    def on_message(self, msg):
        logging.info('websocket: %s', msg)
        self.write_message(msg)
