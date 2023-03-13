
import dataclasses
import functools
import inspect
import json
import uuid

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
        for name in dir(module):
            if name.startswith('__'):
                continue

            if name in self._container._ignore:
                continue

            attr = getattr(module, name)

            # ignore objects that are not classes
            if not isinstance(attr, type(Data)):
                continue

            # ignore classes outside of module root
            if not attr.__module__.startswith(module.__name__):
                continue

            attr = self._dataclass(name, attr)
            setattr(module, name, attr)

    def _dataclass(self, name, dataclass):
        for member,member_cls in dataclass.__annotations__.items():
            if not hasattr(dataclass, member):
                setattr(dataclass, member, None)

        # make class a dataclass if it isn't already
        if not dataclasses.is_dataclass(dataclass):
            dataclass = dataclasses.dataclass(init=True, kw_only=True)(dataclass)

        members = dict(
            name       = name,
            record_cls = dataclass
            )

        types = [Interface]
        if not hasattr(dataclass, f'_{dataclass.__name__}__no_db'):
            members.update(dict(db=self.db, table=name))
            types.append(_.records.DatabaseInterface)

            table = self.schema.table(name)
            for field in dataclasses.fields(dataclass):
                column = table.column(field.name)
                column.type(Data._column_mapping.get(field.type))

                if field.metadata.get('pkey', False):
                    column.primary_key()
                    members['primary_key'] = field.name

                unique = field.metadata.get('unique', False)
                if unique is not False:
                    table.unique(field.name, unique)

                reference = field.metadata.get('ref', None)
                if reference:
                    key = field.metadata.get('key', None)
                    column.references(reference.__name__, key)

            if hasattr(dataclass, f'_{dataclass.__name__}__no_pkey'):
                table.primary_key(None)

        record = type(name, tuple(types), _.prefix(members))
        self._container[name] = record

        if not hasattr(dataclass, f'_{dataclass.__name__}__no_handler'):
            members['record'] = record

            # check if a custom handler was defined
            data_handler = self._container._handler.get(dataclass.__name__)
            types = [data_handler] if data_handler else []
            # add the base records handler
            types.append(_.records.HandlerInterface)

            record_handler = type(name, tuple(types), _.prefix(members))
            _.application._record_handler(self.name, record_handler)

        return dataclass

    _column_mapping = {
        str:       'TEXT',
        int:       'INTEGER',
        float:     'REAL',
        bool:      'BOOLEAN',
        uuid.UUID: 'UUID',
        }


class Interface(_.records.Interface):
    @classmethod
    def from_json(cls, msg):
        return cls(**json.loads(msg))

    @classmethod
    def as_dict(cls, obj):
        return dataclasses.asdict(obj._record)


class DataContainer(_.Container):
    def __init__(self):
        super().__init__()
        self._ignore = set()
        self._handler = {}

    @staticmethod
    def json(obj, **kwds):
        return json.dumps(obj, cls=Data.Json, separators=(',',':'), **kwds)

    # decorator for adding custom handlers for message types
    def handler(self, _dataclass):
        def wrap(_handler):
            self._ignore.add(_handler.__name__)
            self._handler[_dataclass.__name__] = _handler
            return _handler
        return wrap

    @staticmethod
    def dump(obj):
        return Interface.dump(obj)

    @staticmethod
    def no_db(cls):
        setattr(cls, f'_{cls.__name__}__no_db', True)
        return cls

    @staticmethod
    def no_handler(cls):
        setattr(cls, f'_{cls.__name__}__no_handler', True)
        return cls

    @staticmethod
    def no_pkey(cls):
        setattr(cls, f'_{cls.__name__}__no_pkey', True)
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

    @staticmethod
    def ref(foreign, key=None):
        return dataclasses.field(metadata={'ref':foreign,'key':key})
