
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

        await super(Data, self).init(module, database)

    def load(self, module):
        for name in dir(module):
            if name.startswith('__'):
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

    def _dataclass(self, name, cls):
        # make class a dataclass if it isn't already
        if not dataclasses.is_dataclass(cls):
            cls = dataclasses.dataclass(init=False, kw_only=True)(cls)

        members = dict(name=name)
        types   = [Interface]
        if not hasattr(cls, f'_{cls.__name__}__no_db'):
            members.update(dict(db=self.db, table=name))
            types.append(_.records.DatabaseInterface)

            table = self.schema.table(name)
            for field in dataclasses.fields(cls):
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

            if hasattr(cls, f'_{cls.__name__}__no_pkey'):
                table.primary_key(None)

        cls = type(name, (cls,_DataClass), {})

        members['record_cls'] = cls
        record = type(name, tuple(types), _.prefix(members))
        self._container[name] = record

        if not hasattr(cls, f'_{cls.__name__}__no_handler'):
            members['record'] = record
            record_handler = type(name, (_.records.HandlerInterface,), _.prefix(members))
            _.application._record_handler(self.name, record_handler)

        return cls

    _column_mapping = {
        str:  'TEXT',
        int:  'INTEGER',
        bool: 'BOOLEAN',
        }


class Interface(_.records.Interface):
    def __init__(self, *args, **kwds):
        self.__dict__['_record'] = self._record_cls()
        for kwd in kwds:
            setattr(self._record, kwd, kwds[kwd])

    @classmethod
    def load(cls, msg):
        return cls(**json.loads(msg))

    @classmethod
    def dict(cls, _record=None):
        return dataclasses.asdict(_record)


class _DataClass:
    def __init__(self, **kwds):
        for kwd in kwds:
            setattr(self, kwd, kwds[kwd])


class DataContainer(_.Container):
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
