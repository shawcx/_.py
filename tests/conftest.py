#
# _ keeps its state in module globals and parses sys.argv, so each test
# runs its app in a separate interpreter.
#

import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
            with urllib.request.urlopen(req, timeout=10) as r:
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
