# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`underscorepy` (imported as `_`) is a small async application framework on top of Tornado and SQLAlchemy (async). Apps subclass `_.Application` (plain asyncio) or `_.WebApplication` (Tornado web server) and are configured almost entirely from INI files. `skeleton/` is a complete example app that exercises most components.

## Commands

- `make install`: `pip3 install --upgrade .`
- `make dist` / `make deb`: sdist or Debian package (deb needs `stdeb`)
- `make clean` / `make distclean`
- Run the example app: `make -C skeleton run` (compiles protobufs with `protoc`, builds JS/CSS via npm/browserify/sass, then runs `PYTHONPATH=.. python3 -m skeleton --debug`). Needs the databases it names in `skeleton.ini` (Postgres, and Redis for the redis cache) unless you trim the INI.
- Print the Protobuf options template: `python3 -m _.records.protobuf`

Tests: set up with `uv venv && uv pip install -e '.[test]'`, then `make test PYTHON=.venv/bin/python`. For one test, run `.venv/bin/python -m pytest tests/test_records.py::test_binary_round_trip`. `_` keeps its state in module globals and parses `sys.argv`, so each test writes an app, an INI and modules into `tmp_path` and runs them in a subprocess (`run_app` and `Server` in `tests/conftest.py`). There's no linter config.

## Architecture

**Global namespace as state.** The `_` package is the app's runtime registry. Startup sets module attributes such as `_.application`, `_.config` (ConfigParser), `_.args`, `_.argparser`, `_.name`, `_.ns`, `_.paths`, and `_.sessions`. Code everywhere reads these rather than passing objects around.

**Startup sequence** (`Application.main` → `_async_main`, `_/application.py`; `_/settings.py`):
1. `_.name` defaults to the lowercased app class name; `_.paths` roots at the app module's directory joined with `ns`.
2. INI files are merged in order: `<name>.ini`, `<name>.ini.local` (beside the app), `/etc/<ns>/<name>.ini`, `~/.<name>.ini`, then `--ini/-I`.
3. Components load in a fixed order: `databases`, `records`, `caches`, `logins`, `supports`. Records depend on databases; the sessions cache and dblogin reference database instances by name.
4. Args are parsed twice: once for `--ini`/`--debug`, then fully after components have added their own flags. Each component's `args()` hook runs afterwards.
5. `WebApplication` resolves `_.sessions` from the `sessions =` key in the app's section, calls the app's `initialize()` (which sets `self.patterns`), prepends the auto-generated record and login routes, applies the optional `prefix =` for reverse proxies, and listens.

**Component loader** (`_/components.py`). For each `[databases]`, `[records]`, `[caches]`, `[logins]` or `[supports]` section:
- Each key is an instance name. Its value is the implementation module, or the key itself when there's no value (`store = postgres`, or just `sqlite`).
- A `+` prefix imports a third-party module: `+pkg.mod` or `+pkg.mod.ClassName`.
- Without an explicit class, the loader picks the first class in the module that has a `_` classmethod. It calls `cls._(instance_name, **kwds)`, where kwds come from the INI section named after the instance.
- Each base class in `_/<type>/__init__.py` (`Database`, `Record`, `Cache`, `Login`, `Support`) defines `_()` and registers the instance in `_.<type>[name]`. Databases and records are also set directly as `_.<name>`.
- `Cache` and `Login` build a dynamic subclass whose INI options become `_`-prefixed class attributes (`_.prefix`).

**Records** (`_/records/`). These turn user modules into SQLAlchemy tables plus REST handlers at `/records/<component>(?:/(.*))?` via `HandlerInterface`. Content negotiation uses `?type=json` or binary.
- `data.py`: plain classes become dataclasses. Decorators and fields: `_.<name>.pkey()`, `uniq()`, `refs()`, `no_table`, `no_handler`, `handles(cls)` for a custom handler. Fields typed as classes become child tables with a cascading FK. Without a `pkey()`, a `<name>_id` autoincrement key is added.
- `protobuf.py`: walks the `*_pb2` modules and subpackages inside the configured package. Custom options come from `_/records/Protobuf.proto`; the app compiles its own copy (see `skeleton/Makefile`) and names it with `options =`. The `relational` and `handlers` INI flags control table style and handler creation. Generated `*_pb2.py` files are build outputs, not source.
  - Storage: singular scalars get native columns, and `uint64` uses `_.databases.UInt64`. Repeated scalars use `db.array()`: `ARRAY` on Postgres, a JSON list elsewhere. Maps are always JSON. Messages are JSON in proto3 JSON form, or child tables `<Parent>_<field>` when `relational`; repeated children are kept in order by a `_position` column.
  - Conversion goes through real protobuf messages (`_assign_pb` and `_fill_pb`). Child table classes live in `_proto_children`.

**Logins** register handlers at `/login/<component>` and add `/login` and `/logout`. On success they call `application.on_<component>_login_success`, or the generic `on_login_success`, which must return a session dict containing `session_id`; it's saved through `_.sessions`.

**Conventions**
- Hooks may be sync or async; the framework calls them through `await _.wait(...)`.
- Raise `_.error(fmt, *args)` for user-facing failures; it's logged without a traceback unless `--debug`. Use `_.HTTPError` in handlers.
- Importing `_` replaces `json`'s default encoder with `_.JSONEncoder` (handles `_as_dict`, bytes→base64, UUID, datetime). `protobuf.py` replaces it again when loaded.
- `_.handlers.Template` renders `<path>.html` from `templates/`. `_.handlers.Protected` and `_.auth` decorators check the `session_id` secure cookie.
- `_.auth.records` is a no-op by design, so generated record endpoints are open. Apps replace it, before components load, with whatever auth suits them. Don't change the default.
