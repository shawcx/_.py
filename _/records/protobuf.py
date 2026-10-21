#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import configparser
import dataclasses
import datetime
import json
import keyword
import logging
import os
import types
import typing

import sqlalchemy
import tornado.web
import google.protobuf.descriptor
import google.protobuf.message
import google.protobuf.message_factory
import google.protobuf.json_format

import _


def _repeated(field):
    # FieldDescriptor.label was removed in protobuf 7
    try:
        return field.is_repeated
    except AttributeError:
        return field.label == field.LABEL_REPEATED


def _attr(name):
    'the record attribute for a field, Python keywords get a trailing underscore'
    return f'{name}_' if keyword.iskeyword(name) else name


def _check_names(descriptor):
    # a keyword field such as "from" becomes attribute "from_", which mustn't be taken
    names = {field.name for field in descriptor.fields}
    for field in descriptor.fields:
        if keyword.iskeyword(field.name) and _attr(field.name) in names:
            raise _.error('Field "%s" in %s clashes with the attribute for "%s"',
                _attr(field.name), descriptor.full_name, field.name)


def _renamed(descriptor):
    'attribute to field name for fields whose attribute differs'
    return {_attr(f.name):f.name for f in descriptor.fields if _attr(f.name) != f.name}


# well-known types that get native columns and Python values
_WKT = {
    'google.protobuf.Timestamp'   : 'timestamp',
    'google.protobuf.Duration'    : 'duration',
    'google.protobuf.Struct'      : 'json',
    'google.protobuf.Value'       : 'json',
    'google.protobuf.ListValue'   : 'json',
    'google.protobuf.DoubleValue' : 'wrapper',
    'google.protobuf.FloatValue'  : 'wrapper',
    'google.protobuf.Int64Value'  : 'wrapper',
    'google.protobuf.UInt64Value' : 'wrapper',
    'google.protobuf.Int32Value'  : 'wrapper',
    'google.protobuf.UInt32Value' : 'wrapper',
    'google.protobuf.BoolValue'   : 'wrapper',
    'google.protobuf.StringValue' : 'wrapper',
    'google.protobuf.BytesValue'  : 'wrapper',
    }


def _wkt(field):
    'the kind of well-known type for a single field, None for anything else'
    if field.message_type is None or _repeated(field):
        return None
    return _WKT.get(field.message_type.full_name)


def _is_wkt_message(field):
    'true for single and repeated well-known type fields'
    return field.message_type is not None and field.message_type.full_name in _WKT


def _from_wkt(kind, msg):
    if kind == 'timestamp':
        return msg.ToDatetime(tzinfo=datetime.timezone.utc)
    if kind == 'duration':
        return msg.ToTimedelta()
    if kind == 'wrapper':
        return msg.value
    return google.protobuf.json_format.MessageToDict(msg)


def _to_wkt(kind, value, msg):
    msg.SetInParent()
    if kind in ('timestamp', 'duration') and isinstance(value, str):
        # RFC 3339 times and durations such as "1.5s"
        msg.FromJsonString(value)
    elif kind == 'timestamp':
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        msg.FromDatetime(value)
    elif kind == 'duration':
        msg.FromTimedelta(value)
    elif kind == 'wrapper':
        msg.value = _scalar(msg.DESCRIPTOR.fields_by_name['value'], value)
    else:
        google.protobuf.json_format.ParseDict(value, msg)


def _is_map(field):
    return field.message_type is not None and field.message_type.GetOptions().map_entry


def _is_message(field):
    return field.type == field.TYPE_MESSAGE


