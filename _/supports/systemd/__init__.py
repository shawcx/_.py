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


class Systemd(_.supports.Support):
    async def init(self, name, **kwds):
        self.params = dict(
            ns        = _.ns,
            name      = _.name,
            cmdline   = f'{os.path.abspath(sys.argv[0])}',
            user      = 'nobody',
            conf_path = '/etc/systemd/system/{name}.service',
            )

        self.params.update(kwds)

        _.argparser.add_argument(f'--systemd',
            action='store_true',
            help='install systemd service'
            )

    async def args(self, name):
        if not _.args.systemd:
            return

        logging.info('Installing systemd service')

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
            raise _.error('Could not write systemd service: %s', e)

        _.application.stop()
