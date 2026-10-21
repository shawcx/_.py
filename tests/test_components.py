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
                bare      = sorted(_.supports.keys()),
                cache     = sorted(_.caches.keys()),
                )))
            self.stop()

    App.main()
    '''

WIDGET = '''
    import _.caches
    import _.supports

    class Widget(_.supports.Support):
        async def init(self, component_name, **kwds):
            self.kwds = kwds

    # rely on the base class init accepting the INI options
    class BareSupport(_.supports.Support):
        pass

    class BareCache(_.caches.Cache):
        pass
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
            b = +widget.BareSupport

            [w]
            colour = blue

            [b]
            option = 1

            [caches]
            c = +widget.BareCache

            [c]
            option = 1
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
    # base init methods accept the options passed by the loader
    assert loaded['bare'] == ['b', 'w']
    assert loaded['cache'] == ['c']


def test_unknown_component(run_app):
    result = run_app({
        'app.py'  : APP,
        'app.ini' : '[supports]\nnope\n',
        })
    assert 'Unknown module: _.supports.nope' in result.stderr
    assert result.stdout == ''
