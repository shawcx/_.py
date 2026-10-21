import json
import os
import sqlite3
import shutil
import subprocess
import textwrap

import pytest

from conftest import ROOT, Server, backends, database_ini

pytest.importorskip('google.protobuf')
if not shutil.which('protoc'):
    pytest.skip('protoc not installed', allow_module_level=True)

PROTO = '''
    syntax = "proto3";

    package pbt;

    import "pbt/Protobuf.proto";
    import "google/protobuf/duration.proto";
    import "google/protobuf/struct.proto";
    import "google/protobuf/timestamp.proto";
    import "google/protobuf/wrappers.proto";

    enum Color {
        RED   = 0;
        GREEN = 1;
    }

    message Address {
        string city = 1;
        bytes  code = 2;
        int64  big  = 3;
    }

    message Person {
        string name = 1 [(pkey) = true];
        int32  age  = 2;
    }

    message Everything {
        string              name   = 1 [(pkey) = true];
        repeated int32      scores = 2;
        repeated bytes      blobs  = 3;
        repeated uint64     bigs   = 4;
        repeated string     tags   = 5;
        map<string,int32>   counts = 6;
        map<string,Address> places = 7;
        uint64              huge   = 8;
        Color               color  = 9;
        Address             addr   = 10;
        Address             unset  = 11;
        optional int32      maybe  = 12;
        bytes               blob   = 13;
        double              ratio  = 14;
    }

    message Order {
        option (id) = 'order_id';
        message Line {
            string  sku  = 1;
            int32   qty  = 2;
            Address origin = 3;
        }
        string        customer = 1;
        repeated Line lines    = 2;
        Address       ship     = 3;
    }

    message Tags {
        option (no_table) = true;
        repeated string tags = 1;
    }

    message Event {
        string                      name  = 1 [(pkey) = true];
        google.protobuf.Timestamp   at    = 2;
        google.protobuf.Duration    took  = 3;
        google.protobuf.Int64Value  count = 4;
        google.protobuf.StringValue note  = 5;
        google.protobuf.UInt64Value big   = 6;
        google.protobuf.Struct      meta  = 7;
        google.protobuf.Value       value = 8;
        repeated google.protobuf.Timestamp times = 9;
        google.protobuf.Timestamp   unset = 10;
        google.protobuf.BytesValue  blob  = 11;
    }

    message Owner {
        string name = 1 [(pkey) = true];
    }

    message Pet {
        string         name    = 1 [(pkey) = true];
        string         owner   = 2 [(ref) = "Owner.name"];
        optional int32 age     = 3 [(required) = true];
        Address        home    = 4 [(required) = true];
        string         scratch = 5 [(no_column) = true];
    }
    '''

