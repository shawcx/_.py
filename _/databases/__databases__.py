#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import collections
import logging

import _


class Database:
    PH = None

    @classmethod
    async def _(cls, name, **kwds):
        self = cls()
        _.databases[name] = self
        await self.init(name, **kwds)

    async def init(self, **kwds):
        pass

    async def close(self):
        pass

    async def find(self, table, params=None, order=None):
        raise NotImplementedError

    async def find_one(self, table, id_column, _id, order=None):
        raise NotImplementedError

    async def insert(self, table, id_column, values):
        columns = ','.join(f'"{s}"' for s in values.keys())
        placeholder = ','.join(self.PH * len(values))
        statement = f'INSERT INTO {table} ({columns}) VALUES ({placeholder})'
        return await self.execute(statement, tuple(values.values()))

    async def insert_unique(self, table, id_column, values):
        raise NotImplementedError

    async def upsert(self, table, id_column, values):
        raise NotImplementedError

    async def update(self, table, id_column, values):
        raise NotImplementedError

    async def delete(self, table, id_column, value):
        statement = f'DELETE FROM {table} WHERE {id_column}={self.PH}'
        await self.execute(statement, (value,))

    def schema(self, name):
        return Schema(self, name)


class Schema:
    def __init__(self, parent, name):
        self._parent = parent
        self._name   = name
        self._tables = {}

    def table(self, table_name):
        self._tables[table_name] = Table(table_name)
        return self._tables[table_name]

    async def apply(self):
        for table_name,table in self._tables.items():
            try:
                statement = table.apply()
                await self._parent.execute(statement)
            except _.error as e:
                raise _.error('%s: %s', self._name, e)


class Table:
    def __init__(self, name):
        self._name         = name
        self._default_id   = '_id'
        self._columns      = {}
        self._primary_keys = {}
        self._foreign_keys = {}
        self._unique       = collections.defaultdict(set)

    def column(self, column_name):
        if column_name not in self._columns:
            self._columns[column_name] = Column(self, column_name)
        return self._columns[column_name]

    def default_id(self, default_id):
        self._default_id = default_id
        return self

    def primary_key(self, key):
        if key is None:
            self._primary_keys = None
        else:
            self._primary_keys[key] = True
        return self

    def foreign_key(self, key):
        self._foreign_keys[key] = True
        return self

    def unique(self, key, group=None):
        self._unique[group].add(key)
        return self

    def apply(self):
        table = self._name.lower()

        if self._primary_keys is not None:
            if not self._primary_keys:
                if self.default_id not in self._columns:
                    column = self.column(self._default_id)
                self._primary_keys[self._default_id] = True

            for key in self._primary_keys:
                try:
                    self._columns[key].null(False)
                except KeyError:
                    raise _.error('primary key for non-existent field: %s.%s', self._name, key)

        spec = [c.apply() for c in self._columns.values()]

        if self._primary_keys: # may be None
            primary_keys = '","'.join(self._primary_keys.keys())
            spec.append(f'PRIMARY KEY ("{primary_keys}")')

        for group,names in self._unique.items():
            unique = '","'.join(names)
            if unique:
                spec.append(f'UNIQUE ("{unique}")')

        spec = ',\n  '.join(spec)
        return f'CREATE TABLE IF NOT EXISTS {self._name.lower()} (\n  {spec}\n  )'


class Column:
    def __init__(self, table, name):
        self._table     = table
        self._name      = name
        self._type      = 'TEXT'
        self._repeated  = False
        self._null      = True
        self._reference = None

    def type(self, column_type=None):
        self._type = column_type if column_type is not None else 'TEXT'
        return self

    def primary_key(self):
        self._table.primary_key(self._name)
        return self

    def references(self, reference, key):
        self._null = True
        self._reference = (reference,key)

    def repeated(self, repeatable=True):
        self._repeated = repeatable
        return self

    def null(self, nullable):
        self._null = nullable
        return self

    def apply(self):
        not_null = ' NOT NULL' if not self._null else ''
        if self._reference:
            table = self._reference[0]
            key   = self._reference[1] or self.__name
            reference = f' REFERENCES {table}("{key}") ON DELETE CASCADE'
        else:
            reference = ''
        return f'"{self._name}" {self._type.upper()}{not_null}{reference}'
