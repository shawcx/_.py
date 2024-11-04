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
    try:
        caller = inspect.getfile(_.application.__class__)
    except OSError:
        caller = '.'

    # allow apps to define a name or derive from caller
    _.name = kwds.get('name', None)
    if _.name is None:
        # get the name of the script
        _.name = os.path.basename(caller)
        if _.name.endswith('.py'):
            _.name = _.name[:-3]

    # allow apps to define a namespace
    _.ns = kwds.get('ns', _.name)
    if _.ns is None:
        _.ns = ''

    # get the directory of the script
    root = kwds.get('root', None)
    if root is None:
        root = os.path.dirname(caller)
    root = os.path.abspath(root)

    _.paths = _.Paths(root=root, ns=_.ns)

    # if ns is not passed in use the supplied or derived ns
    ini_name = _.name or _.ns
    ini_dir  = _.ns or _.name

    # allow several locations for ini files
    ini_files = [
        _.paths(f'{ini_name}.ini'),
        _.paths(f'{ini_name}.ini.local'),
        os.path.join(os.path.sep, 'etc', f'{ini_dir}', f'{ini_name}.ini'),
        os.path.join(os.path.expanduser('~'), f'.{ini_name}.ini'),
        ]

    # first pass at parsing args to get additional ini files
    _.args,remainder = _.argparser.parse_known_args()

    # append a custom ini file if specified
    if _.args.ini:
        ini_files.append(_.args.ini)

    # little hack because I like the generic options at the bottom of the help message
    _.args.debug = '--debug' in remainder or '-D' in remainder
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level   = logging.DEBUG if _.args.debug else logging.INFO,
        force   = True
        )

    # load the ini files, at least one file must exist
    try:
        if _.args.debug:
            for ini_file in ini_files:
                logging.debug('Loading ini file: %s', ini_file)
        ok = _.config.read(ini_files)
    except configparser.ParsingError as e:
        raise _.error('Unable to parse file: %s', e)

    if not ok:
        logging.warning('Unable to read config file(s):\n  %s', '\n  '.join(ini_files))

    # load the components specified in the ini file
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

    # add the generic arguments after any components
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

    try:
        for name,component in _.supports.items():
            await _.wait(component.args(name))
    except _.error as e:
        logging.error('%s', e)
        _.application.stop()
        return
