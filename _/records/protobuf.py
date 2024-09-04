#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import dataclasses
import logging
import os
import sys
import typing

import sqlalchemy
import google.protobuf.message
import google.protobuf.json_format

import _

from . import Protobuf_pb2


class Protobuf(_.records.Record):
    async def init(self, module, database=None):
        # setup the container beforehand so the data module can use data decorators
        if hasattr(_, self.name):
            raise _.error('Record name "%s" for "%s" conflicts in _ root', self.name, module.__name__)
        self._container = ProtobufContainer()
        setattr(_, self.name, self._container)

        await super().init(module, database)

    def load(self, module):
        # iterate over all the members of the protobuf modules
        self.package = module.__package__ + '.'
        for member in dir(module):
            # all proto messages end with _pb2
            if not member.endswith('_pb2'):
                continue
            # get a handle to the pb2 module descriptor
            pb2 = getattr(module, member)
            # iterate over all the message definitions
            for name,descriptor in pb2.DESCRIPTOR.message_types_by_name.items():
                message = getattr(pb2, name)

                table_options = message.DESCRIPTOR.GetOptions()
                if self.db and not table_options.Extensions[Protobuf_pb2.no_table]:
                    table_type = self._proto_table(name, message=message)
                    self._container[name] = table_type

                if table_options.Extensions[Protobuf_pb2.handler]:
                    members = {
                        'name' : name,
                    }
                    #members['record'] = record
                    ## check if a custom handler was defined
                    proto_handler = self._container._handler.get(name)
                    types = [proto_handler] if proto_handler else []
                    # add the base records handler
                    types.append(_.records.HandlerInterface)

                    #record_handler = type(name, tuple(types), _.prefix(members))
                    #_.application._record_handler(self.name, record_handler)

    def _proto_table(self, name, message=None, descriptor=None, parent=None, parent_key=None, parent_col=None):
        child_tables = {}
        annotations  = {}

        members = {
            '__tablename__'   : name,
            '__annotations__' : annotations,
            }

        if message:
            members['_ProtoInterface__pb'] = message

        if descriptor is None:
            descriptor = message.DESCRIPTOR

        primary_key = None
        # iterate over message to determine columns
        for field in descriptor.fields:
            col_options = field.GetOptions()

            # check if column should be primary key
            is_primary_key = col_options.Extensions[Protobuf_pb2.pkey]
            if is_primary_key:
                if primary_key:
                    raise _.error('Only one primary key can be specified')
                primary_key = field.name

            column_type = Protobuf._proto_field_mapping[field.type]
            if column_type is dict:
                if is_primary_key:
                    raise _.error('Message type cannot be primary key')

                ref_table_name = f'{name}_{field.name}'
                column_type = ref_table_name
                if field.label is field.LABEL_REPEATED:
                    column_type = typing.List[column_type]
                else:
                    column_type = typing.Optional[column_type]
                column_type = sqlalchemy.orm.Mapped[column_type]

                annotations[field.name] = column_type

                members[field.name] = sqlalchemy.orm.relationship(
                    back_populates=name,
                    lazy='joined',
                    cascade="all, delete-orphan",
                    init=False,
                    )

                child_tables[ref_table_name] = field
            else:
                # support repeated field types
                if field.label is field.LABEL_REPEATED:
                    column_type = typing.List[column_type]
                column_type = sqlalchemy.orm.Mapped[column_type]

                # check if column should be unique
                unique = col_options.Extensions[Protobuf_pb2.uniq]

                # check for foreign key
                if col_options.HasExtension(Protobuf_pb2.ref):
                    print('TODO: FKEY:', col_options.Extensions[Protobuf_pb2.ref])

                annotations[field.name] = column_type

                members[field.name] = sqlalchemy.orm.mapped_column(
                    primary_key=is_primary_key,
                    unique=unique,
                    init=False,
                    )

        table_options = descriptor.GetOptions()

        if table_options.HasExtension(Protobuf_pb2.id):
            primary_key = table_options.Extensions[Protobuf_pb2.id]
            members[primary_key] = sqlalchemy.orm.mapped_column(
                sqlalchemy.INTEGER,
                primary_key=True,
                autoincrement=True,
                init=False,
                )
        elif primary_key is None:
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

        table_type = type(name, (ProtoInterface,_.databases.Base,), members)

        for child_table,field in child_tables.items():
            child_type = self._proto_table(child_table, descriptor=field.message_type, parent=name, parent_key=primary_key, parent_col=field.name)
            setattr(table_type, f'_{field.name}', child_type)

        return table_type

    # TODO: try mapping to sqlalchemy.types
    _proto_field_mapping = [
        None,
        float,     # DOUBLE
        float,     # FLOAT
        int,       # INT64
        int,       # UINT64
        int,       # INT32
        int,       # FIXED64
        int,       # FIXED32
        bool,      # BOOL
        str,       # STRING
        dict,      # GROUP - deprecated
        dict,      # MESSAGE
        bytes,     # BYTES
        int,       # UINT32
        int,       # ENUM
        int,       # SFIXED32
        int,       # SFIXED64
        int,       # SINT32
        int,       # SINT64
        ]



