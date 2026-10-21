import json

APP = '''
    import json
    import _

    class App(_.Application):
        async def initialize(self):
            print(json.dumps(dict(
                databases = sorted(_.databases.keys()),
                store     = type(_.store).__name__,
                widget    = _.supports['w'].kwds,
                )))
            self.stop()

    App.main()
    '''

WIDGET = '''
    import _.supports

    class Widget(_.supports.Support):
        async def init(self, component_name, **kwds):
            self.kwds = kwds
    '''


def test_component_loading(run_app, tmp_path):
    result = run_app({
        'app.py'    : APP,
        'widget.py' : WIDGET,
        'app.ini'   : f'''
            [databases]
            store = sqlite
            sqlite

            [store]
            database = {tmp_path}/store.db

            [sqlite]
            database = {tmp_path}/sqlite.db

            [supports]
            w = +widget.Widget

            [w]
            colour = blue
            ''',
        })
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])

    # aliased and bare keys both create instances named after the key
    assert loaded['databases'] == ['sqlite', 'store']
    # databases are also exposed as _.<name>
    assert loaded['store'] == 'SQLite'
    # + imports a third-party class and passes it the [w] section
    assert loaded['widget'] == {'colour': 'blue'}


def test_unknown_component(run_app):
    result = run_app({
        'app.py'  : APP,
        'app.ini' : '[supports]\nnope\n',
        })
    assert 'Unknown module: _.supports.nope' in result.stderr
    assert result.stdout == ''