def _json_form(pb):
    'the proto3 JSON form of a message, keeping the field names from the .proto'
    return google.protobuf.json_format.MessageToDict(pb,
        always_print_fields_with_no_presence = True,
        preserving_proto_field_name          = True,
        )


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
        self._container = ProtobufContainer()

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
        self._package = module.__name__
        # container path of the subpackage being loaded, e.g. ['sub']
        self._path = []
        self.load_module(module)
        del self._module_name
        del self._path

    def load_module(self, module):
        self._module_name = module.__name__
        for member_name in dir(module):
            # ignore the options file
            if member_name == self._options_name:
                continue

            # get a handle to the pb2 module descriptor
            member = getattr(module, member_name)

            # ignore anything that isn't a module from this package
            if not isinstance(member, types.ModuleType):
                continue
            if not member.__name__.startswith(self._package + '.'):
                continue

            # all proto messages end with _pb2
            if not member_name.endswith('_pb2'):
                # ignore any module starting with _
                if not member_name.startswith('_'):
                    # load submodules for nested protobufs
                    self._container[member_name] = ProtobufContainer(self._container.handlers)
                    stash = (self._container,self._module_name)
                    self._container = self._container[member_name]
                    self._path.append(member_name)
                    self.load_module(member)
                    self._path.pop()
                    (self._container,self._module_name) = stash
                continue

            # iterate over all the message definitions
            for name in member.DESCRIPTOR.message_types_by_name:
                message = getattr(member, name)
                options = message.DESCRIPTOR.GetOptions()

                # subpackage messages get their own tables and routes,
                # pbt.sub.Tags is table sub_Tags served at /<component>/sub/Tags
                table_name = '_'.join(self._path + [name])
                route      = '/'.join(self._path + [name])

                _check_names(message.DESCRIPTOR)
                if self.db and not options.Extensions[self._options.no_table]:
                    record_type = self._proto_table(table_name, message=message)
                else:
                    # declare the message fields so _as_dict has something to return
                    fields = message.DESCRIPTOR.fields
                    members = {_attr(f.name):None for f in fields}
                    members['__annotations__'] = {_attr(f.name):typing.Any for f in fields}
                    members['_ProtoInterface__pb'] = message
                    members['_proto_children'] = {}
                    members['_proto_renamed'] = _renamed(message.DESCRIPTOR)
                    record_type = type(name, (ProtoInterface,), members)
                    record_type = dataclasses.dataclass(init=False, kw_only=True)(record_type)

                self._container[name] = record_type

                if self.handlers and not options.Extensions[self._options.no_handler]:
                    self._proto_handler(route, record_type, module.__name__, message.DESCRIPTOR.full_name)

    def _proto_table(self, name, message=None, descriptor=None, parent=None, parent_key=None, parent_col=None, ordered=False):
        child_tables = {}
        annotations  = {}

        members = {
            '__tablename__'   : name,
            '__annotations__' : annotations,
            '__module__'      : self._module_name,
            }

        if descriptor is None:
            descriptor = message.DESCRIPTOR
        if message is None:
            # child tables build their message class from the descriptor
            message = google.protobuf.message_factory.GetMessageClass(descriptor)
        members['_ProtoInterface__pb'] = message
        _check_names(descriptor)

        primary_key = None
        required    = []
        # iterate over message to determine columns
        for field in descriptor.fields:
            col_options = field.GetOptions()
            where = f'{descriptor.full_name}.{field.name}'
            attr  = _attr(field.name)

            # the field stays in the message but isn't stored
            if col_options.Extensions[self._options.no_column]:
                if col_options.Extensions[self._options.pkey]:
                    raise _.error('%s: a primary key must be stored', where)
                continue

            # unset values are refused before the record is stored
            is_required = col_options.Extensions[self._options.required]
            if is_required:
                required.append(field.name)

            # check if column should be primary key
            is_primary_key = col_options.Extensions[self._options.pkey]
            if is_primary_key:
                if primary_key:
                    raise _.error('Only one primary key can be specified')
                primary_key = attr
                primary_column = field.name

            # check if column should be unique
            unique = col_options.Extensions[self._options.uniq]

            if _is_message(field) and is_primary_key:
                raise _.error('Message type cannot be primary key')
            if _repeated(field) and is_primary_key:
                raise _.error('Repeated field cannot be primary key')

            # foreign key given as "Table.column"
            foreign_key = []
            if col_options.HasExtension(self._options.ref):
                ref = col_options.Extensions[self._options.ref]
                if '.' not in ref:
                    raise _.error('%s: ref must be "Table.column", not "%s"', where, ref)
                if _is_message(field) or _repeated(field):
                    raise _.error('%s: only single scalar fields can have a ref', where)
                foreign_key = [sqlalchemy.ForeignKey(ref)]

            kind = _wkt(field)
            if _is_message(field) and self.relational and not _is_map(field) and not _is_wkt_message(field):
                # messages become child tables, maps and well-known types don't
                ref_table_name = f'{name}_{field.name}'
                ordering = {}
                if _repeated(field):
                    annotations[attr] = sqlalchemy.orm.Mapped[list[ref_table_name]]
                    # keep repeated children in the order they were given, _before_save
                    # numbers them; not ordering_list, as session.merge() resets it
                    ordering = dict(order_by=f'{ref_table_name}._position')
                else:
                    annotations[attr] = sqlalchemy.orm.Mapped[typing.Optional[ref_table_name]]
                members[attr] = sqlalchemy.orm.relationship(
                    back_populates=name,
                    lazy='joined',
                    cascade="all, delete-orphan",
                    passive_deletes=True,
                    init=False,
                    **ordering,
                    )
                child_tables[ref_table_name] = field
                continue

            if kind:
                # well-known types get native columns
                column_type = self._wkt_column_type(kind, field)
            elif _is_message(field):
                # messages and maps are stored in their proto3 JSON form
                column_type = (self.db.JSON or sqlalchemy.JSON)(none_as_null=True)
            else:
                column_type = self._column_type(field)
                if _repeated(field):
                    # TEXT[] rather than VARCHAR[] to match existing tables
                    if field.type == field.TYPE_STRING:
                        column_type = sqlalchemy.TEXT()
                    column_type = self.db.array(column_type)

            annotations[attr] = sqlalchemy.orm.Mapped[typing.Optional[typing.Any]]
            members[attr] = sqlalchemy.orm.mapped_column(
                column_type,
                *foreign_key,
                name=field.name,
                primary_key=is_primary_key,
                unique=unique,
                init=False,
                **({'nullable' : False} if is_required else {}),
                )

        table_options = descriptor.GetOptions()

        if table_options.HasExtension(self._options.id):
            primary_key = primary_column = table_options.Extensions[self._options.id]
            members[primary_key] = sqlalchemy.orm.mapped_column(
                sqlalchemy.INTEGER,
                primary_key=True,
                autoincrement=True,
                init=False,
                )
        elif primary_key is None:
            primary_key = primary_column = f'{name}_id'
            members[primary_key] = sqlalchemy.orm.mapped_column(
                sqlalchemy.INTEGER,
                primary_key=True,
                autoincrement=True,
                init=False,
                )

        if ordered:
            # unannotated so it stays out of _as_dict, like the foreign key
            members['_position'] = sqlalchemy.orm.mapped_column(
                sqlalchemy.INTEGER,
                init=False,
                default=None,
                )

        if parent and parent_key and parent_col:
            members[f'{parent}_{parent_key}'] = sqlalchemy.orm.mapped_column(
                sqlalchemy.ForeignKey(f'{parent}.{parent_key}', ondelete='CASCADE'),
                init=False,
                )
            members[f'{parent}'] = sqlalchemy.orm.relationship(
                parent,
                back_populates=parent_col,
                lazy='joined',
                init=False,
                )

        members['__primary_key__'] = primary_key
        members['_proto_children'] = {}
        members['_proto_required'] = tuple(required)
        members['_proto_renamed']  = _renamed(descriptor)

        table_type = type(name, (ProtoInterface,self.db.Base,), members)

        # refuse to store a record that its message can't represent, child
        # tables too as they can be updated without their parent
        sqlalchemy.event.listen(table_type, 'before_insert', _validate)
        sqlalchemy.event.listen(table_type, 'before_update', _validate)

        for child_table,field in child_tables.items():
            # the foreign key names the parent's column, which differs from the attribute for keywords
            child_type = self._proto_table(child_table, descriptor=field.message_type, parent=name, parent_key=primary_column, parent_col=_attr(field.name), ordered=_repeated(field))
            table_type._proto_children[field.name] = child_type
            setattr(table_type, f'_{field.name}', child_type)

        return table_type

    def _proto_handler(self, route, record_type, module_name, full_name):
        ## check if a custom handler was defined
        proto_handler = self._container.handlers.get(full_name)
        # the default handler needs a table
        if not proto_handler and not hasattr(record_type, '__table__'):
            return

        handler_name = route.replace('/', '_')
        if proto_handler:
            handler_name = proto_handler.__name__
            module_name = proto_handler.__module__
        types = [proto_handler] if proto_handler else [_.records.HandlerInterface]
        types.append(tornado.web.RequestHandler)

        # served at the message's route, whichever handler class is used
        record_handler = type(handler_name, tuple(types), {
            '_component' : route,
            '_db'        : self.db,
            '_record'    : record_type,
            '__module__' : module_name,
            })

        _.application._record_handler(self.component_name, record_handler)

    def _wkt_column_type(self, kind, field):
        if kind == 'timestamp':
            return _.databases.UTCDateTime()
        if kind == 'duration':
            return sqlalchemy.Interval()
        if kind == 'wrapper':
            return self._column_type(field.message_type.fields_by_name['value'])
        return (self.db.JSON or sqlalchemy.JSON)(none_as_null=True)

    def _column_type(self, field):
        F = google.protobuf.descriptor.FieldDescriptor
        if field.type in (F.TYPE_DOUBLE, F.TYPE_FLOAT):
            return sqlalchemy.Float()
        if field.type == F.TYPE_BOOL:
            return sqlalchemy.Boolean()
        if field.type == F.TYPE_STRING:
            return sqlalchemy.String()
        if field.type == F.TYPE_BYTES:
            return (self.db.BYTES or sqlalchemy.LargeBinary)()
        if field.type in (F.TYPE_UINT64, F.TYPE_FIXED64):
            return _.databases.UInt64()
        # the remaining integers and enums all fit in a BIGINT
        return sqlalchemy.BIGINT()


