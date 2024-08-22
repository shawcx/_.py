#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import logging
import os

import google.protobuf.message
import google.protobuf.json_format

import _

from . import Protobuf_pb2

import sqlalchemy


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
        for member in dir(module):
            # all proto messages end with _pb2
            if not member.endswith('_pb2'):
                continue
            # get a handle to the pb2 module descriptor
            pb2 = getattr(module, member)
            # iterate over all the message definitions
            for name,descriptor in pb2.DESCRIPTOR.message_types_by_name.items():
                message = getattr(pb2, name)
                self._message(name, message)

    def _message(self, name, message):
        table_options = message.DESCRIPTOR.GetOptions()

        members = dict(
            name       = name,
            record_cls = message
            )

        types = [Interface]
        if not table_options.Extensions[Protobuf_pb2.no_db]:
            types.append(_.records.DatabaseInterface)
            members.update(dict(db=self.db, __table__=name.lower()))

            columns = []

            # iterate over message to determine columns
            for field in message.DESCRIPTOR.fields:
                column_type = Protobuf._column_mapping[field.type]
                column_type = getattr(self.db, column_type)

                # support repeated field types
                if field.label is field.LABEL_REPEATED:
                    column_type = sqlalchemy.ARRAY(column_type)

                column = sqlalchemy.Column(field.name, column_type)

                col_options = field.GetOptions()

                # check if column should be a primary key
                if col_options.Extensions[Protobuf_pb2.pkey]:
                    column.primary_key = True

                # check for foreign key
                if col_options.HasExtension(Protobuf_pb2.ref):
                    print('TODO: FKEY:', col_options.Extensions[Protobuf_pb2.ref])

                columns.append(column)

            if table_options.HasExtension(Protobuf_pb2.id):
                column_name = table_options.Extensions[Protobuf_pb2.id]
                column = sqlalchemy.Column(column_name, sqlalchemy.INTEGER, primary_key=True)
                columns.append(column)

            table = sqlalchemy.Table(name.lower(), _.databases.meta, *columns)

        # Protobuf does not want you to subclass the Message
        # so we dynamically create a thin wrapper
        record = type(name, tuple(types), _.prefix(members))

        self._container[name] = record

        if not table_options.Extensions[Protobuf_pb2.no_handler]:
            members['record'] = record

            # check if a custom handler was defined
            proto_handler = self._container._handler.get(name)
            types = [proto_handler] if proto_handler else []
            # add the base records handler
            types.append(_.records.HandlerInterface)

            record_handler = type(name, tuple(types), _.prefix(members))
            _.application._record_handler(self.name, record_handler)

    _column_mapping = [
        None,
        'DOUBLE',  # DOUBLE
        'REAL',    # FLOAT
        'BIGINT',  # INT64
        'NUMERIC', # UINT64
        'INTEGER', # INT32
        'NUMERIC', # FIXED64
        'BIGINT',  # FIXED32
        'BOOLEAN', # BOOL
        'TEXT',    # STRING
        'JSON',    # GROUP
        'JSON',    # MESSAGE
        'BYTES',   # BYTES
        'BIGINT',  # UINT32
        'INTEGER', # ENUM
        'INTEGER', # SFIXED32
        'BIGINT',  # SFIXED64
        'INTEGER', # SINT32
        'BIGINT',  # SINT64
        ]


class Interface(_.records.Interface):
    @classmethod
    def from_json(cls, msg):
        _record = cls._record_cls()
        google.protobuf.json_format.Parse(msg, _record)
        return cls(_record)

    @classmethod
    def as_dict(cls, obj):
        return google.protobuf.json_format.MessageToDict(
            obj._record,
            always_print_fields_with_no_presence = True,
            preserving_proto_field_name          = True,
            )


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
