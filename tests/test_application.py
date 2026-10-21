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
