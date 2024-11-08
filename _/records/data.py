
import dataclasses
import functools
import inspect
import logging
import json
import typing
import uuid

import sqlalchemy
import tornado.web

import _


class Data(_.records.Record):
    async def init(self, module, **kwds):
        # setup the container beforehand so the data module can use data decorators
        if hasattr(_, self.component_name):
            raise _.error('Record name "%s" for "%s" conflicts in _ root', self.component_name, module.__name__)
        self._container = DataContainer()
        setattr(_, self.component_name, self._container)
        await super().init(module, **kwds)

    def load(self, module):
        self.module_name = module.__name__
        for name in dir(module):
            if name.startswith('__'):
                continue

            if name in self._container._ignore:
                continue

            # ignore objects that are not classes
            cls = getattr(module, name)
            if not isinstance(cls, type(Data)):
                continue

            # ignore classes outside of module root
            if not cls.__module__.startswith(self.module_name):
                continue

            if self.db and not hasattr(cls, f'_{name}__no_table'):
                try:
                    record_type = self._data_table(name, cls)
                except Exception as e:
                    logging.exception('%s', e)
            else:
                if not dataclasses.is_dataclass(cls):
                    cls = dataclasses.dataclass(init=False, kw_only=True)(cls)
                record_type = type(name, (DataInterface,cls), {})

            self._container[name] = record_type

            if not hasattr(cls, f'_{name}__no_handler'):
                self._data_handler(name, record_type)

    def _data_table(self, name, cls, parent=None, parent_key=None, parent_col=None):
        child_tables = {}
        annotations = {}
        members = {
            '__tablename__'   : name,
            '__annotations__' : annotations,
            }

        # make class a dataclass if it isn't already
        if not dataclasses.is_dataclass(cls):
            cls = dataclasses.dataclass(init=False, kw_only=True)(cls)

        primary_key = None
        for field in dataclasses.fields(cls):
            # check if column should be primary key
            is_primary_key = field.metadata.get('pkey', False)
            if is_primary_key:
                if primary_key:
                    raise _.error('Only one primary key can be specified')
                primary_key = field.name

            uniq = field.metadata.get('uniq', False)
            refs = field.metadata.get('refs', None)

            if refs:
                annotations[field.name] = sqlalchemy.orm.Mapped[typing.Optional[field.type]]
                members[field.name] = sqlalchemy.orm.mapped_column(
                    sqlalchemy.ForeignKey(refs, ondelete="CASCADE"),
                    init=False,
                    )
            elif field.type.__module__.startswith(self.module_name):
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
                    unique=uniq,
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
                sqlalchemy.ForeignKey(f'{parent}.{parent_key}', ondelete="CASCADE"),
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

    def _data_handler(self, name, record_type):
        data_handler = self._container._handlers.get(name)
        if data_handler:
            name = data_handler.__name__

        types = [data_handler] if data_handler else [_.records.HandlerInterface]
        types.append(tornado.web.RequestHandler)

        record_handler = type(name, tuple(types), {
            '_component' : name,
            '_db'        : self.db,
            '_record'    : record_type,
            '__module__' : self.module_name,
            })
        
        _.application._record_handler(self.component_name, record_handler)


class DataInterface(_.records.RecordsInterface):
    @staticmethod
    def __dataclass(cls, msg, dst):
        for field in dataclasses.fields(cls):
            child_cls = getattr(cls, f'_{field.name}', None)
            if child_cls:
                child = child_cls()
                DataInterface.__dataclass(child_cls, msg.get(field.name), child)
                setattr(dst, field.name, child)
            else:
                if field.name in msg:
                    setattr(dst, field.name, msg[field.name])

    def __call__(self, *args, **kwds):
        msg = args[0] if args else kwds
        self.__dataclass(self, msg, self)
        return self

    @classmethod
    def _from_dict(cls, *args, **kwds):
        msg = args[0] if args else kwds
        self = cls()
        self.__dataclass(cls, msg, self)
        return self

    @classmethod
    def _from_json(cls, msg):
        msg = json.loads(msg)
        self = cls()
        self.__dataclass(cls, msg, self)
        return self


class DataContainer(_.Container):
    def __init__(self):
        super().__init__()
        self._ignore = set()
        self._handlers = {}

    # decorator for adding custom handlers for message types
    def handles(self, _datacls):
        def wrap(_handler):
            self._ignore.add(_handler.__name__)
            self._handlers[_datacls.__name__] = _handler
            return _handler
        return wrap

    @staticmethod
    def dump(obj):
        return DataInterface.dump(obj)

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
        return dataclasses.field(metadata={'pkey':True})

    @staticmethod
    def uniq(group=None, arg=dataclasses.MISSING):
        return dataclasses.field(metadata={'uniq':True})

    @staticmethod
    def refs(table_column):
        return dataclasses.field(metadata={'refs':table_column})
