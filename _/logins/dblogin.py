#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import json
import logging
import typing

import sqlalchemy

import _


class DbLogin(_.logins.Login):
    _table    = 'users'
    _username = 'username'
    _password = 'password'

    @classmethod
    async def init(cls, component_name, database=None, table=None, username=None, password=None, **kwds):
        cls._database = database
        if database is None:
            if 1 == len(_.databases):
                cls._database = list(_.databases.keys())[0]
            else:
                raise _.error('dblogin requires a database to be specified')
        try:
            cls._db = _.databases[cls._database]
        except AttributeError:
            raise _.error('No database specified for %s', component_name)

        # if only one login specified use short argument
        prefix = f'{component_name}-' if len(_.config['logins']) > 1 else ''

        _.argparser.add_argument(f'--{prefix}add-user',
            metavar='<arg>', nargs=2,
            help='create or update user with password'
            )

        _.argparser.add_argument(f'--{prefix}list-users',
            action='store_true',
            help='list users'
            )

        # create the dblogin table
        annotations = {
            cls._username : typing.Optional[str],
            cls._password : typing.Optional[str],
            }
        columns = {
            '__tablename__'   : cls._table,
            '__annotations__' : annotations,
            '__primary_key__' : cls._username,
            cls._username : sqlalchemy.orm.mapped_column(primary_key=True, init=False),
            cls._password : sqlalchemy.orm.mapped_column(init=False),
            }

        for col,dbtype in kwds.items():
            if not dbtype:
                dbtype = 'str'
            annotations[col] = typing.Optional[__builtins__.get(dbtype)]
            columns[col] = sqlalchemy.orm.mapped_column(init=False)

        table_cls = type(cls._table, (_.databases.Base,), columns)
        await cls._db.create_tables()

        cls._table = table_cls

        members = {
            'component' : component_name,
            'db'        : cls._db,
            'table'     : cls._table,
            'username'  : cls._username,
            'password'  : cls._password,
        }
        subclass = type('DBLoginRecords', (DBLoginRecords,), _.prefix(members))
        _.application._record_handler('logins', subclass)

    @classmethod
    async def args(cls, component_name):
        # if only one login specified use short argument
        prefix = f'{component_name}_' if len(_.config['logins']) > 1 else ''

        add_user = getattr(_.args, f'{prefix}add_user')
        if add_user:
            username,password = add_user
            password = _.auth.simple_hash(username + password)

            record = dict((k,None) for k in _.config[component_name])
            record.pop('database', None)
            record.pop('table',    None)

            record[cls._username] = username
            record[cls._password] = password

            callback = getattr(_.application, f'on_{component_name}_add_user', None)
            if callback is None:
                callback = getattr(_.application, 'on_dblogin_add_user', None)
            if callback:
                await _.wait(callback(component_name, record))

            user = cls._table._from_dict(**record)
            await cls._db.upsert(user)
            _.application.stop()

        if getattr(_.args, f'{prefix}list_users'):
            for user in await cls._db.find(cls._table):
                user = user._as_dict()
                user.pop(cls._password)
                print(', '.join(f'{k}: {v}' for k,v in user.items()))
            _.application.stop()

    @classmethod
    async def check(cls, username, password):
        if password:
            password = _.auth.simple_hash(username + password)

        account = cls._table()
        setattr(account, cls._username, username)

        try:
            record = await cls._db.find_one(cls._table, username)
        except _.error as e:
            logging.warning('%s', e)
            record = None

        if record is None:
            logging.warning('No user: %s', username)
            return None

        if password != record[cls._password]:
            logging.warning('Bad password: %s', username)
            return None

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
    async def get(self, component_name, username=None):
        if username:
            record = await self._db.find_one(self._table, username)
            record = record._as_dict()
            record.pop(self._password, None)
            self.write(record)
        else:
            records = await self._db.find(self._table)
            data = []
            for record in records:
                record = record._as_dict()
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

        entry = dict(_.config[self._component])
        prune = list(entry.keys()) + [self._username, self._password]
        for key in list(user.keys()):
            if key not in prune:
                user.pop(key)

    # TODO: this needs to be updated
        record = dict((k,None) for k in entry)
        record.pop('database', None)
        record.pop('table',    None)
        record.update(user)

        callback = getattr(_.application, f'on_{self._component}_update', None)
        if callback is None:
            callback = getattr(_.application, 'on_dblogin_update', None)
        if callback:
            await _.wait(callback(self._component, record))

        if not self._password not in record:
            password = _.auth.simple_hash(username + password)
            record[self._password] = password

        await self._db.insert(record)
        self.set_status(204)

    # DELETE
    @_.auth.protected
    async def delete(self, username=None):
        self.set_status(204)
        if username is None:
            return

        user = await self._db.find_one(self._table, username)
        await self._db.delete(user)

        callback = getattr(_.application, f'on_{self._component}_delete', None)
        if callback is None:
            callback = getattr(_.application, 'on_dblogin_delete', None)
        if callback:
            await _.wait(callback(self, self._component, username))
