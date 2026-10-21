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


def test_sqlite_uuid_type(run_app, tmp_path):
    result = run_app({
        'app.py'  : '''
            import uuid
            import sqlalchemy
            import _

            class App(_.Application):
                async def initialize(self):
                    table = sqlalchemy.Table('t', sqlalchemy.MetaData(),
                        sqlalchemy.Column('u', _.db.UUID()))
                    value = uuid.uuid4()
                    async with _.db.engine.begin() as conn:
                        await conn.run_sync(table.metadata.create_all)
                        await conn.execute(table.insert().values(u=value))
                        loaded = (await conn.execute(sqlalchemy.select(table.c.u))).scalar()
                    print(loaded == value)
                    self.stop()

            App.main()
            ''',
        'app.ini' : f'[databases]\ndb = sqlite\n\n[db]\ndatabase = {tmp_path}/db.db\n',
        })
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True', result.stderr


def test_json_encoder(run_app):
    result = run_app({'app.py' : '''
        import datetime
        import json
        import uuid
        import _

        class App(_.Application):
            def initialize(self):
                utc = datetime.timezone.utc
                print(json.dumps(dict(
                    datetime  = datetime.datetime(2024, 5, 1, 12, 0, 0, 500, tzinfo=utc),
                    naive     = datetime.datetime(2024, 5, 1, 12, 0),
                    date      = datetime.date(2024, 5, 1),
                    time      = datetime.time(12, 30),
                    timedelta = datetime.timedelta(minutes=1, seconds=30),
                    bytes     = b'hi',
                    uuid      = uuid.UUID(int=1),
                    ), cls=_.JSONEncoder))
                self.stop()

        App.main()
        '''})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(
        datetime  = '2024-05-01T12:00:00.000500+00:00',
        naive     = '2024-05-01T12:00:00',
        date      = '2024-05-01',
        time      = '12:30:00',
        timedelta = 90.0,
        bytes     = 'aGk=',
        uuid      = '00000000-0000-0000-0000-000000000001',
        )