class ProtoInterface(_.records.RecordsInterface):
    'converts between records and protobuf messages'

    # child table classes by field name, only used in relational mode
    _proto_children = {}
    # fields marked (required) in the .proto
    _proto_required = ()
    # attribute to field name where they differ, e.g. from_ for from
    _proto_renamed = {}

    def _before_save(self):
        '''called by the database before an insert or merge, numbers repeated
           children by their place in the list so they load in that order'''
        loaded = sqlalchemy.inspect(self).dict if hasattr(self, '__table__') else {}
        for name in self._proto_children:
            children = loaded.get(_attr(name))
            if isinstance(children, list):
                for index,child in enumerate(children):
                    child._position = index
            for child in children if isinstance(children, list) else [children] if children else []:
                child._before_save()

    def _check_required(self):
        for name in self._proto_required:
            if getattr(self, _attr(name), None) is None:
                raise _.error('%s.%s is required', type(self).__name__, name)
        for name in self._proto_children:
            children = getattr(self, _attr(name), None) or []
            for child in children if isinstance(children, list) else [children]:
                child._check_required()

    def _assign_pb(self, pb):
        'set the record fields from a protobuf message'
        json_form = None
        for field in pb.DESCRIPTOR.fields:
            child_type = self._proto_children.get(field.name)
            value = getattr(pb, field.name)
            kind = _wkt(field)
            if kind:
                value = _from_wkt(kind, value) if pb.HasField(field.name) else None
            elif _is_message(field) and not child_type:
                if json_form is None:
                    json_form = _json_form(pb)
                # unset singular messages are left out of the JSON form
                value = json_form.get(field.name)
            elif child_type:
                if _repeated(field):
                    value = [child_type()._assign_pb(item) for item in value]
                elif pb.HasField(field.name):
                    value = child_type()._assign_pb(value)
                else:
                    value = None
            elif _repeated(field):
                value = list(value)
            elif field.has_presence and not pb.HasField(field.name):
                # optional and oneof fields that were not set
                value = None
            setattr(self, _attr(field.name), value)
        return self

    def _fill_pb(self, pb):
        'set the fields of a protobuf message from the record'
        json_form = {}
        for field in pb.DESCRIPTOR.fields:
            value = getattr(self, _attr(field.name), None)
            if value is None:
                continue
            kind = _wkt(field)
            if kind:
                _to_wkt(kind, value, getattr(pb, field.name))
            elif _is_message(field) and not self._proto_children.get(field.name):
                json_form[field.name] = value
            elif _is_message(field):
                if _repeated(field):
                    for item in value:
                        item._fill_pb(getattr(pb, field.name).add())
                else:
                    getattr(pb, field.name).SetInParent()
                    value._fill_pb(getattr(pb, field.name))
            elif _repeated(field):
                getattr(pb, field.name).extend(_scalar(field, v) for v in value)
            else:
                setattr(pb, field.name, _scalar(field, value))
        if json_form:
            google.protobuf.json_format.ParseDict(json_form, pb)
        return pb

    def _as_dict(self):
        '''the proto3 JSON form of the record, plus a generated primary key so
           clients can address it'''
        _dict = _json_form(self._as_pb())
        key = self._generated_key()
        if key:
            _dict[key] = getattr(self, key, None)
        return _dict

    @classmethod
    def _generated_key(cls):
        'the primary key when it is a column the message lacks, e.g. order_id'
        key = getattr(cls, '__primary_key__', None)
        if key is None or key in {_attr(f.name) for f in cls.__pb.DESCRIPTOR.fields}:
            return None
        return key

    @classmethod
    def _split_key(cls, msg):
        '''take a generated primary key out of a dict before it is parsed into
           the message, so a record's own _as_dict output can be read back'''
        key = cls._generated_key()
        if not key or not isinstance(msg, dict) or key not in msg:
            return msg,None,None
        msg = dict(msg)
        return msg,key,msg.pop(key)

    @classmethod
    def _parse(cls, parse, *args):
        pb = cls.__pb()
        try:
            parse(*args, pb)
        except (google.protobuf.json_format.ParseError, google.protobuf.message.DecodeError) as e:
            raise _.error('%s', e) from None
        return pb

    def __call__(self, *args, **kwds):
        msg,key,value = self._split_key(args[0] if args else kwds)
        self._assign_pb(self._parse(google.protobuf.json_format.ParseDict, msg))
        if key:
            setattr(self, key, value)
        return self

    @classmethod
    def _from_dict(cls, *args, **kwds):
        return cls()(*args, **kwds)

    @classmethod
    def _from_json(cls, msg):
        try:
            msg = json.loads(msg)
        except ValueError as e:
            raise _.error('%s', e) from None
        return cls._from_dict(msg)

    @classmethod
    def _from_binary(cls, packed):
        pb = cls.__pb()
        try:
            pb.ParseFromString(packed)
        except google.protobuf.message.DecodeError as e:
            raise _.error('%s', e) from None
        return cls()._assign_pb(pb)

    @classmethod
    def _from_pb(cls, pb):
        return cls()._assign_pb(pb)

    def _as_binary(self):
        return self._as_pb().SerializeToString()

    def _as_pb(self):
        try:
            return self._fill_pb(self.__pb())
        except (google.protobuf.json_format.ParseError, TypeError, ValueError, KeyError) as e:
            raise _.error('%s', e) from None


