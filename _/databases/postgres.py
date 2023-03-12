#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import re

import _

try:
    import psycopg
except ImportError:
    raise _.error('Missing psycopg (PostgreSQL) module')


class Postgres(_.databases.Database):
    async def init(self, name, **kwds):
        self.dsn = ' '.join('{0}={1}'.format(k, v) for k,v in kwds.items())

        sanitized = re.sub('password=[^ ]*', 'password=****', self.dsn)
        logging.info('DSN: %s', sanitized)

        try:
            self.conn = await psycopg.AsyncConnection.connect(self.dsn,
                row_factory=psycopg.rows.dict_row
                )
        except psycopg.OperationalError as e:
            raise _.error('%s', e) from None

    async def close(self):
        pass

    async def execute(self, statement, args):
        return await self.db.execute(statement, args)

    async def find(self, table, params=None, sort=None):
        statement = f'SELECT * FROM {table}'
        if params:
            statement += ' WHERE ' + params
        if sort:
            statement += ' ' + sort

        cursor = await self.execute(statement)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def find_one(self, table, id_column, _id):
        statement = f'SELECT * FROM {table} WHERE {id_column}=%s'
        cursor = await self.execute(statement, [_id])
        return cursor.fetchone()

    async def insert(self, table, id_column, values):
        cursor = await super().insert(table, id_column, values)
        rows = cursor.rowcount
        if rows is None:
            rows = -1
        if id_column not in values:
            cursor = await self.execute('SELECT lastval()')
            values[id_column] = cursor.fetchone()[0]
        return rows

    async def update(self, table, id_column, values):
        _id = values[id_column]
        columns = ','.join('"%s"=%%s' % s.lower() for s in values.keys())
        statement = 'UPDATE {0} SET {1} WHERE {2}=%s'.format(table, columns, id_column)

        cursor = await self.execute(statement, values.values() + [_id])

        rows = cursor.rowcount
        if rows is None:
            rows = -1

        return rows

    async def upsert(self, table, id_column, values):
        rows = await self.insert_unique(table, values, id_column)
        if rows <= 0:
            rows = await self.update(table, values, id_column)
        return rows

    async def insert_unique(self, table, id_column, values):
        columns = ','.join('"%s"' % k.lower() for k in values.keys())
        placeholder = ','.join('%s' for x in xrange(len(values)))
        statement = f'''INSERT INTO {table} ({columns}) VALUES {placeholder}
            WHERE NOT EXISTS (select {id_column} from {table} where {id_column} = '{values[id_column]}')'''

        cursor = await self.execute(statement, values.values())

        rows = cursor.rowcount
        if rows is None:
            rows = -1
        return rows
