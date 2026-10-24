#
# _ keeps its state in module globals and parses sys.argv, so each test
# runs its app in a separate interpreter.
#
# Set UNDERSCORE_TEST_POSTGRES to a URL such as
# postgresql://user:password@127.0.0.1:5432/db to also run the database
# tests against Postgres. They drop and recreate its public schema.
#

import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# the test servers are local, so ignore any http_proxy (pybuild sets one)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def backends():
    yield 'sqlite'
    if os.environ.get('UNDERSCORE_TEST_POSTGRES'):
        yield 'postgres'


def database_ini(backend, tmp_path, name='db', reset=True):
    'the INI section for a database named name, emptied first if reset'
    if backend == 'sqlite':
        return f'[{name}]\ndatabase = {tmp_path}/{name}.db\n'
    url = os.environ['UNDERSCORE_TEST_POSTGRES']
    if reset:
        subprocess.run(['psql', '-q', url, '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public'],
            check=True, capture_output=True)
    url = urllib.parse.urlsplit(url)
    return (
        f'[{name}]\n'
        f'host = {url.hostname}\nport = {url.port or 5432}\n'
        f'username = {url.username}\npassword = {url.password}\n'
        f'database = {url.path.lstrip("/")}\n'
        )


def write_files(directory, files):
    for name,content in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))


def app_env(home):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [ROOT, env.get('PYTHONPATH')]))
    # keep ~/.<name>.ini lookups inside the test
    env['HOME'] = str(home)
    # files rewritten within a second can have the same size and mtime
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


@pytest.fixture
def run_app(tmp_path):
    '''write the files into tmp_path, run app.py there and return the result'''
    def _run(files, *args, home=None):
        write_files(tmp_path, files)
        return subprocess.run(
            [sys.executable, str(tmp_path / 'app.py'), *args],
            cwd     = tmp_path,
            env     = app_env(home or tmp_path),
            capture_output = True,
            text    = True,
            timeout = 30,
            )
    return _run


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, directory, files):
        write_files(directory, files)
        self.port = free_port()
        self.log  = open(directory / 'server.log', 'w+')
        self.proc = subprocess.Popen(
            [sys.executable, str(directory / 'app.py'), '--port', str(self.port)],
            cwd    = directory,
            env    = app_env(directory),
            stdout = self.log,
            stderr = subprocess.STDOUT,
            )
        self.wait_ready()

    def wait_ready(self, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f'server exited:\n{self.output()}')
            try:
                socket.create_connection(('127.0.0.1', self.port), timeout=0.2).close()
                return
            except OSError:
                time.sleep(0.1)
        self.stop()
        raise RuntimeError(f'server not listening:\n{self.output()}')

    def output(self):
        self.log.seek(0)
        return self.log.read()

    def request(self, method, path, body=None):
        url = f'http://127.0.0.1:{self.port}{path}'
        req = urllib.request.Request(url, data=body, method=method)
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()
