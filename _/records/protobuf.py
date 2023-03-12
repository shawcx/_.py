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


class Protobuf(_.records.Record):
    _proto_handlers = {}

    def load(self, module):
        if hasattr(_, self.name):
            raise _.error('Record name "%s" for "%s" conflicts in _ root', self.name, module.__name__)
        self._container = _.Container()
        setattr(_, self.name, self._container)

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

        members = dict(name=name,record_cls=message)
        types   = [Interface]
        if not table_options.Extensions[Protobuf_pb2.no_db]:
            members.update(dict(db=self.db, table=name))
            types.append(_.records.DatabaseInterface)

            table = self.schema.table(name)
            if table_options.HasExtension(Protobuf_pb2.id):
                table.default_id(table_options.Extensions[Protobuf_pb2.id])

            # iterate over message to determine columns
            for field in message.DESCRIPTOR.fields:
                column = table.column(field.name)
                column.type(Protobuf._column_mapping[field.type])

                col_options = field.GetOptions()
                # check if column should be a primary key
                if col_options.Extensions[Protobuf_pb2.pkey]:
                    column.primary_key()
                    members['primary_key'] = field.name
                # check for foreign key
                if col_options.HasExtension(Protobuf_pb2.ref):
                    table.foreign_key(col_options.Extensions[Protobuf_pb2.ref])
                if field.label is field.LABEL_REPEATED:
                    column.repeated()

        # Protobuf does not want you to subclass the Message
        # so we dynamically create a thin wrapper
        record = type(name, tuple(types), _.prefix(members))
        self._container[name] = record

        if not table_options.Extensions[Protobuf_pb2.no_handler]:
            members['record'] = record

            # check if a custom handler was defined
            handler = Protobuf._proto_handlers.get(message, None)
            types = [handler] if handler else []
            # add the base records handler
            types.append(_.records.HandlerInterface)

            handler = type(name, tuple(types), _.prefix(members))
            _.application._record_handler(self.name, handler)

    _column_mapping = [
        None,
        'DOUBLE PRECISION', # DOUBLE
        'REAL',             # FLOAT
        'BIGINT',           # INT64
        'NUMERIC',          # UINT64
        'INTEGER',          # INT32
        'NUMERIC',          # FIXED64
        'BIGINT',           # FIXED32
        'BOOLEAN',          # BOOL
        'TEXT',             # STRING
        'JSONB',            # GROUP
        'JSONB',            # MESSAGE
        'BYTEA',            # BYTES
        'BIGINT',           # UINT32
        'INTEGER',          # ENUM
        'INTEGER',          # SFIXED32
        'BIGINT',           # SFIXED64
        'INTEGER',          # SINT32
        'BIGINT',           # SINT64
        ]


class Interface(_.records.Interface):
    def __init__(self, _record=None):
        self.__dict__['_record'] = _record if _record else self._record_cls()

    @classmethod
    def load(cls, msg):
        _record = cls._record_cls()
        google.protobuf.json_format.Parse(msg, _record)
        return cls(_record)

    @classmethod
    def dict(cls, _record):
        return google.protobuf.json_format.MessageToDict(
            _record,
            including_default_value_fields = True,
            preserving_proto_field_name    = True,
            )


# decorator for adding custom handlers for message types
def handler(message):
    def wrap(proto_handler):
        Protobuf._proto_handlers[message] = proto_handler
        return proto_handler
    return wrap


# function to compile protobuf files for underscore apps
if '__main__' == __name__:
    root = os.path.dirname(_.__file__)
    root = os.path.abspath(os.path.join(root, '..'))
    print(root)
