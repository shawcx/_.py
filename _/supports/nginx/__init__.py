#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import os

import _


class Nginx(_.supports.Support):
    async def init(self, component_name, **kwds):
        self.params = dict(
            ns          = _.ns,
            name        = _.name,
            web_root    = '/var/www/html',
            address     = '127.0.0.1',
            port        = 8080,
            listen_ip4  = '0.0.0.0',
            listen_ip6  = '[::]',
            listen_http = 80,
            listen_ssl  = 443,
            conf_path   = '/etc/nginx/sites-available/{server_name}',
            )

        self.params.update(dict(_.config[_.name]))
        try:
            self.params.update(dict(_.config[component_name]))
        except KeyError:
            pass
        self.params.update(kwds)

        try:
            _.argparser.add_argument(f'--nginx',
                metavar='<server_name>', default=0, nargs='?',
                help='install nginx config'
                )
        except:
            raise _.error('Multiple nginx supports detected: %s', component_name) from None

    async def args(self, component_name):
        if _.args.nginx == 0:
            return

        name = _.args.nginx if _.args.nginx else _.name

        if 'server_name' not in self.params:
            self.params['server_name'] = name

        conf = _.paths(f'{name}.conf')
        print('CONF:', conf)
        if not os.path.exists(conf):
            conf = os.path.join(self.root, 'nginx', 'nginx.conf')
        logging.debug('Loading configuration: %s', conf)

        try:
            with open(conf, 'r') as fp:
                conf = fp.read()
            try:
                conf = conf.format(**self.params)
            except KeyError as e:
                raise _.error('Missing nginx configuration file parameter: %s', e) from None

            path = self.params['conf_path'].format(**self.params)
            with open(path, 'w') as fp:
                fp.write(conf)
        except _.error:
            raise
        except Exception as e:
            raise _.error('Could not write nginx configuration: %s', e) from None

        logging.info('Installed nginx configuration: %s', name)

        _.application.stop()
