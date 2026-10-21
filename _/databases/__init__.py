#
# (c) 2015-2024 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import base64
import io
import logging
import typing

import _

try:
    import sqlalchemy
    import sqlalchemy.types
    import sqlalchemy.orm
    from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
except ImportError:
    raise _.error('Missing sqlalchemy module')

logging.getLogger('alembic').setLevel(logging.WARNING)


class UInt64(sqlalchemy.types.TypeDecorator):
    '''unsigned 64-bit integer: NUMERIC(20) on Postgres, otherwise stored in
       a BIGINT as its two's complement so values of 2**63 and up fit'''
    impl     = sqlalchemy.BIGINT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(sqlalchemy.NUMERIC(20, 0))
        return dialect.type_descriptor(sqlalchemy.BIGINT())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == 'postgresql':
            return value
        return value - (1 << 64) if value >= (1 << 63) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return int(value)
        return value + (1 << 64) if value < 0 else value


class JSONArray(sqlalchemy.types.TypeDecorator):
    'list stored as JSON for databases without arrays, bytes as base64'
    impl     = sqlalchemy.JSON
    cache_ok = True

    def __init__(self, binary=False):
        super().__init__()
        self.binary = binary

    def process_bind_param(self, value, dialect):
        if value is not None and self.binary:
            value = [base64.b64encode(v).decode('ascii') for v in value]
        return value

    def process_result_value(self, value, dialect):
        if value is not None and self.binary:
            value = [base64.b64decode(v) for v in value]
        return value


class Database:
    TEXT    = sqlalchemy.TEXT
    INTEGER = sqlalchemy.INTEGER
    BIGINT  = sqlalchemy.BIGINT
    #DOUBLE  = sqlalchemy.DOUBLE_PRECISION
    NUMERIC = sqlalchemy.NUMERIC
    REAL    = sqlalchemy.REAL
    BOOLEAN = sqlalchemy.BOOLEAN
    JSON    = None
    BYTES   = None
    UUID    = None

    TYPE_ANNOTATION_MAP = {}

    @classmethod
    async def _(cls, component_name, **kwds):
        self = cls()
        self.component_name = component_name
        # each database gets its own models and metadata
        self.Base = self._declarative_base()
        self.check_schema = kwds.pop('check_schema', 'true').lower() not in ('false', 'no', 'off', '0')
        _.databases[component_name] = self
        setattr(_, component_name, self)

        _.argparser.add_argument(f'--{component_name}-migrate',
            action='store_true',
            help=f'Apply schema changes to the {component_name} database'
            )

        await self.init(component_name, **kwds)

    def _declarative_base(self):
        class Base(
                sqlalchemy.ext.asyncio.AsyncAttrs,
                sqlalchemy.orm.MappedAsDataclass,
                sqlalchemy.orm.DeclarativeBase,
                ):
            'base class for _.records'
            type_annotation_map = self.TYPE_ANNOTATION_MAP
        return Base

    async def init(self, component_name, **kwds):
        kwds['drivername'] = self.DRIVER
        url = sqlalchemy.engine.URL.create(**kwds)
        logging.debug('Database URL: %s: %s', component_name, url)
        self.engine = create_async_engine(url, echo=False)
        self.session = sqlalchemy.orm.sessionmaker(self.engine, class_=AsyncSession)

    def array(self, item_type):
        'column type for a list of item_type, overridden by databases with arrays'
        return JSONArray(binary=isinstance(item_type, sqlalchemy.LargeBinary))

    async def create_tables(self):
        '''create the tables in an empty database, otherwise compare them to the
           models and apply the changes if --<name>-migrate was given'''
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(self._sync_schema)
        except _.error:
            raise
        except Exception as e:
            raise _.error('Database "%s": %s', self.component_name, e) from None

    def _sync_schema(self, conn):
        metadata = self.Base.metadata
        existing = set(sqlalchemy.inspect(conn).get_table_names())
        if not self.check_schema or not existing & set(metadata.tables):
            metadata.create_all(conn)
            return

        try:
            import alembic.migration
            import alembic.operations
        except ImportError:
            logging.warning('Database "%s": install alembic to check the schema', self.component_name)
            metadata.create_all(conn)
            return

        apply,manual = _plan_schema(conn, metadata)
        migrate = getattr(_.args, f'{self.component_name}_migrate', False)

        # apply nothing unless everything can be applied, SQLite can't roll back DDL
        if apply and migrate and not manual:
            operations = alembic.operations.Operations(alembic.migration.MigrationContext.configure(conn))
            for op in apply:
                logging.info('%s: %s', self.component_name, _render_sql(conn, op))
                operations.invoke(op)
            return

        if not apply and not manual:
            return

        lines = [f'Database "{self.component_name}" differs from the schema:']
        lines.extend(f'  {_render_sql(conn, op)}' for op in apply)
        if manual:
            lines.append('These changes may lose data and must be applied by hand:')
            lines.extend(f'  {_render_sql(conn, op)}' for op in manual)
            if apply:
                lines.append(f'Then run with --{self.component_name}-migrate to apply the rest')
        else:
            lines.append(f'Run with --{self.component_name}-migrate to apply them')
        raise _.error('%s', '\n'.join(lines))

    async def close(self):
        await self.engine.dispose()

    # CREATE
    async def insert(self, *args):
        try:
            async with self.session() as session:
                async with session.begin():
                    session.add_all(args)
        except sqlalchemy.exc.IntegrityError as e:
            raise _.error('%s', e) from None

    # READ
    async def find(self, cls, value=None, column=None):
        statement = sqlalchemy.select(cls)
        if value:
            column = getattr(cls, column or cls.__primary_key__)
            statement = statement.where(column == value)
        async with self.session() as session:
            results = await session.execute(statement)
            return results.unique().scalars().all()

    async def find_one(self, cls, value, column=None):
        statement = sqlalchemy.select(cls)
        column = getattr(cls, column or cls.__primary_key__)
        statement = statement.where(column == value)
        async with self.session() as session:
            results = await session.execute(statement)
            return results.unique().scalars().first()

    # UPDATE
    async def upsert(self, *args):
        async with self.session() as session:
            async with session.begin():
                for obj in args:
                    await session.merge(obj)

    # DELETE
    async def delete(self, obj, value=None):
        async with self.session() as session:
            async with session.begin():
                if value is None:
                    # delete an ORM instance
                    await session.delete(obj)
                else:
                    # otherwise assume obj is the SQLalchemy table class
                    column = getattr(obj, obj.__primary_key__)
                    statement = sqlalchemy.delete(obj).where(column == value)
                    results = await session.execute(statement)
                    return results.rowcount


