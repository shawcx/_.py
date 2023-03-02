
import _
import tornado.web


class Records(_.handlers.Protected):
    @tornado.web.authenticated
    async def get(self, record, record_id=None):
        if not record_id:
            records = await self.application.db.find(record)
            self.write(dict(data=[dict(r) for r in records]))
        else:
            record = await self.application.db.findOne(record, record_id, 'username')
            self.write(record)


class Users(_.handlers.Protected):
    @tornado.web.authenticated
    async def get(self, record_id=None):
        if not record_id:
            records = await self.application.db.find('users')
            data = []
            for record in records:
                record = dict(record)
                record.pop('password', None)
                data.append(record)
            self.write(dict(data=data))
        else:
            record = await self.application.db.findOne('users', record_id, 'username')
            record = dict(record)
            record.pop('password', None)
            self.write(record)