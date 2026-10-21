import json

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
