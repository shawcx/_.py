

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
        self._unique       = {}

    def column(self, column_name):
        self._columns[column_name] = Column(self, column_name)
        return self._columns[column_name]

    def default_id(self, default_id):
        self._default_id = default_id
        return self

    def primary_key(self, key):
        self._primary_keys[key] = True
        return self

    def foreign_key(self, key):
        #'UUID REFERENCES {table}({table}_id) ON DELETE CASCADE'.format(table=foreign_key.lower())
        self._foreign_keys[key] = True
        return self

    def unique(self, key):
        self._unique[key] = True
        return self

    def apply(self):
        table = self._name.lower()

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
        primary_keys = '","'.join(self._primary_keys.keys())
        if primary_keys:
            spec.append(f'PRIMARY KEY ("{primary_keys}")')
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