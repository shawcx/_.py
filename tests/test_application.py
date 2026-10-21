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
