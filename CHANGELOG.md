Changelog
=========

Unreleased
----------

### Upgrading

- **JSON output of protobuf records** (`_as_dict`, `_as_json` and the REST
  handlers) is now the proto3 JSON form throughout: 64-bit integers as
  strings, enums by name, timestamps in RFC 3339, durations such as
  `"90.5s"`, bytes as base64. Unset optional and message fields are left
  out, and relational child records no longer include their internal ids.
  A generated primary key such as `order_id` is still included.
- **The `json` module is no longer patched.** Importing `_` used to replace
  the default encoder for the whole process. Now `_.JSONEncoder` is used
  explicitly: by `_.handlers.Handler.write()`, which every `_` handler and
  custom record handler derives from, by `_.websockets.WebSocket.write_message()`,
  and by `_.json_encode()` for app code. A plain `json.dumps()` of records,
  bytes or datetimes now raises `TypeError`, as does writing them from a
  handler built directly on `tornado.web.RequestHandler`; use
  `_.json_encode()` or derive from `_.handlers.Handler`.
- **JSON output of dates and times** is ISO 8601 for every record type, for
  example `2024-05-01T12:00:00+00:00` rather than `2024-05-01 12:00:00+00:00`.
  `date` and `time` values, which used to fail, are encoded too.
- **Protobuf well-known types** get native columns, so existing tables
  differ and the startup check prints the SQL. In JSON mode a JSON
  `Timestamp` column becomes `TIMESTAMPTZ`, a type change you apply by
  hand. In relational mode the child tables these types used to get, such
  as `Event_at` with `seconds` and `nanos`, are replaced by a column that
  `--<database>-migrate` adds; copy any data across, then drop the old
  table. On records these fields now hold `datetime`, `timedelta` and plain
  values rather than proto3 JSON strings and objects.

### Added

- Protobuf well-known types are stored natively:
  - `Timestamp` becomes a `TIMESTAMPTZ` column held as a UTC `datetime`,
    accurate to the microsecond.
  - `Duration` becomes an `INTERVAL` held as a `timedelta`.
  - Wrappers such as `Int64Value` and `StringValue` become a nullable column
    of the wrapped type, so an unset value is `None` and differs from a
    stored `0` or `""`.
  - `Struct`, `Value` and `ListValue` become JSON columns holding plain
    dicts, values and lists.
  - Repeated well-known types are stored as JSON in proto3 JSON form.
- A protobuf record's own JSON output can be read back with `_from_dict`,
  generated primary key included, so a REST client can PUT back what it got
  from GET to update a record.
- Protobuf fields named after Python keywords, such as `from` or `class`,
  are supported: the record attribute is `from_`, while the column, the
  message and the JSON output keep `from`.

- Protobuf field options that were declared but ignored now work:
  - `(required)` makes the column NOT NULL and refuses to store a record
    with the field unset, including fields on relational child records.
  - `(no_column)` keeps the field in the message but doesn't store it.
  - `(ref) = "Table.column"` adds a foreign key.
- The skeleton has a logo and favicon, drawn as SVGs in
  `skeleton/src/images`; `make images` there re-renders them.

### Fixed

- In 0.9.0 the JSON output of relational protobuf records (`_as_dict`,
  `_as_json` and the REST handlers) left repeated child records out; the
  data was stored and read correctly.
- Updating a relational protobuf record (`upsert`, REST PUT) on Postgres
  lost the order of its repeated children.
- Relational child records are checked against their message when they're
  saved on their own, not only through their parent.
- dblogin pointed at an unknown database crashed with a `KeyError`
  traceback instead of naming the database.

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
- **Python 3.10 or later** is required, along with Tornado 6.3 or later.
  The redis extra needs redis 5.0.1 or later.
- **Packaging** moved to `pyproject.toml`; `setup.py` remains only for
  `make deb`.

### Added

- dblogin passwords are stored as salted scrypt hashes. Existing unsalted
  hashes still work and are upgraded on the next successful login.
- `make test` and a pytest suite. Set `UNDERSCORE_TEST_POSTGRES` to also
  run against Postgres.
- Optional extras: `postgres`, `sqlite`, `redis`, `protobuf`, `ldap`,
  `migrations`, `test` and `all`.
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
- Apps using dblogin or the dbcache session store without a `[records]`
  section crashed at startup, and `--add-user` failed without a `[dblogin]`
  section.
- Basic auth returns 400 for a malformed header, quotes the realm, and
  awaits coroutine handlers.
- Replaced calls deprecated in Tornado (`get/set_secure_cookie`) and redis
  (`close`).
- The SQLite `UUID` type and `RecordsInterface._as_json` raised
  `NameError`.
- Protobuf records are checked against their message before they're
  stored, so an unknown nested key is rejected (400 from the REST handlers)
  instead of being saved and breaking later reads.
- `_.handlers.Template` returns 404 for a page without a template instead
  of 500.
- The skeleton's WebSocket handler, admin page URLs, missing dashboard and
  messages pages, and JS rebuilds after editing `js/records/` are fixed.
