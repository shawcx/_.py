#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import configparser
import logging
import os
import types
import typing

import sqlalchemy
import tornado.web
import google.protobuf.message
import google.protobuf.json_format

import _


class Protobuf(_.records.Record):
    async def init(self, module, **kwds):
        # setup the container beforehand so the data module can use data decorators
        if hasattr(_, self.component_name):
            raise _.error('Record name "%s" for "%s" conflicts in _ root', self.component_name, module.__name__)

        _.argparser.add_argument(f'--{self.component_name}',
            action='store_true',
            help='output Protobuf options template'
            )

        # options come from Protobuf.proto but need to be compiled in-line to avoid headaches
        self._options_name = f"{kwds.get('options', 'Protobuf')}_pb2"

        # container class for derived Python types
        self._container = _.Container()

        # access the types via the name or alias of the component
        setattr(_, self.component_name, self._container)

        # default to JSON style tables instead of relational
        try:
            self.relational = _.config.getboolean(self.component_name, 'relational')
        except configparser.NoOptionError:
            self.relational = False

        # default to creating handlers unless specified otherwise in the ini
        try:
            self.handlers = _.config.getboolean(self.component_name, 'handlers')
        except configparser.NoOptionError:
            self.handlers = True

        await super().init(module, **kwds)

    @classmethod
    async def args(cls, component_name):
        if getattr(_.args, component_name, False):
            path = os.path.join(os.path.dirname(__file__), 'Protobuf.proto')
            protobuf = open(path, 'r').read()
            print(protobuf)
            _.application.stop()

    def load(self, module):
        try:
            self._options = getattr(module, self._options_name)
        except AttributeError:
            raise _.error('Cannot find protobuf module "%s"', self._options_name)
        self.load_module(module)
        del self._module_name

    def load_module(self, module):
        self._module_name = module.__name__
        for member_name in dir(module):
            # ignore the options file
            if member_name == self._options_name:
                continue

            # get a handle to the pb2 module descriptor
            member = getattr(module, member_name)

            # all proto messages end with _pb2
            if not member_name.endswith('_pb2'):
                # load submodules for nested protobufs
                if isinstance(member, types.ModuleType):
                    self._container[member_name] = _.Container()
                    stash = (self._container,self._module_name)
                    self._container = self._container[member_name]
                    self.load_module(member)
                    (self._container,self._module_name) = stash
                continue

            # iterate over all the message definitions
            for name in member.DESCRIPTOR.message_types_by_name:
                message = getattr(member, name)
                options = message.DESCRIPTOR.GetOptions()

                if self.db and not options.Extensions[self._options.no_table]:
                    record_type = self._proto_table(name, message=message)
                else:
                    record_type = type(name, (ProtoInterface,), {'_ProtoInterface__pb' : message,})

                self._container[name] = record_type

                if self.handlers and not options.Extensions[self._options.no_handler]:
                    self._proto_handler(name, record_type, module.__name__)

    def _proto_table(self, name, message=None, descriptor=None, parent=None, parent_key=None, parent_col=None):
        child_tables = {}
        annotations  = {}

        members = {
            '__tablename__'   : name,
            '__annotations__' : annotations,
            '__module__'      : self._module_name,
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
            is_primary_key = col_options.Extensions[self._options.pkey]
            if is_primary_key:
                if primary_key:
                    raise _.error('Only one primary key can be specified')
                primary_key = field.name

            # check if column should be unique
            unique = col_options.Extensions[self._options.uniq]

            # get the scalar type of the field or dict if message
            column_type = Protobuf._proto_field_mapping[field.type]
            if column_type is dict:
                if is_primary_key:
                    raise _.error('Message type cannot be primary key')

                if not self.relational: # JSON
                    column_type = dict[str, typing.Any]
                else: # flat tables
                    ref_table_name = f'{name}_{field.name}'
                    column_type = ref_table_name

                if field.label is field.LABEL_REPEATED:
                    column_type = list[column_type]

                column_type = sqlalchemy.orm.Mapped[typing.Optional[column_type]]

                annotations[field.name] = column_type

                if not self.relational: # JSON
                    members[field.name] = sqlalchemy.orm.mapped_column(
                        None,
                        primary_key=is_primary_key,
                        unique=unique,
                        init=False,
                        )
                else:
                    members[field.name] = sqlalchemy.orm.relationship(
                        back_populates=name,
                        lazy='joined',
                        cascade="all, delete-orphan",
                        init=False,
                        )
                    child_tables[ref_table_name] = field
            else:
                explicit_type = None
                if column_type is bytes:
                    explicit_type = self.db.BYTES
                # support repeated field types
                if field.label is field.LABEL_REPEATED:
                    if column_type is str:
                        explicit_type = sqlalchemy.ARRAY(sqlalchemy.TEXT)
                    column_type = list[column_type]

                column_type = sqlalchemy.orm.Mapped[typing.Optional[column_type]]

                # check for foreign key
                if col_options.HasExtension(self._options.ref):
                    print('TODO: FKEY:', col_options.Extensions[self._options.ref])

                annotations[field.name] = column_type

                members[field.name] = sqlalchemy.orm.mapped_column(
                    explicit_type,
                    primary_key=is_primary_key,
                    unique=unique,
                    init=False,
                    )

        table_options = descriptor.GetOptions()

        if table_options.HasExtension(self._options.id):
            primary_key = table_options.Extensions[self._options.id]
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

        table_type = type(name, (ProtoInterface,self.db.Base,), members)

        for child_table,field in child_tables.items():
            child_type = self._proto_table(child_table, descriptor=field.message_type, parent=name, parent_key=primary_key, parent_col=field.name)
            setattr(table_type, f'_{field.name}', child_type)

        return table_type

    def _proto_handler(self, name, record_type, module_name):
        ## check if a custom handler was defined
        proto_handler = _handlers.get(name)
        if proto_handler:
            name = proto_handler.__name__
            module_name = proto_handler.__module__
        types = [proto_handler] if proto_handler else [_.records.HandlerInterface]
        types.append(tornado.web.RequestHandler)

        record_handler = type(name, tuple(types), {
            '_component' : name,
            '_db'        : self.db,
            '_record'    : record_type,
            '__module__' : module_name,
            })

        _.application._record_handler(self.component_name, record_handler)

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


class ProtoInterface(_.records.RecordsInterface):
    @staticmethod
    def __descriptor(cls, descriptor, msg, dst):
        for field in descriptor.fields:
            if field.type is field.TYPE_MESSAGE:
                child_cls = getattr(cls, f'{field.name}')
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
        msg = google.protobuf.json_format.MessageToJson(pb)
        self = cls()
        self.__descriptor(cls, pb.DESCRIPTOR, msg, self)
        return self

    def _as_pb(self):
        pb = self.__pb()
        try:
            google.protobuf.json_format.ParseDict(self._as_dict(), pb)
        except google.protobuf.json_format.ParseError as e:
            raise _.error('%s', e) from None
        return pb.SerializeToString()


_handlers = {}
def handle(_message):
    def wrap(_handler):
        _handlers[_message.DESCRIPTOR.name] = _handler
        return _handler
    return wrap


#class ProtobufContainer(_.Container):
#    _handlers = {}
#
#    # decorator for adding custom handlers for message types
#    def handles(self, _message):
#        def wrap(_handler):
#            self._handlers[_message.DESCRIPTOR.name] = _handler
#            return _handler
#        return wrap

if '__main__' == __name__:
    path = os.path.join(os.path.dirname(__file__), 'Protobuf.proto')
    protobuf = open(path, 'r').read()
    print(protobuf)
