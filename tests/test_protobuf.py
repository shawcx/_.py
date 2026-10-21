import json
import os
import shutil
import subprocess
import textwrap

import pytest

from conftest import ROOT, backends, database_ini

pytest.importorskip('google.protobuf')
if not shutil.which('protoc'):
    pytest.skip('protoc not installed', allow_module_level=True)

PROTO = '''
    syntax = "proto3";

    package pbt;

    import "pbt/Protobuf.proto";

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
