
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

import sqlalchemy

class Skeleton(_.WebApplication):
    async def initialize(self):
        self.websockets = {}

        self.db = _.databases.store

        message = _.proto.Message()
        message.message_id = 1
        message.field1 = 'Matt'
        message.field2 = b'\xff\x01abc'
        print(message)
        await self.db.upsert(message)

        r = _.proto.Reports()
        r.single = {}
        r.single['source'] = 'matt'
        r.single['count'] = 10
        r.single['deep'] = {}
        r.single['deep']['deep'] = 'DEEP'
        r.multiple = []
        for x in range(4):
            m = dict(
                source=f'{x * x}',
                count = x,
                )
            r.multiple.append(m)
        r.req = '88'
        print('JSON:', r._as_json())
        data = r._as_binary()
        print('BINARY:', data)
        x = _.proto.Reports._from_binary(data)
        x.single['count2'] = 10
        x.Reports_id = 35
        print(x)

        if False:
            await self.db.upsert(x)
        await self.db.upsert(x)

        if True:
            s = _.data.skel()
            s(
                field1='name',
                field2=100,
                field3=200,
                lat=1.2,
                lng=3.4,
                )
            print()
            b = s._as_binary()
            print(b)
            b = _.data.skel._from_binary(b)
            print(b)
            print()
            try:
                await self.db.insert(s)
            except Exception as e:
                s = await self.db.find_one(_.data.skel, None)
                if s:
                    await self.db.delete(s)

        if False:
            #print(skel._as_json())
            #print(skel._as_dict())
            #print()
            #print('#' * 20)
            #print('repr:', repr(skel))
            #print('dict:', skel.dict())
            #print('json:', skel.json())
            #await skel.delete()
            #await skel.insert()
            #await skel.update()
            #await skel.upsert()
            #print('find:', await _.data.skel.find_one('name'))
            #print('count:', await _.data.skel.count())
            #print('count: samples == 200:', await skel.count('field3', 200))
            #print('#' * 20)
            #print()
            #print('#' * 20)

            skel = _.proto.Skeleton()
            skel(dict(field1='50',field2='60'))
            #print(skel._as_json())
            #await self.db.insert(skel)
            for r in await self.db.find(_.proto.Skeleton):
                print('@', r.Skeleton_id, r._as_json())
                #r2 = await self.db.find_one(_.proto.Skeleton, r.Skeleton_id)
                #print(r2._as_json())

            skel2 = _.proto.Skeleton()
            skel2(field1='500',field2='600')
            print(skel2._as_json())
            print(skel2._as_binary())
            skel2.field1 = 'skel'
            skel2.field2 = 'example'
            print(skel2._as_dict())
            print(skel2)
            print()

            r = _.proto.Reports()
            r.single = _.proto.Reports._single()
            r.single.source = 'matt'
            r.single.count = 10
            r.single.deep = _.proto.Reports._single._deep()
            r.single.deep.deep = 'DEEP'
            for x in range(4):
                m = _.proto.Reports._multiple()
                m.source=f'{x * x}'
                m.count = 11
                m.deep = _.proto.Reports._multiple._deep()
                m.deep.deep = 'D' * x
                m.count=x
                r.multiple.append(m)
            r.req = '88'

            #await self.db.insert(r)
            await self.db.upsert(r)
            for report in await self.db.find(_.proto.Reports):
                print('@@@@', report.Reports_id, report._as_json())
                await self.db.delete(report)

            print()

            await self.db.upsert(r)
            for report in await self.db.find(_.proto.Reports):
                print('###', report.Reports_id, report._as_json())

            z = _.proto.Reports()
            R = _.proto.Reports
            print()
            print('#' * 80)
            print(report.Reports_id)
            print(await self.db.delete(R, 1))
            print(await self.db.delete(R, 2))
            print('#' * 80)
            print()
            #r.Report_id = 1

            for report in await self.db.find(_.proto.Reports):
                print('###', report.Reports_id, report._as_json())

            #one = await self.db.find_one(_.proto.Reports, 3)
            #one.single.count=999
            #await self.db.update(one)

            #print(r._as_json())
            p = r._as_binary()
            r2 = _.proto.Reports._from_binary(p)
            #r2 = _.proto.Reports._from_json(r._as_json())
            print(r2)
            print()
            print(r2._as_binary())
            print()
            #print(r2._as_dict())
            print()
            #print(r2._as_json())
            print()
            print('_.data:', _.data)
            e = _.data.exo()
            e.u = uuid.uuid4()
            e.s = _.data.exo._s()
            e.s.v = 8
            print(e)
            #print(e._as_dict())
            #print(_.data.exo._from_json(e._as_json()))
            #print(_.data.exo._from_dict(e._as_dict()))
            print()
            for r in await self.db.find(_.data.exo):
                print(r._as_json())
            print(await self.db.find(_.data.exo))
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

    async def on_gitlab_login_success(self, handler, user):
        session = {
            'session_id' : str(uuid.uuid4()),
            'username'   : user['username'],
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        return session

    async def on_login_success(self, handler, user):
        user.last = int(time.time() * 1000)
        await _.databases.sqlite.upsert(user)

        session = {
            'session_id' : str(uuid.uuid4()),
            'username'   : user.username,
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        return session

    async def is_session_expired(self, session, expires):
        created = session.time / 1000
        elapsed = (time.time() - created) / 3600
        return elapsed > expires
