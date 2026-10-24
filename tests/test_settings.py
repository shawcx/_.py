import json

import pytest

APP = '''
    import json
    import _

    class App(_.Application):
        def initialize(self):
            print(json.dumps(dict(_.config['app'])))
            self.stop()

    App.main()
    '''


def config_of(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_ini_merge_order(run_app, tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.app.ini').write_text('[app]\nc = home\nd = home\n')
    (tmp_path / 'extra.ini').write_text('[app]\nd = extra\n')

    result = run_app({
        'app.py'        : APP,
        'app.ini'       : '[app]\na = ini\nb = ini\nc = ini\nd = ini\n',
        'app.ini.local' : '[app]\nb = local\nc = local\nd = local\n',
        }, '--ini', str(tmp_path / 'extra.ini'), home=home)

    # later files win: app.ini < app.ini.local < ~/.app.ini < --ini
    assert config_of(result) == dict(a='ini', b='local', c='home', d='extra')


def test_missing_ini_warns(run_app):
    result = run_app({'app.py' : APP.replace("dict(_.config['app'])", '{}')})
    assert config_of(result) == {}
    assert 'Unable to read config file' in result.stderr


VERSION_APP = '''
    import _

    class App(_.WebApplication):
        version = '1.2.0'

        def initialize(self):
            print('started')
            self.stop()

    App.main()
    '''


@pytest.mark.parametrize('flag', ['--version', '-V'])
def test_version(run_app, flag):
    import _.version
    # an unloadable component shows nothing is loaded or started
    result = run_app({
        'app.py'  : VERSION_APP,
        'app.ini' : '[databases]\nstore = +missing.module\n',
        }, flag)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['app 1.2.0', f'underscorepy {_.version.__version__}']
    assert result.stderr == ''


def test_version_without_app_version(run_app):
    import _.version
    result = run_app({'app.py' : VERSION_APP.replace("version = '1.2.0'", 'pass')}, '--version')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f'underscorepy {_.version.__version__}']
