#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import datetime
import importlib
import json
import logging
import os
import uuid

import google.protobuf.json_format

import _

from . import Records_pb2


class Protobuf(_.records.Record):
    async def init(self, name, module, database=None):
        try:
            imported = importlib.import_module(module)
        except ModuleNotFoundError:
            raise _.error('Unknown module: %s', module)
        if database:
            db = _.database[database]
            schema = db.schema(module)
            __generate(schema, imported)
            await _.wait(schema.apply())

    class Json(_.records.Json):
        def default(self, obj):
            if hasattr(obj, 'DESCRIPTOR'):
                return Protobuf.dict(obj)
            return super(Json, self).default(obj)

    @staticmethod
    def dict(message):
        return google.protobuf.json_format.MessageToDict(
            message,
            including_default_value_fields = True,
            preserving_proto_field_name    = True,
            )

    @staticmethod
    def dumps(obj, **kwds):
        return json.dumps(obj, cls=Protobuf.Json, separators=(',',':'), **kwds)

    @staticmethod
    def loads(text, message):
        return google.protobuf.json_format.Parse(text, message)


def _Protobuf__generate(schema, imported):
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

    # iterate over all the members of the protobuf modules
    for member in dir(imported):
        # all proto messages end with _pb2
        if not member.endswith('_pb2'):
            continue
        # get a handle to the pb2 module descriptor
        descriptor = getattr(imported, member).DESCRIPTOR

        # iterate over all the message definitions
        for name,message in descriptor.message_types_by_name.items():
            options = message.GetOptions()

            # ignore messages explicitly defined as not a table
            if options.HasExtension(Records_pb2.ignore):
                if options.Extensions[Records_pb2.ignore]:
                    continue

            table = schema.table(name)
            if options.HasExtension(Records_pb2.default_id):
                table.default_id(options.Extensions[Records_pb2.default_id])

            # iterate over message to determine columns
            for field in message.fields:
                column = table.column(field.name)
                column.type(_column_mapping[field.type])

                options = field.GetOptions()
                # check if column should be a primary key
                if options.HasExtension(Records_pb2.primary_key):
                    if options.Extensions[Records_pb2.primary_key]:
                        column.primary_key()
                # check for foreign key
                if options.HasExtension(Records_pb2.foreign_key):
                    table.foreign_key(options.Extensions[Records_pb2.foreign_key])
                if field.label is field.LABEL_REPEATED:
                    column.repeated()