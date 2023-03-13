#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import asyncio
import logging
import os
import signal
import socket
import sys
import traceback

import tornado.web

import _


class Application(tornado.web.Application):
    @classmethod
    def main(cls, ns=None):
        _.application = self = cls()
        try:
            asyncio.run(self.__async_main(ns))
        except _.error as e:
            if _.args.debug:
                traceback.print_tb(e.__traceback__)
            logging.error('%s', e)

    async def __async_main(self, ns):
        self._records_patterns = []
        self._login_patterns   = []

        self.patterns = []
        self.settings = {}

        self.loop = asyncio.get_event_loop()
        self._stop_event = asyncio.Event()

        signal.signal(signal.SIGINT,  self.__signalHandler)
        signal.signal(signal.SIGTERM, self.__signalHandler)

        name = self.__class__.__name__.lower()
        try:
            await _.settings.load(ns=ns, name=name)
            await self.logging()
        except _.error as e:
            if _.args.debug:
                traceback.print_tb(e.__traceback__)
            logging.error('%s', e)
            self.stop()

        if not self._stop_event.is_set():
            for name,component in _.logins.items():
                try:
                    await _.wait(component.args(name))
                except _.error as e:
                    logging.error('%s', e)
                    self.stop()
                    break

        if not self._stop_event.is_set():
            try:
                await self.__async_init()
            except _.error as e:
                logging.error('%s', e)

        for name,component in _.caches.items():
            await component.close()

        for name,component in _.databases.items():
            await component.close()

    async def __async_init(self, **kwds):
        # check if a sessions cache was specified
        _.sessions = _.config.get(_.name, 'sessions', fallback=None)
        if _.sessions:
            logging.debug('Sessions cache: %s', _.sessions)
            try:
                _.sessions = _.caches[_.sessions]
            except KeyError:
                raise _.error('Unknown sessions cache instance: %s', _.sessions)

        self.settings['static_path']   = _.paths('static')
        self.settings['template_path'] = _.paths('templates')
        self.settings['debug']         = _.args.debug

        # call the underscore application's entry point
        try:
            await _.wait(self.initialize())
        except NotImplementedError:
            logging.warning('No "initialize" function defined')

        if 'cookie_secret' not in self.settings:
            self.settings['cookie_secret'] = await self.cookie_secret()

        patterns = list(self._records_patterns)

        if self._login_patterns:
            self._login_patterns += [
                ( r'/login',  _.logins.LoginPage ),
                ( r'/logout', _.logins.Logout    ),
                ]
            self.settings['login_url'] = '/login'
        patterns += self._login_patterns
        patterns += self.patterns

        patterns.append(
            ( r'/(favicon.ico)', tornado.web.StaticFileHandler, {'path':''}),
            )

        if _.args.debug:
            for (pattern,cls,*params) in patterns:
                handler = f'{cls.__module__}.{cls.__name__}'
                logging.debug('%-32s %s %s', pattern, handler, params[0] if params else '')

        await self.__listen(patterns)
        await self._stop_event.wait()
        await _.wait(self.on_stop())

    async def __listen(self, patterns, **kwds):
        # call the Tornado Application init here to give children a chance
        # to initialize patterns and settings
        super().__init__(patterns, **self.settings)

        if 'xheaders' not in kwds:
            kwds['xheaders'] = True

        try:
            self.listen(_.args.port, _.args.address, **kwds)
        except Exception as e:
            raise _.error('%s', e) from None

        logging.info('Listening on %s:%d', _.args.address, _.args.port)

    def _record_handler(self, name, cls):
        self._records_patterns.append(
            (f'/{name}/{cls._name}(?:/(.*))?', cls)
            )

    def _login_handler(self, name, cls):
        self._login_patterns.append(
            (f'/{name}/{cls._name}', cls)
            )

    async def initialize(self):
        'underscore apps should override this function'
        raise NotImplementedError

    async def logging(self):
        'underscore apps can override or extend this function'

        # add the handlers to the logger
        if _.config.getboolean(_.name, 'logging', fallback=False):
            full_path = _.paths(f'{_.name}.log')
            file_logger = logging.FileHandler(full_path)
            file_logger.setLevel(logging.DEBUG if _.args.debug else logging.INFO)
            file_logger.setFormatter(
                logging.Formatter(
                    fmt = '%(asctime)s %(levelname)-8s %(message)s',
                    datefmt = '%Y-%m-%d %H:%M:%S',
                    )
                )
            root_logger = logging.getLogger()
            root_logger.addHandler(file_logger)

    async def cookie_secret(self):
        'underscore apps can override this function'
        if _.sessions is not None:
            return await _.wait(_.sessions.cookie_secret())

    async def on_login(self, handler, user, *args, **kwds):
        'underscore apps should override this function if a login is specified'
        raise NotImplementedError

    def task(self, fn, *args, **kwds):
        async def _task():
            await _.wait(fn(*args, **kwds))
        return asyncio.create_task(_task())

    def periodic(self, _timeout, fn, *args, **kwds):
        'run a function or coroutine on a recurring basis'
        async def _periodic():
            while True:
                # bail if the stop event is set
                # otherwise run the function after the timeout occurs
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=_timeout)
                    break
                except asyncio.TimeoutError as e:
                    pass
                try:
                    result = await _.wait(fn(*args, **kwds))
                except Exception as e:
                    logging.exception(e)
        return asyncio.create_task(_periodic())

    def stop(self):
        logging.debug('Setting stop event')
        self._stop_event.set()

    def on_stop(self):
        pass

    def __signalHandler(self, signum, frame):
        'handle signals in a thread-safe way'
        signame = signal.Signals(signum).name
        handler = getattr(self, f'on_{signame.lower()}', None)
        if handler:
            if handler(signum, frame):
                return
        logging.info('Terminating %s on %s signal', _.name, signame)
        self.loop.call_soon_threadsafe(self.stop)

    # demonstrate a specific signal handler
    # and print newline after ^C on terminals
    def on_sigint(self, signum, frame):
        print()
