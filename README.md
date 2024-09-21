
underscore.py
-------------

```
[myapp]
address = 0.0.0.0
port    = 8080
```

```
import _
import _.websockets

class Echo(_.websockets.WebSocket):
    def on_message(self, msg):
        print('Echo:', msg)
        self.write_message(msg)

class MyApp(_.Application):
    def initialize(self):
        self.patterns = [
            ( r'/ws',       Echo                ),
            ( r'/([a-z]*)', _.handlers.Template ),
            ]

MyApp.main()
```

Look at the skeleton directory for a more complete example application.