APP = '''
    import json
    import sqlalchemy
    import google.protobuf.json_format as json_format
    import _
    import pbt.Test_pb2

    MAX = str(2**64 - 1)

    EVERYTHING = dict(
        name   = 'e',
        scores = [1, 2],
        blobs  = ['aGk=', ''],
        bigs   = [MAX, '1'],
        tags   = ['a', 'b'],
        counts = {'x': 1},
        places = {'home': {'city': 'c', 'code': 'AQ==', 'big': '9007199254740993'}},
        huge   = MAX,
        color  = 'GREEN',
        addr   = {'city': 'x'},
        blob   = 'AAE=',
        ratio  = 0.5,
        )

    ORDER = dict(
        customer = 'c',
        lines    = [dict(sku='s1', qty=1, origin={'city': 'f'}), dict(sku='s2', qty=2)],
        ship     = {'city': 'y'},
        )

    def as_json(msg):
        return json_format.MessageToDict(msg, preserving_proto_field_name=True)

    def expected(cls, value):
        return as_json(json_format.ParseDict(value, cls()))

    class App(_.Application):
        async def initialize(self):
            pb, db = _.pb, _.db
            out = dict(containers=sorted(k for k,v in pb.items() if isinstance(v, _.Container)))

            person = pb.Person._from_dict(dict(name='alice', age=30))
            out['person_binary'] = pb.Person._from_binary(person._as_binary())._as_dict()

            out['tags_json'] = json.loads(pb.Tags._from_dict(dict(tags=['a','b']))._as_json())

            # every field type survives the database and binary round-trips
            await db.insert(pb.Everything._from_dict(EVERYTHING))
            loaded = await db.find_one(pb.Everything, 'e')
            out['everything'] = as_json(loaded._as_pb()) == expected(pbt.Test_pb2.Everything, EVERYTHING)
            binary = pb.Everything._from_binary(loaded._as_binary())
            out['everything_binary'] = as_json(binary._as_pb()) == expected(pbt.Test_pb2.Everything, EVERYTHING)
            out['everything_fields'] = dict(
                huge   = loaded.huge,
                bigs   = loaded.bigs,
                blobs  = [b.hex() for b in loaded.blobs],
                color  = loaded.color,
                addr   = loaded.addr if isinstance(loaded.addr, dict) else loaded.addr._as_dict(),
                unset  = loaded.unset,
                maybe  = loaded.maybe,
                places = loaded.places,
                )

            # nested values are checked against the message before they're stored
            if not _.config.getboolean('pb', 'relational'):
                bad = pb.Everything._from_dict(dict(name='bad', addr={'city': 'x'}))
                bad.addr['nope'] = 1
                try:
                    await db.insert(bad)
                    out['invalid'] = 'stored'
                except _.error as e:
                    out['invalid'] = 'rejected' if 'nope' in str(e) else str(e)
                out['invalid_stored'] = await db.find_one(pb.Everything, 'bad') is not None

            # well-known types
            EVENT = dict(
                name  = 'launch',
                at    = '2024-05-01T12:00:00.123456Z',
                took  = '90.5s',
                count = '0',
                note  = 'hi',
                big   = MAX,
                meta  = {'tags': ['a', 1], 'ok': True},
                value = 3.5,
                times = ['2024-01-01T00:00:00Z'],
                blob  = 'AAE=',
                )
            await db.insert(pb.Event._from_dict(EVENT))
            event = await db.find_one(pb.Event, 'launch')
            out['event'] = as_json(event._as_pb()) == expected(pbt.Test_pb2.Event, EVENT)
            out['event_values'] = dict(
                at    = event.at.isoformat(),
                took  = event.took.total_seconds(),
                count = event.count,
                note  = event.note,
                big   = event.big,
                meta  = event.meta,
                value = event.value,
                times = event.times,
                unset = event.unset,
                blob  = event.blob.hex(),
                )
            # an unset wrapper is None, unlike a stored 0
            await db.insert(pb.Event._from_dict(dict(name='empty')))
            empty = await db.find_one(pb.Event, 'empty')
            out['event_empty'] = [empty.count, empty.note, empty.at]
            out['event_json'] = json.loads(event._as_json())['took']
            def event_columns(conn):
                inspector = sqlalchemy.inspect(conn)
                return {c['name']: str(c['type']) for c in inspector.get_columns('Event')}, inspector.get_table_names()
            async with db.engine.connect() as conn:
                columns,tables = await conn.run_sync(event_columns)
            out['event_columns'] = dict(columns=columns, child_tables=sorted(t for t in tables if t.startswith('Event_')))

            # required, ref and no_column options
            await db.insert(pb.Owner._from_dict(dict(name='alice')))
            pet = dict(name='rex', owner='alice', age=3, home={'city': 'x'}, scratch='kept')
            async def attempt(**changes):
                value = {k:v for k,v in dict(pet, **changes).items() if v is not None}
                try:
                    await db.insert(pb.Pet._from_dict(value))
                    return 'stored'
                except _.error as e:
                    return str(e)
            out['pet'] = dict(
                ok        = await attempt(),
                bad_owner = await attempt(name='a', owner='nobody'),
                no_age    = await attempt(name='b', age=None),
                no_home   = await attempt(name='c', home=None),
                )
            def table_info(conn):
                inspector = sqlalchemy.inspect(conn)
                columns = {c['name']: c['nullable'] for c in inspector.get_columns('Pet')}
                fks = [(fk['referred_table'], fk['referred_columns']) for fk in inspector.get_foreign_keys('Pet')]
                return columns, fks
            async with db.engine.connect() as conn:
                columns,fks = await conn.run_sync(table_info)
            out['pet_columns'] = dict(
                stored    = sorted(columns),
                age_null  = columns['age'],
                home_null = columns.get('home'),
                fks       = fks,
                )
            loaded = await db.find_one(pb.Pet, 'rex')
            out['scratch'] = dict(
                binary = pb.Pet._from_binary(pb.Pet._from_dict(pet)._as_binary()).scratch,
                stored = loaded._as_pb().scratch,
                )

            # nested messages convert from dicts in both modes
            await db.insert(pb.Order._from_dict(ORDER))
            order = (await db.find(pb.Order))[0]
            out['order'] = as_json(order._as_pb()) == expected(pbt.Test_pb2.Order, ORDER)
            await db.delete(pb.Order, order.order_id)

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

STARTED = '''
    import json
    import _

    class App(_.Application):
        def initialize(self):
            print(json.dumps('started'))
            self.stop()

    App.main()
    '''

PACKAGE = '''
    import json
    import os
    from . import Test_pb2
    from . import sub
    '''


@pytest.fixture(params=list(backends()))
def run_proto_app(request, run_app, tmp_path):
    def _run(relational, reset=True, app=APP):
        (tmp_path / 'pbt' / 'sub').mkdir(parents=True, exist_ok=True)
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
        ini = f'[databases]\ndb = {request.param}\n\n' + database_ini(request.param, tmp_path, reset=reset) + textwrap.dedent(f'''
            [records]
            pb = protobuf

            [pb]
            module     = pbt
            database   = db
            options    = Protobuf
            handlers   = false
            relational = {str(relational).lower()}
            ''')
        result = run_app({'app.py' : app, 'app.ini' : ini})
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

    assert out['everything'] is True
    assert out['everything_binary'] is True
    assert out['order'] is True
    assert out['everything_fields'] == dict(
        # unsigned 64-bit values above 2**63 are not truncated
        huge   = 2**64 - 1,
        bigs   = [2**64 - 1, 1],
        blobs  = ['6869', ''],
        # enums are stored as numbers
        color  = 1,
        # nested messages are child records in relational mode,
        # otherwise they are held in proto3 JSON form
        addr   = (dict(city='x', code='', big=0, Everything_addr_id=1) if relational
                  else {'city': 'x', 'code': '', 'big': '0'}),
        # unset messages and optional fields are None
        unset  = None,
        maybe  = None,
        places = {'home': {'city': 'c', 'code': 'AQ==', 'big': '9007199254740993'}},
        )

    assert out['event'] is True
    assert out['event_values'] == dict(
        at    = '2024-05-01T12:00:00.123456+00:00',
        took  = 90.5,
        count = 0,
        note  = 'hi',
        big   = 2**64 - 1,
        meta  = {'tags': ['a', 1], 'ok': True},
        value = 3.5,
        # repeated well-known types stay in proto3 JSON form
        times = ['2024-01-01T00:00:00Z'],
        unset = None,
        blob  = '0001',
        )
    assert out['event_empty'] == [None, None, None]
    assert out['event_json'] == 90.5
    columns = out['event_columns']['columns']
    assert columns['at'] in ('TIMESTAMP', 'DATETIME')
    assert columns['took'] in ('INTERVAL', 'DATETIME')
    assert columns['count'] == 'BIGINT'
    # no child tables, even in relational mode
    assert out['event_columns']['child_tables'] == []

    pet = out['pet']
    assert pet['ok'] == 'stored'
    # the database refuses an owner that doesn't exist
    assert 'foreign key' in pet['bad_owner'].lower()
    assert pet['no_age'] == 'Pet.age is required'
    assert pet['no_home'] == 'Pet.home is required'
    # no_column fields aren't stored, required ones are NOT NULL
    stored = sorted(['age', 'name', 'owner'] + ([] if relational else ['home']))
    assert out['pet_columns']['stored'] == stored
    assert out['pet_columns']['age_null'] is False
    assert out['pet_columns']['home_null'] is (None if relational else False)
    assert out['pet_columns']['fks'] == [['Owner', ['name']]]
    # but they're kept in the message
    assert out['scratch'] == dict(binary='kept', stored='')

    if not relational:
        assert out['invalid'] == 'rejected'
        assert out['invalid_stored'] is False

    if relational:
        # deleting by id cascades to child tables in the database
        assert out['deleted'] == 1
        assert out['orphans'] == 0


@pytest.mark.parametrize('relational', [False, True])
def test_protobuf_schema_matches(run_proto_app, relational):
    # a second start compares the tables it created with the models, so any
    # difference in how a type is reflected would refuse to start here
    run_proto_app(relational)
    started = run_proto_app(relational, reset=False, app=STARTED)
    assert started == 'started'


WEB_APP = '''
    import _

    class App(_.WebApplication):
        def is_session_expired(self, *args, **kwds):
            return False

        def initialize(self):
            pass

    App.main()
    '''


@pytest.fixture
def proto_server(tmp_path):
    # two components each with a message named Greeting, one with a custom handler
    files = {
        'pbw/Web.proto'     : '''
            syntax = "proto3";
            package pbw;
            import "pbw/Protobuf.proto";
            message Greeting { option (no_table) = true; string text = 1; }
            message Plain    { option (no_table) = true; string text = 1; }
            message Thing    { string name = 1 [(pkey) = true]; }
            ''',
        'pbw/__init__.py'   : '''
            from . import Web_pb2
            from . import sub
            import _

            @_.web.handles(Web_pb2.Greeting)
            class Hello:
                async def get(self, record_id=None):
                    self.write(f'hello {record_id}')
            ''',
        # same message names as the parent package
        'pbw/sub/Sub.proto' : '''
            syntax = "proto3";
            package pbw.sub;
            import "pbw/Protobuf.proto";
            message Greeting { option (no_table) = true; string text = 1; }
            message Thing    { string name = 1 [(pkey) = true]; string colour = 2; }
            ''',
        'pbw/sub/__init__.py' : '''
            from . import Sub_pb2
            import _

            @_.web.handles(Sub_pb2.Greeting)
            class SubHello:
                async def get(self, record_id=None):
                    self.write(f'sub hello {record_id}')
            ''',
        'pbo/Other.proto'   : '''
            syntax = "proto3";
            package pbo;
            import "pbw/Protobuf.proto";
            message Greeting { option (no_table) = true; string text = 1; }
            ''',
        # the options can only be defined once, so share them
        'pbo/__init__.py'   : 'from pbw import Protobuf_pb2\nfrom . import Other_pb2\n',
        }
    (tmp_path / 'pbw' / 'sub').mkdir(parents=True)
    (tmp_path / 'pbo').mkdir()
    shutil.copy(os.path.join(ROOT, '_', 'records', 'Protobuf.proto'), tmp_path / 'pbw')
    for name,content in files.items():
        (tmp_path / name).write_text(textwrap.dedent(content))
    subprocess.run(['protoc', '-I.', '--python_out=.', 'pbw/Protobuf.proto', 'pbw/Web.proto', 'pbw/sub/Sub.proto', 'pbo/Other.proto'],
        cwd=tmp_path, check=True)
    server = Server(tmp_path, {
        'app.py'  : WEB_APP,
        'app.ini' : f'''
            [app]
            sessions = memory

            [databases]
            db = sqlite

            [db]
            database = {tmp_path}/web.db

            [caches]
            memory

            [records]
            web   = protobuf
            other = protobuf

            [web]
            module   = pbw
            database = db
            options  = Protobuf

            [other]
            module   = pbo
            database = db
            options  = Protobuf
            ''',
        })
    server.directory = tmp_path
    yield server
    server.stop()


def test_protobuf_handler_routes(proto_server):
    # custom handlers are served at the message name
    assert proto_server.request('GET', '/web/Greeting/x') == (200, b'hello x')
    assert proto_server.request('GET', '/web/Hello/x')[0] == 404
    # the other component's Greeting doesn't pick up that handler
    assert proto_server.request('GET', '/other/Greeting/x')[0] == 404
    # messages without a table only get a route from a custom handler
    assert proto_server.request('GET', '/web/Plain')[0] == 404
    assert proto_server.request('GET', '/web/Thing') == (200, b'{"data": []}')


def test_protobuf_subpackage_routes(proto_server):
    # subpackage messages have their own routes and tables
    assert proto_server.request('GET', '/web/sub/Greeting/x') == (200, b'sub hello x')
    assert proto_server.request('GET', '/web/Greeting/x') == (200, b'hello x')

    thing = json.dumps(dict(name='a', colour='red')).encode()
    assert proto_server.request('POST', '/web/sub/Thing', thing)[0] == 204
    code,body = proto_server.request('GET', '/web/sub/Thing/a')
    assert code == 200 and json.loads(body)['colour'] == 'red'
    assert proto_server.request('GET', '/web/Thing/a')[0] == 404

    with sqlite3.connect(proto_server.directory / 'web.db') as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'Thing', 'sub_Thing'} <= tables
