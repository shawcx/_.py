APP = '''
    import os
    import signal
    import _

    class App(_.Application):
        def initialize(self):
            os.kill(os.getpid(), signal.SIGTERM)

        def on_sigterm(self, signum, frame):
            print('on_sigterm', signum == signal.SIGTERM)

        def on_stop(self):
            print('on_stop')

    App.main()
    '''


def test_sigterm_stops_app(run_app):
    result = run_app({'app.py' : APP})
    assert result.returncode == 0, result.stderr
    assert result.stdout.split('\n')[:2] == ['on_sigterm True', 'on_stop']
    assert 'Terminating app on SIGTERM signal' in result.stderr


def test_records_in_plain_application(run_app, tmp_path):
    # handlers are only served by a WebApplication but records still load
    result = run_app({
        'app.py'    : '''
            import _

            class App(_.Application):
                def initialize(self):
                    print(sorted(_.data.keys()))
                    self.stop()

            App.main()
            ''',
        'models.py' : 'class thing:\n    x : int\n',
        'app.ini'   : f'''
            [databases]
            db = sqlite

            [db]
            database = {tmp_path}/db.db

            [records]
            data

            [data]
            module   = models
            database = db
            ''',
        })
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['thing']"


def test_missing_template_is_not_found(tmp_path):
    from conftest import Server
    server = Server(tmp_path, {
        'app.py' : '''
            import _

            class App(_.WebApplication):
                def initialize(self):
                    self.patterns = [(r'/([a-z]*)', _.handlers.Template)]

            App.main()
            ''',
        'templates/index.html' : 'hello',
        })
    try:
        assert server.request('GET', '/') == (200, b'hello')
        assert server.request('GET', '/index') == (200, b'hello')
        # page names come from the URL, so a missing template is a 404, not a 500
        assert server.request('GET', '/missing')[0] == 404
    finally:
        server.stop()


def test_json_module_is_not_patched(run_app):
    result = run_app({'app.py' : '''
        import json
        import _
        import _.records.protobuf
        import google.protobuf.timestamp_pb2

        class App(_.Application):
            def initialize(self):
                try:
                    json.dumps(b'x')
                    print('patched')
                except TypeError:
                    print('untouched')
                stamp = google.protobuf.timestamp_pb2.Timestamp(seconds=1)
                print(_.json_encode(dict(b=b'x', t=stamp)))
                self.stop()

        App.main()
        '''})
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['untouched', '{"b": "eA==", "t": "1970-01-01T00:00:01Z"}']


def test_handlers_write_json(tmp_path):
    import asyncio
    import tornado.websocket
    from conftest import Server
    server = Server(tmp_path, {
        'app.py' : '''
            import datetime
            import _
            import _.websockets

            VALUE = dict(b=b'x', d=datetime.date(2024, 5, 1), script='</script>')

            class Data(_.handlers.Handler):
                def get(self):
                    self.write(VALUE)

            class Socket(_.websockets.WebSocket):
                def on_message(self, msg):
                    self.write_message(VALUE)

            class App(_.WebApplication):
                def initialize(self):
                    self.patterns = [(r'/data', Data), (r'/ws', Socket)]

            App.main()
            ''',
        })
    try:
        code,body = server.request('GET', '/data')
        assert code == 200
        # </ is escaped so the JSON can sit inside a script tag
        assert body == b'{"b": "eA==", "d": "2024-05-01", "script": "<\\/script>"}'

        async def ws():
            conn = await tornado.websocket.websocket_connect(f'ws://127.0.0.1:{server.port}/ws')
            await conn.write_message('hi')
            message = await conn.read_message()
            conn.close()
            return message
        assert asyncio.run(ws()) == '{"b": "eA==", "d": "2024-05-01", "script": "</script>"}'
    finally:
        server.stop()