def _plan_schema(conn, metadata):
    '''compare the database with the models using alembic autogenerate and split
       the changes into those that are safe to apply and those that may lose data'''
    import alembic.autogenerate
    import alembic.migration
    import alembic.operations.ops as ops

    # ignore tables in the database that these models don't define
    def include_name(name, type_, parent_names):
        return type_ != 'table' or name in metadata.tables

    context = alembic.migration.MigrationContext.configure(conn, opts=dict(
        include_name = include_name,
        compare_type = True,
        ))
    script = alembic.autogenerate.produce_migrations(context, metadata)

    apply,manual = [],[]
    for op in script.upgrade_ops.ops:
        for op in op.ops if isinstance(op, ops.ModifyTableOps) else [op]:
            if _pkey_nullable_only(metadata, op):
                continue
            if isinstance(op, (ops.DropTableOp, ops.DropColumnOp, ops.AlterColumnOp)):
                manual.append(op)
            elif isinstance(op, ops.AddColumnOp) and not (op.column.nullable or op.column.server_default):
                # existing rows would need a value
                manual.append(op)
            else:
                apply.append(op)
    return apply,manual


def _pkey_nullable_only(metadata, op):
    '''primary keys are never null, but models declare them Optional and
       SQLite only adds NOT NULL when asked, so ignore that difference'''
    import alembic.operations.ops as ops

    if not isinstance(op, ops.AlterColumnOp) or op.modify_nullable is None:
        return False
    if op.modify_type is not None or op.modify_server_default is not False or op.modify_name is not None:
        return False
    table = metadata.tables.get(op.table_name)
    return table is not None and op.column_name in table.c and table.c[op.column_name].primary_key


def _render_sql(conn, op):
    'the SQL for an alembic operation, for logging and error messages'
    import alembic.migration
    import alembic.operations

    output = io.StringIO()
    context = alembic.migration.MigrationContext.configure(
        dialect_name = conn.dialect.name,
        opts         = dict(as_sql=True, output_buffer=output),
        )
    alembic.operations.Operations(context).invoke(op)
    return ' '.join(output.getvalue().split()).rstrip(';')
