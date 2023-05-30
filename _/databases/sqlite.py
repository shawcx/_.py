#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import os
import sqlite3
import uuid

import _

try:
    import aiosqlite
except ImportError:
    raise _.error('Missing aiosqlite module')

logging.getLogger("aiosqlite").setLevel(logging.WARNING)


class SQLite(_.databases.Database):
    PH = '?'

    async def init(self, name, path=None, schema=None):
        self.conn = None

        if path is None:
            raise _.error(f'Specify "path" for SQLite {name}')

        aiosqlite.register_adapter(bool, int)
        aiosqlite.register_converter('BOOLEAN', lambda v: bool(int(v)))

        aiosqlite.register_adapter(uuid.UUID, str)
        aiosqlite.register_converter('UUID', lambda v: uuid.UUID(v))

        try:
            self.conn = await aiosqlite.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        except sqlite3.OperationalError:
            raise _.error('Unable to open database: %s', path)

        self.conn.row_factory = sqlite3.Row

        cursor = await self.conn.cursor()
        await cursor.execute('PRAGMA foreign_keys = ON;')
        await cursor.close()

        if not schema:
            return

        if not os.path.isfile(schema):
            schema = _.paths(schema)

        if os.path.isfile(schema):
            logging.info('Loading schema: %s', schema)
            with open(schema, 'r') as fp:
                cursor = await self.conn.cursor()
                await cursor.executescript(fp.read())
                await self.conn.commit()
        else:
            raise _.error('Schema not found: %s', schema)

    async def close(self):
        if self.conn:
            await self.conn.commit()
            await self.conn.close()

    async def execute(self, statement, args=None):
        lastrowid = 0
        cursor = await self.conn.cursor()
        try:
            await cursor.execute(statement, args)
            lastrowid = cursor.lastrowid
        except sqlite3.OperationalError as e:
            raise _.error('Operational error: %s', e)
        except sqlite3.ProgrammingError as e:
            raise _.error('Programming error: %s', e)
        except sqlite3.IntegrityError as e:
            raise _.error('Integrity error: %s', e)
        finally:
            await cursor.close()
        await self.conn.commit()
        return lastrowid

    async def find(self, table, params=None, order=None):
        statement = f'SELECT * FROM {table}'
        args = []
        if params:
            statement += f' WHERE {params[0]}={self.PH}'
            args.append(params[1])
        if order:
            statement += f' ORDER BY {order} DESC'

        cursor = await self.conn.cursor()
        await cursor.execute(statement, tuple(args))
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def find_one(self, table, id_column, value, order=None):
        statement = f'SELECT * FROM {table} WHERE {id_column}={self.PH}'
        if order:
            statement += f' ORDER BY {order} DESC'
        statement += ' LIMIT 1'

        try:
            cursor = await self.conn.cursor()
            await cursor.execute(statement, (value,))
        except sqlite3.OperationalError as e:
            raise _.error('%s', e)
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def count(self, table, field=None, value=None):
        statement = f'SELECT count(*) FROM {table}'
        args = None
        if field:
            statement += f' WHERE {field}={self.PH}'
            args = (value,)
        try:
            cursor = await self.conn.cursor()
            await cursor.execute(statement, args)
            result = await cursor.fetchone()
            return result[0]
        except sqlite3.ProgrammingError as e:
            raise _.error('Problem executing statement: %s', e)
        except sqlite3.IntegrityError as e:
            raise _.error('Integrity error: %s', e)
        finally:
            await cursor.close()

    async def insert(self, table, id_column, values):
        lastrowid = await super().insert(table, id_column, values)
        if id_column not in values:
            values[id_column] = lastrowid
        return lastrowid

    async def update(self, table, id_column, values):
        where = values.get(id_column)
        columns = ','.join(f'{s}={self.PH}' for s in values.keys())
        statement = f'UPDATE {table} SET {columns} WHERE {id_column}={self.PH}'
        return await self.execute(statement, tuple(values.values()) + (where,))

    async def upsert(self, table, values):
        columns = ','.join(f'"{s}"' for s in values.keys())
        placeholder = ','.join(self.PH * len(values))
        statement = f'INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholder})'
        return await self.execute(statement, tuple(values.values()))
