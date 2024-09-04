
import dataclasses
import functools
import inspect
import json
import typing
import uuid

import sqlalchemy

import _


class Data(_.records.Record):
    async def init(self, module, database=None):
        # setup the container beforehand so the data module can use data decorators
        if hasattr(_, self.name):
            raise _.error('Record name "%s" for "%s" conflicts in _ root', self.name, module.__name__)
        self._container = DataContainer()
        setattr(_, self.name, self._container)

        await super().init(module, database)

    def load(self, module):
        self.module = module
        for name in dir(module):
            if name.startswith('__'):
                continue

            if name in self._container._ignore:
                continue

            # ignore objects that are not classes
            attr = getattr(module, name)
            if not isinstance(attr, type(Data)):
                continue

            # ignore classes outside of module root
            if not attr.__module__.startswith(module.__name__):
                continue

            if self.db and not hasattr(attr, f'_{name}__no_table'):
                table_type = self._data_table(name, attr)
                self._container[name] = table_type

    def _data_table(self, name, dataclass, parent=None, parent_key=None, parent_col=None):
        # make class a dataclass if it isn't already
        if not dataclasses.is_dataclass(dataclass):
            dataclass = dataclasses.dataclass(init=True, kw_only=True)(dataclass)

        child_tables = {}
        annotations = {}
        members = {
            '__tablename__'   : name,
            '__annotations__' : annotations,
            }

        #members.update(dict(db=self.db, table=name))
        #types.append(_.records.DatabaseInterface)

        primary_key = None
        for field in dataclasses.fields(dataclass):
            # check if column should be primary key
            is_primary_key = field.metadata.get('pkey', False)
            if is_primary_key:
                if primary_key:
                    raise _.error('Only one primary key can be specified')
                primary_key = field.name

            unique = field.metadata.get('unique', False)

            if field.type.__module__.startswith(self.module.__name__):
                ref_table_name = f'{name}_{field.name}'
                annotations[field.name] = sqlalchemy.orm.Mapped[typing.Optional[ref_table_name]]
                members[field.name] = sqlalchemy.orm.relationship(
                    back_populates=name,
                    lazy='joined',
                    cascade="all, delete-orphan",
                    init=False,
                    )
                child_tables[ref_table_name] = field
            else:
                annotations[field.name] = typing.Optional[field.type]
                members[field.name] = sqlalchemy.orm.mapped_column(
                    primary_key=is_primary_key,
                    unique=unique,
                    init=False,
                    )

        if primary_key is None:
            primary_key = f'{name}_id'
            members[primary_key] = sqlalchemy.orm.mapped_column(
                sqlalchemy.INTEGER,
                primary_key=True,
                autoincrement=True,
                init=False,
                )

        if parent and parent_key and parent_col:
            members[f'{parent}_{parent_key}'] = sqlalchemy.orm.mapped_column(
                sqlalchemy.ForeignKey(f'{parent}.{parent_key}'),
                init=False,
                )
            members[f'{parent}'] = sqlalchemy.orm.relationship(
                parent,
                back_populates=parent_col,
                lazy='joined',
                init=False,
                )

        members['__primary_key__'] = primary_key

        table_type = type(name, (DataInterface,_.databases.Base,), members)

        for child_table,field in child_tables.items():
            child_type = self._data_table(child_table, field.type, parent=name, parent_key=primary_key, parent_col=field.name)
            setattr(table_type, f'_{field.name}', child_type)

        return table_type

def _dataclass(cls, msg, dst):
    for field in dataclasses.fields(cls):
        child_cls = getattr(cls, f'_{field.name}', None)
        if child_cls:
            child = child_cls()
            _dataclass(child_cls, msg.get(field.name), child)
            setattr(dst, field.name, child)
        else:
            setattr(dst, field.name, msg.get(field.name))

class DataInterface:
    def __call__(self, *args, **kwds):
        msg = args[0] if args else kwds
        _dataclass(self, msg, self)

    @classmethod
    def _from_dict(cls, *args, **kwds):
        msg = args[0] if args else kwds
        self = cls()
        _dataclass(cls, msg, self)
        return self

    @classmethod
    def _from_json(cls, msg):
        msg = json.loads(msg)
        self = cls()
        _dataclass(cls, msg, self)
        return self


class DataContainer(_.Container):
    def __init__(self):
        super().__init__()
        self._ignore = set()
        self._handler = {}

    # decorator for adding custom handlers for message types
    def handler(self, arg=None):
        def wrap(_handler):
            if arg:
                self._ignore.add(_handler.__name__)
                name = arg.__name__
            else:
                name = _handler.__name__
            self._handler[name] = _handler
            return _handler
        return wrap

    @staticmethod
    def dump(obj):
        return Interface.dump(obj)

    @staticmethod
    def db(cls):
        setattr(cls, f'_{cls.__name__}__db', True)
        return cls

    @staticmethod
    def no_table(cls):
        setattr(cls, f'_{cls.__name__}__no_table', True)
        return cls

    @staticmethod
    def no_handler(cls):
        setattr(cls, f'_{cls.__name__}__no_handler', True)
        return cls

    @staticmethod
    def pkey(arg=dataclasses.MISSING):
        kwds = {'metadata':{'pkey':True}}
        if isinstance(arg, dataclasses.Field):
            kwds['metadata'].update(arg.metadata)
            kwds['default'] = arg.default
            kwds['default_factory'] = arg.default_factory
        elif inspect.isfunction(arg):
            kwds['default_factory'] = arg
        elif arg is not dataclasses.MISSING:
            kwds['default'] = arg
        return dataclasses.field(**kwds)

    @staticmethod
    def uniq(group=None, arg=dataclasses.MISSING):
        if not isinstance(group, str):
            arg = group
            group = None
        kwds = {'metadata':{'unique':group}}
        if isinstance(arg, dataclasses.Field):
            kwds['metadata'].update(arg.metadata)
            kwds['default'] = arg.default
            kwds['default_factory'] = arg.default_factory
        elif inspect.isfunction(arg):
            kwds['default_factory'] = arg
        elif arg is not dataclasses.MISSING:
            kwds['default'] = arg
        return dataclasses.field(**kwds)

    #@staticmethod
    #def ref(foreign, key=None):
    #    return dataclasses.field(metadata={'ref':foreign,'key':key})