class ProtoInterface:
    @staticmethod
    def __descriptor(cls, descriptor, msg, dst):
        for field in descriptor.fields:
            if field.type is field.TYPE_MESSAGE:
                child_cls = getattr(cls, f'_{field.name}')
                if field.label == field.LABEL_REPEATED:
                    dst_list = getattr(dst, field.name)
                    for item in getattr(msg, field.name):
                        child = child_cls()
                        ProtoInterface.__descriptor(child_cls, field.message_type, item, child)
                        dst_list.append(child)
                else:
                    child = child_cls()
                    ProtoInterface.__descriptor(child_cls, field.message_type, getattr(msg, field.name), child)
                    setattr(dst, field.name, child)
            else:
                setattr(dst, field.name, getattr(msg, field.name))

    def __call__(self, *args, **kwds):
        msg = args[0] if args else kwds
        pb = self.__pb()
        try:
            google.protobuf.json_format.ParseDict(msg, pb)
        except google.protobuf.json_format.ParseError as e:
            raise _.error('%s', e) from None
        self.__descriptor(self, pb.DESCRIPTOR, pb, self)

    @classmethod
    def _from_dict(cls, *args, **kwds):
        msg = args[0] if args else kwds
        pb = cls.__pb()
        try:
            google.protobuf.json_format.ParseDict(msg, pb)
        except google.protobuf.json_format.ParseError as e:
            raise _.error('%s', e) from None
        self = cls()
        self.__descriptor(cls, pb.DESCRIPTOR, pb, self)
        return self

    @classmethod
    def _from_json(cls, msg):
        pb = cls.__pb()
        try:
            google.protobuf.json_format.Parse(msg, pb)
        except google.protobuf.json_format.ParseError as e:
            raise _.error('%s', e) from None
        self = cls()
        self.__descriptor(cls, pb.DESCRIPTOR, pb, self)
        return self

    @classmethod
    def _from_pb(cls, packed):
        pb = cls.__pb()
        pb.ParseFromString(packed)
        self = cls()
        self.__descriptor(cls, pb.DESCRIPTOR, pb, self)
        return self

    def _as_pb(self):
        pb = self.__pb()
        try:
            google.protobuf.json_format.ParseDict(self._as_dict(), pb)
        except google.protobuf.json_format.ParseError as e:
            raise _.error('%s', e) from None
        return pb.SerializeToString()


class ProtobufContainer(_.Container):
    def __init__(self):
        super().__init__()
        self._handler = {}

    # decorator for adding custom handlers for message types
    def handler(self, _message):
        def wrap(_handler):
            self._handler[_message.DESCRIPTOR.name] = _handler
            return _handler
        return wrap


# function to compile protobuf files for underscore apps
if '__main__' == __name__:
    root = os.path.dirname(_.__file__)
    root = os.path.abspath(os.path.join(root, '..'))
    print(root)
