#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import json
import logging

import _


class DbLogin(_.logins.Login):
    _table    = 'users'
    _username = 'username'
    _password = 'password'

    @classmethod
    async def init(cls, name, database=None, table=None, username=None, password=None, **kwds):
        if database is None:
            if 1 == len(_.databases):
                cls._database = list(_.databases.keys())[0]
            else:
                raise _.error('dblogin requires a database to be specified')
        try:
            cls._db = _.databases[cls._database]
        except AttributeError:
            raise _.error('No database specified for %s', name)

        # if only one login specified use short argument
        prefix = f'{name}-' if len(_.config['logins']) > 1 else ''

        _.argparser.add_argument(f'--{prefix}add-user',
            metavar='<arg>', nargs=2,
            help='create or update user with password'
            )

        _.argparser.add_argument(f'--{prefix}list-users',
            action='store_true',
            help='list users'
            )

        schema = cls._db.schema(name)
        table = schema.table(cls._table)
        table.column(cls._username).primary_key()
        table.column(cls._password)
        for col,dbtype in kwds.items():
            table.column(col).type(dbtype)
        await schema.apply()

        members = {
            'name'     : name,
            'db'       : cls._db,
            'table'    : cls._table,
            'username' : cls._username,
            'password' : cls._password,
        }
        subclass = type('DBLoginRecords', (DBLoginRecords,), _.prefix(members))
        _.application._record_handler('logins', subclass)

    @classmethod
    async def args(cls, name):
        # if only one login specified use short argument
        prefix = f'{name}_' if len(_.config['logins']) > 1 else ''

        add_user = getattr(_.args, f'{prefix}add_user')
        if add_user:
            username,password = add_user
            password = _.auth.simple_hash(username + password)

            record = dict((k,None) for k in _.config[name])
            record.pop('database', None)
            record.pop('table',    None)

            record[cls._username] = username
            record[cls._password] = password

            callback = getattr(_.application, f'on_{name}_add_user', None)
            if callback is None:
                callback = getattr(_.application, 'on_dblogin_add_user', None)
            if callback:
                await _.wait(callback(name, record))

            await cls._db.upsert(cls._table, record)
            _.application.stop()

        if getattr(_.args, f'{prefix}list_users'):
            for user in await cls._db.find(cls._table):
                print(user[cls._username])
            _.application.stop()

    @classmethod
    async def check(cls, username, password):
        if password:
            password = _.auth.simple_hash(username + password)

        try:
            record = await cls._db.find_one(cls._table, cls._username, username)
        except _.error as e:
            logging.warning('%s', e)
            record = None

        if record is None:
            logging.warning('No user: %s', username)
            return None

        if password != record.get(cls._password, '!'):
            logging.warning('Bad password: %s', username)
            return None

        record.pop(cls._password)
        return record

    async def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)

        if username is None or password is None:
            raise _.HTTPError(500)

        user = await self.check(username, password)
        if user:
            await self.on_login_success(user)
        else:
            await self.on_login_failure()


class DBLoginRecords(_.handlers.Protected):
    # READ
    @_.auth.protected
    async def get(self, name, username=None):
        if username:
            record = await self._db.find_one(self._table, self._username, username)
            record.pop(self._password, None)
            self.write(record)
        else:
            records = await self._db.find(self._table)
            data = []
            for record in records:
                record = dict(record)
                record.pop(self._password, None)
                data.append(record)
            self.write({'data':data})

    # UPDATE
    @_.auth.protected
    async def put(self, username=None):
        try:
            user = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise _.HTTPError(500)

        username = user.get(self._username, None)
        password = user.pop(self._password, None)
        if not username or not password:
            raise _.HTTPError(500)

        entry = dict(_.config[self._name])
        prune = list(entry.keys()) + [self._username, self._password]
        for key in list(user.keys()):
            if key not in prune:
                user.pop(key)

        record = dict((k,None) for k in entry)
        record.pop('database', None)
        record.pop('table',    None)
        record.update(user)

        callback = getattr(_.application, f'on_{self._name}_update', None)
        if callback is None:
            callback = getattr(_.application, 'on_dblogin_update', None)
        if callback:
            await _.wait(callback(self._name, record))

        if not self._password not in record:
            password = _.auth.simple_hash(username + password)
            record[self._password] = password

        await self._db.insert(self._table, self._username, record)
        self.set_status(204)

    # DELETE
    @_.auth.protected
    async def delete(self, username=None):
        self.set_status(204)
        await self._db.delete(self._table, self._username, username)

        callback = getattr(_.application, f'on_{self._name}_delete', None)
        if callback is None:
            callback = getattr(_.application, 'on_dblogin_delete', None)
        if callback:
            await _.wait(callback(self, self._name, username))
