#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import argparse
import collections
import configparser
import inspect
import logging
import os
import sys
import time
import traceback

import _


# override exit to set the stop event
class ArgParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        _.application.stop()

_.argparser = ArgParser(add_help=False)

_.argparser.add_argument('--ini', '-I',
    metavar='<path>',
    help='Specify additional ini file')

_.argparser.add_argument('--address', '-a',
    metavar='<address>',
    help = 'Interface to bind to')

_.argparser.add_argument('--port', '-p',
    metavar='<port>',
    type=int,
    help='Port to listen on')


_.config = configparser.ConfigParser(
    allow_no_value = True,
    interpolation  = None,
    )
_.config.optionxform = str


async def load(**kwds):
    # get the path of the caller
    caller = inspect.getfile(_.application.__class__)

    # get the directory of the script
    root = kwds.get('root', None)
    if root is None:
        root = os.path.dirname(caller)
    root = os.path.abspath(root)

    _.name = kwds.get('name', None)
    if _.name is None:
        # get the name of the script
        _.name = os.path.basename(caller)
        if _.name.endswith('.py'):
            _.name = _.name[:-3]

    _.ns = kwds.get('ns', _.name)
    if _.ns is None:
        _.ns = ''

    _.paths = _.Paths(root=root, ns=_.ns)

    # if ns is not passed in use the supplied or derived ns
    ini_files = []

    if _.ns:
        ini_files.append(_.paths(f'{_.ns}.ini'))
        ini_files.append(_.paths(f'{_.ns}.ini.local'))

    ini_files.append(_.paths(f'{_.name}.ini'))
    ini_files.append(_.paths(f'{_.name}.ini.local'))

    # first pass at parsing args to get additional ini files
    _.args,remainder = _.argparser.parse_known_args()

    if _.args.ini:
        ini_files.append(_.args.ini)

    _.args.debug = '--debug' in remainder
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level   = logging.DEBUG if _.args.debug else logging.INFO,
        force   = True
        )

    if _.args.debug:
        for ini_file in ini_files:
            logging.debug('Loading ini file: %s', ini_file)

    try:
        ok = _.config.read(ini_files)
    except configparser.ParsingError as e:
        raise _.error('Unable to parse file: %s', e)

    if not ok:
        raise _.error('Unable to read config file(s):\n  %s', '\n  '.join(ini_files))

    try:
        await _.components.load('databases')
        await _.components.load('records')
        await _.components.load('caches')
        await _.components.load('logins')
        await _.components.load('supports')
    except _.error as e:
        logging.error('%s', e)
        _.application.stop()
        return

    _.argparser.add_argument('--debug', '-D',
        action='store_true',
        help='Log verbose debugging information')

    _.argparser.add_argument('--version', '-V',
        action='store_true',
        help='Show version and exit'
        )

    _.argparser.add_argument('--help', '-h',
        action='help', default=argparse.SUPPRESS,
        help='Show help message')

    _.args = _.argparser.parse_args()

    if not _.args.address:
        _.args.address = _.config.get(_.name, 'address', fallback='127.0.0.1')

    if not _.args.port:
        _.args.port = _.config.getint(_.name, 'port', fallback=8080)

    try:
        for name,component in _.supports.items():
            await _.wait(component.args(name))
    except _.error as e:
        logging.error('%s', e)
        _.application.stop()
        return