def _validate(mapper, connection, record):
    # raises _.error when a required field is unset or a field doesn't fit
    # the message, e.g. an unknown nested key
    record._check_required()
    record._as_pb()


def _scalar(field, value):
    # databases can return Decimal for integers and float columns
    F = google.protobuf.descriptor.FieldDescriptor
    if field.type in (F.TYPE_DOUBLE, F.TYPE_FLOAT):
        return float(value)
    if field.type == F.TYPE_ENUM and isinstance(value, str):
        return field.enum_type.values_by_name[value].number
    if field.type not in (F.TYPE_STRING, F.TYPE_BYTES, F.TYPE_BOOL):
        return int(value)
    return value


class ProtobufContainer(_.Container):
    def __init__(self, handlers=None):
        super().__init__()
        # custom handlers by message full name, shared with subpackage containers
        self.handlers = {} if handlers is None else handlers

    # decorator for adding custom handlers for message types
    def handles(self, _message):
        def wrap(_handler):
            self.handlers[_message.DESCRIPTOR.full_name] = _handler
            return _handler
        return wrap

MessageToDict = _json_form

class ProtoJSONEncoder(_.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'DESCRIPTOR'):
            return MessageToDict(obj)
        return _.JSONEncoder.default(self, obj)

json._default_encoder = ProtoJSONEncoder()


if '__main__' == __name__:
    path = os.path.join(os.path.dirname(__file__), 'Protobuf.proto')
    protobuf = open(path, 'r').read()
    print(protobuf)