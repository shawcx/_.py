
import dataclasses
import logging
import time
import uuid

import _

import skeleton

# this will change the default authentication behavior
# for all the handlers associated with the loaded components
# must be set before _.settings.load is called
_.auth.protected = _.auth.filter_user(lambda current_user: current_user)

class Skeleton(_.Application):
    async def initialize(self):
        self.websockets = {}

        self.db   = _.databases.sqlite

        audio = _.data.audio(
            device='name',
            samples=2048,
            )
        print()
        print('#' * 20)
        print('repr:', repr(audio))
        print('dict:', audio.dict())
        print('json:', audio.json())
        await audio.delete()
        await audio.insert()
        await audio.update()
        await audio.upsert()
        print('find:', await _.data.audio.find_one('name'))
        print('count:', await _.data.audio.count())
        print('count: samples == 2048:', await audio.count('samples', 2048))
        print('#' * 20)
        print()
        print('#' * 20)
        skel = _.proto.Skeleton()
        skel.field1 = 'skel'
        skel.field2 = 'example'
        print('repr:')
        print(repr(skel))
        print('dict:', skel.dict())
        print('json:', skel.json())
        await skel.delete()
        await skel.insert()
        await skel.update()
        await skel.upsert()
        print('find:')
        print(await _.proto.Skeleton.find_one('skel'))
        print('count:', await _.proto.Skeleton.count())
        print('#' * 20)
        print()

        self.patterns = [
            ( r'/ws',       skeleton.handlers.Socket, { 'websockets' : self.websockets } ),
            ( r'/([a-z]*)', _.handlers.Protected ),
            ]

        #self.status_task  = self.periodic(10, self.status)
        #self.status_task.cancel()

    async def status(self):
        logging.info('Periodic: %s', time.ctime())

    async def on_dblogin_add_user(self, name, record):
        'make adjustments to the record before calling sql statement'
        record['disabled'] = False
        record['isadmin']  = True
        record['created']  = _.now()

    async def on_dblogin_update(self, handler, name, record):
        'allow apps to make adjustments to the record before calling sql statement'
        print(name)
        print(record)

    async def on_gitlab_login(self, handler, user):
        session = {
            'session_id' : str(uuid.uuid4()),
            'username'   : user['username'],
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        return session

    async def on_login(self, handler, user):
        user['last'] = int(time.time() * 1000)
        await self.db.update('users', 'username', user)

        session = {
            'session_id' : str(uuid.uuid4()),
            'username'   : user['username'],
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        return session

    async def is_session_expired(self, session, expires):
        created = session['time'] / 1000
        elapsed = (time.time() - created) / 3600
        return elapsed > expires
