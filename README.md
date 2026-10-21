
underscore.py
-------------

```INI
[myapp]
address = 0.0.0.0
port    = 8080
```

```Python
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

Schema changes
--------------

Tables for records are created when the database is empty. After that, each
start compares the models (for example your `.proto` messages) with the
database and refuses to run if they differ:

```
ERROR    Database "store" differs from the schema:
  ALTER TABLE "Reports_multiple" ADD COLUMN _position INTEGER
Run with --store-migrate to apply them
```

`--<database>-migrate` applies changes that can't lose data. Drops and type
changes are printed as SQL to run by hand. This needs `alembic`
(`pip install underscorepy[migrations]`); set `check_schema = false` in the
database's section to skip the check.
