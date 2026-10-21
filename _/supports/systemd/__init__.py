#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import os
import sys

import _


def _command():
    '''the command that starts this app again: python -m package when it was
       run that way, which has no runnable script, otherwise python script'''
    spec = getattr(sys.modules.get('__main__'), '__spec__', None)
    if spec is not None and spec.name:
        module = spec.name.removesuffix('.__main__')
        command = f'{sys.executable} -m {module}'
    else:
        command = f'{sys.executable} {os.path.abspath(sys.argv[0])}'
    # keep an extra ini file given on the command line
    if getattr(_.args, 'ini', None):
        command += f' --ini {os.path.abspath(_.args.ini)}'
    return command


class Systemd(_.supports.Support):
    async def init(self, component_name, **kwds):
        self.params = dict(
            ns        = _.ns,
            name      = _.name,
            user      = os.environ.get('USER', 'nobody'),
            cwd       = os.getcwd(),
            conf_path = '/etc/systemd/system/{name}.service',
            )

        self.params.update(kwds)

        _.argparser.add_argument(f'--systemd',
            metavar='<user>', default=0, nargs='?',
            help='install systemd service'
            )

    async def args(self, component_name):
        if _.args.systemd == 0:
            return

        if _.args.systemd:
            self.params['user'] = _.args.systemd
        if 'cmdline' not in self.params:
            self.params['cmdline'] = _command()

        # set name to the value from params
        name = self.params.get('name')

        with open(os.path.join(self.root, 'systemd', 'systemd.service'), 'r') as fp:
            conf = fp.read()

        try:
            conf = conf.format(**self.params)
        except KeyError as e:
            raise _.error('Missing systemd parameter: %s', e)

        path = self.params['conf_path'].format(**self.params)
        try:
            with open(path, 'w') as fp:
                fp.write(conf)
        except Exception as e:
            raise _.error('Could not write systemd service: %s: %s', name, e) from None

        logging.info('Installed systemd service: %s', name)

        _.application.stop()
