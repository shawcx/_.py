import json
import sqlite3

import pytest

from conftest import backends, database_ini

pytest.importorskip('alembic')

# list the people, adding alice the first time
APP = '''
    import json
    import _

    class App(_.Application):
        async def initialize(self):
            if not await _.db.find_one(_.data.person, 'alice'):
                person = _.data.person()
                person(name='alice', age=30)
                await _.db.insert(person)
            print(json.dumps([p._as_dict() for p in await _.db.find(_.data.person)]))
            self.stop()

    App.main()
    '''

V1 = '''
    import _

    @_.data.no_handler
    class person:
        name : str = _.data.pkey()
        age  : int
    '''

# adds a column and a table
V2 = '''
    import _

    @_.data.no_handler
    class person:
        name  : str = _.data.pkey()
        age   : int
        email : str

    @_.data.no_handler
    class pet:
        name : str = _.data.pkey()
    '''

# drops the age column and adds a table
V3 = '''
    import _

    @_.data.no_handler
    class person:
        name : str = _.data.pkey()

    @_.data.no_handler
    class pet:
        name : str = _.data.pkey()
    '''


@pytest.fixture(params=list(backends()))
def run_version(request, run_app, tmp_path):
    reset = [True]
    def _run(models, *args, ini=''):
        result = run_app({
            'app.py'    : APP,
            'models.py' : models,
            'app.ini'   : (
                f'[databases]\ndb = {request.param}\n\n'
                + database_ini(request.param, tmp_path, reset=reset[0]) + ini
                + '\n[records]\ndata\n\n[data]\nmodule = models\ndatabase = db\n'
                ),
            }, *args)
        reset[0] = False
        lines = result.stdout.strip().splitlines()
        result.people = json.loads(lines[-1]) if lines else None
        return result
    return _run


def test_new_database_is_created(run_version):
    result = run_version(V1)
    assert result.people == [dict(name='alice', age=30)], result.stderr


def test_additive_changes_need_migrate(run_version):
    run_version(V1)

    # refuses to start and lists the changes
    result = run_version(V2)
    assert result.people is None
    assert 'Database "db" differs from the schema' in result.stderr
    assert 'ADD COLUMN email' in result.stderr
    assert 'CREATE TABLE pet' in result.stderr
    assert 'Run with --db-migrate to apply them' in result.stderr

    # applies them, keeping the existing rows
    result = run_version(V2, '--db-migrate')
    assert result.people == [dict(name='alice', age=30, email=None)], result.stderr
    assert 'ADD COLUMN email' in result.stderr

    # and then matches
    result = run_version(V2)
    assert result.people == [dict(name='alice', age=30, email=None)], result.stderr


def test_destructive_changes_are_not_applied(run_version):
    run_version(V1)

    result = run_version(V3, '--db-migrate')
    assert result.people is None
    assert 'must be applied by hand' in result.stderr
    assert 'DROP COLUMN age' in result.stderr
    assert 'Then run with --db-migrate to apply the rest' in result.stderr

    # nothing was applied, not even the new table
    result = run_version(V1)
    assert result.people == [dict(name='alice', age=30)], result.stderr


def test_type_change_is_not_applied(run_version):
    run_version(V1)
    result = run_version(V1.replace('age  : int', 'age  : str'), '--db-migrate')
    assert result.people is None
    assert 'must be applied by hand' in result.stderr
    assert 'ALTER COLUMN age' in result.stderr or 'ALTER TABLE person ALTER' in result.stderr


def test_check_schema_off(run_version):
    run_version(V1)
    # starts without checking, so the new column is missing
    result = run_version(V2, ini='check_schema = false\n')
    assert 'differs from the schema' not in result.stderr
    assert 'no such column' in result.stderr or 'does not exist' in result.stderr


MULTI = '''
    import _

    class App(_.Application):
        def initialize(self):
            self.stop()

    App.main()
    '''


def test_databases_have_separate_tables(run_app, tmp_path):
    result = run_app({
        'app.py'    : MULTI,
        'models1.py': 'import _\n\n@_.data1.no_handler\nclass one:\n    x : int\n',
        'models2.py': 'import _\n\n@_.data2.no_handler\nclass two:\n    y : int\n',
        'app.ini'   : f'''
            [databases]
            db1 = sqlite
            db2 = sqlite

            [db1]
            database = {tmp_path}/db1.db

            [db2]
            database = {tmp_path}/db2.db

            [records]
            data1 = data
            data2 = data

            [data1]
            module   = models1
            database = db1

            [data2]
            module   = models2
            database = db2
            ''',
        })
    assert result.returncode == 0, result.stderr

    def tables(name):
        with sqlite3.connect(tmp_path / name) as conn:
            return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))

    assert tables('db1.db') == ['one']
    assert tables('db2.db') == ['two']
