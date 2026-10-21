Changelog
=========

0.9.0
-----

### Upgrading from 0.8

- **Schema check at startup.** Each start compares the tables with the
  models and refuses to run if they differ, printing the SQL. Run once with
  `--<database>-migrate` to apply changes that can't lose data. Drops and
  type changes are printed for you to run by hand. Install the
  `migrations` extra (`alembic`) for this; without it tables are only
  created, as before. Set `check_schema = false` in a database's section to
  skip the check.
- **Relational protobuf tables** need a `_position` column on repeated
  child tables, and `ON DELETE CASCADE` on child foreign keys. Both are
  applied by `--<database>-migrate`.
- **Protobuf subpackages** now use their own tables and routes:
  `pkg.sub.Msg` is table `sub_Msg`, served at `/<component>/sub/Msg`.
  Rename existing tables (`ALTER TABLE "Msg" RENAME TO "sub_Msg"`) to keep
  their data.
- **Custom record handlers** (`@_.<component>.handles(X)`) are served at
  `X`'s route instead of the handler class name, e.g. `/proto/NoTable`
  rather than `/proto/CustomNoTable`.
- **Nested protobuf values** in JSON mode are held in proto3 JSON form:
  64-bit integers as strings, enums by name, bytes as base64.
- **Binary data records** are JSON encoded instead of pickled.
- **Python 3.10 or later** is required.

### Added

- `make test` and a pytest suite. Set `UNDERSCORE_TEST_POSTGRES` to also
  run against Postgres.
- Optional extras: `postgres`, `sqlite`, `redis`, `protobuf`, `ldap`,
  `migrations` and `test`.
- Listing records with `?type=binary` returns varint length-delimited
  records.

### Fixed

- Request bodies for binary records were unpickled, allowing remote code
  execution. JSON POSTs failed, string primary keys failed in GET and
  DELETE, and bad bodies dropped the connection instead of returning 400.
- Protobuf records failed to load on protobuf 7.
- Protobuf relational mode failed to insert anything with a message field,
  deletes by id violated foreign keys, and repeated children lost their
  order.
- Protobuf `map` fields, repeated non-string scalars, `uint64` values of
  2^63 and up, and `repeated string` on SQLite failed.
- Protobuf binary serialization dropped a declared `(pkey)` field.
- The protobuf loader walked any module imported into the package,
  recursing forever on `os`.
- SQLite foreign keys were never enabled.
- Two databases of the same type shared one set of tables.
- Same-named messages in different components shared custom handlers;
  records without a table got a CRUD handler that always failed.
- Records with handlers crashed a plain `_.Application`.
- `sqlalchemy[asyncio]` is required, so `greenlet` is installed.
- The SQLite `UUID` type and `RecordsInterface._as_json` raised
  `NameError`.
