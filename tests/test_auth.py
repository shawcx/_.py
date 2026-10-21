import base64
import json

import pytest

from conftest import Server

CHECK = '''
    import json
    import _

    class App(_.Application):
        async def initialize(self):
            login = _.logins['dblogin']

            # a user stored with the old unsalted hash
            legacy = login._table()
            legacy(username='bob', password=_.auth.simple_hash('bob' + 'pw'))
            await login._db.upsert(legacy)

            out = dict(
                alice_hash  = (await login._db.find_one(login._table, 'alice')).password[:7],
                alice_ok    = bool(await login.check('alice', 'secret')),
                alice_wrong = await login.check('alice', 'wrong'),
                bob_ok      = bool(await login.check('bob', 'pw')),
                )
            # logging in upgrades the legacy hash
            bob = await login._db.find_one(login._table, 'bob')
            out['bob_hash'] = bob.password[:7]
            out['bob_still_ok'] = bool(await login.check('bob', 'pw'))
            print(json.dumps(out))
            self.stop()

    App.main()
    '''


def test_dblogin_passwords(run_app, tmp_path):
    ini = f'[databases]\ndb = sqlite\n\n[db]\ndatabase = {tmp_path}/db.db\n\n[logins]\ndblogin\n'
    added = run_app({'app.py' : CHECK, 'app.ini' : ini}, '--add-user', 'alice', 'secret')
    assert added.returncode == 0, added.stderr

    result = run_app({'app.py' : CHECK, 'app.ini' : ini})
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out == dict(
        alice_hash   = 'scrypt$',
        alice_ok     = True,
        alice_wrong  = None,
        bob_ok       = True,
        bob_hash     = 'scrypt$',
        bob_still_ok = True,
        )


BASIC = '''
    import tornado.web
    import _

    class Secret(tornado.web.RequestHandler):
        @_.auth.basic('Test Realm')
        async def get(self):
            self.write('ok')

    class App(_.WebApplication):
        async def initialize(self):
            login = _.logins['dblogin']
            user = login._table()
            user(username='alice', password=_.auth.hash_password('secret'))
            await login._db.upsert(user)
            self.patterns = [(r'/secret', Secret)]

    App.main()
    '''


@pytest.fixture
def basic_server(tmp_path):
    server = Server(tmp_path, {
        'app.py'  : BASIC,
        'app.ini' : f'''
            [app]
            basic = dblogin

            [databases]
            db = sqlite

            [db]
            database = {tmp_path}/db.db

            [logins]
            dblogin
            ''',
        })
    yield server
    server.stop()


def basic_request(server, header=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f'http://127.0.0.1:{server.port}/secret')
    if header:
        req.add_header('Authorization', header)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def credentials(user, password):
    return 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()


def test_basic_auth(basic_server):
    code,_body,headers = basic_request(basic_server)
    assert code == 401
    assert headers['WWW-Authenticate'] == 'Basic realm="Test Realm"'

    assert basic_request(basic_server, credentials('alice', 'wrong'))[0] == 401
    assert basic_request(basic_server, credentials('alice', 'secret'))[:2] == (200, b'ok')
    # a header that isn't base64 is a bad request rather than a server error
    assert basic_request(basic_server, 'Basic !!!')[0] == 400
