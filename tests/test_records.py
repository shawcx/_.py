import json
import pickle

import pytest

from conftest import Server

APP = '''
    import _

    class App(_.WebApplication):
        def is_session_expired(self, *args, **kwds):
            return False

        def initialize(self):
            pass

    App.main()
    '''

DATA = '''
    import _

    class person:
        name : str = _.data.pkey()
        age  : int

    class item:
        label : str
        count : int

    @_.data.no_table
    class custom:
        name : str

    @_.data.handles(custom)
    class custom_handler:
        async def get(self, record_id=None):
            self.write(f'hello {record_id}')

    # no table and no custom handler, so nothing to serve
    @_.data.no_table
    class notable:
        name : str
    '''


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    directory = tmp_path_factory.mktemp('records')
    server = Server(directory, {
        'app.py'              : APP,
        'records_data/__init__.py' : DATA,
        'app.ini'             : f'''
            [app]
            sessions = memory

            [databases]
            db = sqlite

            [db]
            database = {directory}/records.db

            [caches]
            memory

            [records]
            data

            [data]
            module   = records_data
            database = db
            ''',
        })
    server.directory = directory
    yield server
    server.stop()


def test_json_crud_string_key(server):
    assert server.request('POST', '/data/person', b'{"name":"alice","age":30}')[0] == 204
    code,body = server.request('GET', '/data/person/alice')
    assert code == 200
    assert json.loads(body) == dict(name='alice', age=30)
    assert server.request('DELETE', '/data/person/alice')[0] == 204
    assert server.request('GET', '/data/person/alice')[0] == 404


def test_json_crud_auto_key(server):
    assert server.request('POST', '/data/item', b'{"label":"x","count":1}')[0] == 204
    code,body = server.request('GET', '/data/item/1')
    assert code == 200
    assert json.loads(body) == dict(label='x', count=1, item_id=1)
    # ids that don't convert to the key's type are not found
    assert server.request('GET', '/data/item/abc')[0] == 404
    assert server.request('DELETE', '/data/item/1')[0] == 204
    assert server.request('DELETE', '/data/item/1')[0] == 404


def test_binary_round_trip(server):
    body = json.dumps(dict(name='bob', age=40)).encode()
    assert server.request('POST', '/data/person?type=binary', body)[0] == 204
    code,body = server.request('GET', '/data/person/bob?type=binary')
    assert code == 200
    # the declared primary key is kept in binary form
    assert json.loads(body) == dict(name='bob', age=40)


def unpack_delimited(packed):
    records = []
    while packed:
        size = shift = 0
        while True:
            byte = packed[0]
            packed = packed[1:]
            size |= (byte & 0x7f) << shift
            shift += 7
            if not byte & 0x80:
                break
        records.append(json.loads(packed[:size]))
        packed = packed[size:]
    return records


def test_binary_list(server):
    # a 200 byte record needs a two byte varint length
    long_name = 'n' * 200
    for name,age in [('carol', 50), (long_name, 60)]:
        body = json.dumps(dict(name=name, age=age)).encode()
        assert server.request('POST', '/data/person', body)[0] == 204
    code,body = server.request('GET', '/data/person?type=binary')
    assert code == 200
    records = unpack_delimited(body)
    assert dict(name='carol', age=50) in records
    assert dict(name=long_name, age=60) in records


class Marker:
    path = None

    def __reduce__(self):
        return (open, (self.path, 'w'))


def test_pickle_body_is_not_loaded(server):
    marker = server.directory / 'marker'
    Marker.path = str(marker)
    code,_ = server.request('POST', '/data/person?type=binary', pickle.dumps(Marker()))
    assert code == 400
    assert not marker.exists()


@pytest.mark.parametrize('body', [b'{not json', b'', None])
def test_bad_body(server, body):
    assert server.request('POST', '/data/person', body)[0] == 400


def test_delete_without_id(server):
    assert server.request('DELETE', '/data/person')[0] == 400


def test_custom_handler_route(server):
    # served at the record name rather than the handler class name
    assert server.request('GET', '/data/custom/x') == (200, b'hello x')
    assert server.request('GET', '/data/custom_handler/x')[0] == 404


def test_no_table_without_handler_has_no_route(server):
    assert server.request('GET', '/data/notable')[0] == 404
