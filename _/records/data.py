
import dataclasses
import functools
import json

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
        # make class a dataclass if it isn't already
        if not dataclasses.is_dataclass(dataclass):
            dataclass = dataclasses.dataclass(init=False, kw_only=True)(dataclass)
        # add in the keyword init parent class
        dataclass = type(name, (dataclass,_DataClass), {})

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
                if unique:
                    table.unique(field.name)

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
        str:  'TEXT',
        int:  'INTEGER',
        bool: 'BOOLEAN',
        }


class _DataClass:
    def __init__(self, **kwds):
        for kwd in kwds:
            setattr(self, kwd, kwds[kwd])


class Interface(_.records.Interface):
    @classmethod
    def from_json(cls, msg):
        return cls(**json.loads(msg))

    @classmethod
    def as_dict(cls, _record=None):
        return dataclasses.asdict(_record)


class DataContainer(_.Container):
    def __init__(self):
        super().__init__()
        self._ignore = set()
        self._handler = {}

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
    def pkey(arg=True):
        meta = {'pkey':True}
        if isinstance(arg, dataclasses.Field):
            meta.update(arg.metadata)
        return dataclasses.field(metadata=meta)

    @staticmethod
    def uniq(arg=True):
        meta = {'unique':True}
        if isinstance(arg, dataclasses.Field):
            meta.update(arg.metadata)
        return dataclasses.field(metadata=meta)

    @staticmethod
    def ref(foreign, key=None):
        return dataclasses.field(metadata={'ref':foreign,'key':key})
