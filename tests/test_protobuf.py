#
# Set UNDERSCORE_TEST_POSTGRES to a URL such as
# postgresql://user:password@127.0.0.1:5432/db to also run against Postgres.
# The tests drop and recreate the public schema of that database.
#

import json
import os
import shutil
import subprocess
import textwrap
import urllib.parse

import pytest

from conftest import ROOT

pytest.importorskip('google.protobuf')
if not shutil.which('protoc'):
    pytest.skip('protoc not installed', allow_module_level=True)

PROTO = '''
    syntax = "proto3";

    package pbt;

    import "pbt/Protobuf.proto";

    message Person {
        string name = 1 [(pkey) = true];
        int32  age  = 2;
    }

    message Order {
        option (id) = 'order_id';
        message Line {
            string sku = 1;
            int32  qty = 2;
        }
        string        customer = 1;
        repeated Line lines    = 2;
    }

    message Tags {
        option (no_table) = true;
        repeated string tags = 1;
    }
    '''

APP = '''
    import json
    import sqlalchemy
    import _

    class App(_.Application):
        async def initialize(self):
            pb, db = _.pb, _.db
            out = dict(containers=sorted(k for k,v in pb.items() if isinstance(v, _.Container)))

            person = pb.Person._from_dict(dict(name='alice', age=30))
            out['person_binary'] = pb.Person._from_binary(person._as_binary())._as_dict()

            out['tags_json'] = json.loads(pb.Tags._from_dict(dict(tags=['a','b']))._as_json())

            if _.config.getboolean('pb', 'relational'):
                order = pb.Order()
                order.customer = 'c'
                line = pb.Order._lines()
                line.sku = 's1'
                line.qty = 1
                order.lines = [line]
                await db.insert(order)
                order_id = (await db.find(pb.Order))[0].order_id
                out['deleted'] = await db.delete(pb.Order, order_id)
                async with db.engine.connect() as conn:
                    lines = sqlalchemy.text('SELECT COUNT(*) FROM "Order_lines"')
                    out['orphans'] = (await conn.execute(lines)).scalar()

            print(json.dumps(out))
            self.stop()

    App.main()
    '''

PACKAGE = '''
    import json
    import os
    from . import Test_pb2
    from . import sub
    '''


def backends():
    yield 'sqlite'
    if os.environ.get('UNDERSCORE_TEST_POSTGRES'):
        yield 'postgres'


def database_ini(backend, tmp_path):
    if backend == 'sqlite':
        return f'[databases]\ndb = sqlite\n\n[db]\ndatabase = {tmp_path}/pb.db\n'
    url = urllib.parse.urlsplit(os.environ['UNDERSCORE_TEST_POSTGRES'])
    reset = f'DROP SCHEMA public CASCADE; CREATE SCHEMA public'
    subprocess.run(['psql', '-q', os.environ['UNDERSCORE_TEST_POSTGRES'], '-c', reset],
        check=True, capture_output=True)
    return (
        '[databases]\ndb = postgres\n\n[db]\n'
        f'host = {url.hostname}\nport = {url.port or 5432}\n'
        f'username = {url.username}\npassword = {url.password}\n'
        f'database = {url.path.lstrip("/")}\n'
        )


@pytest.fixture(params=list(backends()))
def run_proto_app(request, run_app, tmp_path):
    def _run(relational):
        (tmp_path / 'pbt' / 'sub').mkdir(parents=True)
        shutil.copy(os.path.join(ROOT, '_', 'records', 'Protobuf.proto'), tmp_path / 'pbt')
        files = {
            'pbt/Test.proto'      : PROTO,
            'pbt/sub/Sub.proto'   : 'syntax = "proto3";\npackage pbt.sub;\nmessage Inner { string x = 1; }\n',
            'pbt/__init__.py'     : PACKAGE,
            'pbt/sub/__init__.py' : 'from . import Sub_pb2\n',
            }
        for name,content in files.items():
            (tmp_path / name).write_text(textwrap.dedent(content))
        subprocess.run(
            ['protoc', '-I.', '--python_out=.',
                'pbt/Protobuf.proto', 'pbt/Test.proto', 'pbt/sub/Sub.proto'],
            cwd=tmp_path, check=True)
        ini = database_ini(request.param, tmp_path) + textwrap.dedent(f'''
            [records]
            pb = protobuf

            [pb]
            module     = pbt
            database   = db
            options    = Protobuf
            handlers   = false
            relational = {str(relational).lower()}
            ''')
        result = run_app({'app.py' : APP, 'app.ini' : ini})
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert lines, result.stderr
        return json.loads(lines[-1])
    return _run


@pytest.mark.parametrize('relational', [False, True])
def test_protobuf_records(run_proto_app, relational):
    out = run_proto_app(relational)

    # only the package's own submodules become containers, not json or os
    assert out['containers'] == ['sub']
    # a declared primary key survives the binary round-trip
    assert out['person_binary'] == dict(name='alice', age=30)
    # repeated scalars are plain lists so they encode as JSON
    assert out['tags_json'] == dict(tags=['a','b'])

    if relational:
        # deleting by id cascades to child tables in the database
        assert out['deleted'] == 1
        assert out['orphans'] == 0
