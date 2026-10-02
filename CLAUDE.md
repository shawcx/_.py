# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`underscorepy` (imported as `_`) is an async application framework on top of Tornado and SQLAlchemy (async). Apps subclass `_.Application` (plain asyncio) or `_.WebApplication` (Tornado web server), implement `initialize()`, and call `MyApp.main()`. Most behaviour is driven by an INI file rather than code.

## Commands

- Packaging metadata is in `pyproject.toml` (setuptools backend). `setup.py` is only a shim so `make deb` works with stdeb.
- `make install` (`pip3 install --upgrade .`), `make develop` (editable install with all extras)
- `make dist` (`python3 -m build`, sdist and wheel), `make deb` (needs `stdeb`), `make clean` / `make distclean`
- Optional backends are extras: `postgres`, `sqlite`, `redis`, `protobuf`, `ldap`, `all`.
- The version lives in `_/version.py`. `pyproject.toml` reads it through `attr`.
- There's no test suite or linter. The example app in `skeleton/` serves as the integration test: it loads every component type, round-trips protobuf and data records, and serves login, session and record endpoints. Run it with the project venv (`.venv`, created with `pip install -e '.[postgres,sqlite,redis,protobuf]'`): `cd skeleton && PYTHONPATH=.. ../.venv/bin/python -m skeleton --debug`. It needs Postgres (database `skeleton`, connecting as the OS user on localhost) and Redis on localhost:6379, e.g. the `skeleton-pg` and `skeleton-redis` Docker containers. Add a login with `--dblogin-add-user <user> <password>`.
- The full build (it also needs `protoc` and npm for the frontend):
  - `cd skeleton && make run`: builds protobufs and JS/CSS, then runs `PYTHONPATH=.. python3 -m skeleton --debug`
  - `PYTHONPATH=.. python3 -m _.records.protobuf` prints the `Protobuf.proto` options file that app protos import.
- `_/test.py` swaps `_.Application` for a `TestApplication` whose listen step only logs, so you can load an app without binding a port.

## Architecture

**Global namespace as state.** At runtime the `_` module itself holds the app's state: `_.application`, `_.config` (ConfigParser), `_.args`, `_.argparser`, `_.name`, `_.ns`, `_.paths`, `_.sessions`. Component instances are also attached there (e.g. `_.databases.store`, and each record component as `_.<component_name>`). That's why a record component name can't clash with an existing `_` attribute.

**Startup sequence** (`application.py` → `settings.load`):
1. App name comes from the class name (lowercased) or the caller's filename. INI files are read from `<root>/<ns>/<name>.ini`, `<name>.ini.local`, `/etc/<ns>/<name>.ini`, `~/.<name>.ini`, and `--ini`.
2. `components.load()` runs for each section in this order: `databases`, `records`, `caches`, `logins`, `supports`.
3. Args are parsed, then each record/support/login component's `args()` hook runs; a hook can call `_.application.stop()` to exit early (e.g. `--<proto>` prints the options proto).
4. `WebApplication._async_init`: resolves `_.sessions` from the `sessions =` cache name, calls `initialize()`, then assembles routes in this order: record handlers (`/<component>/<Record>(/id)`), then login handlers (`/login/<component>`) plus `/login` and `/logout`, then `self.patterns`. An optional `prefix =` setting is prepended to every route.
5. The app blocks on `_stop_event` (set by SIGINT/SIGTERM or `stop()`), then calls `on_stop()` and closes the caches and databases.

**Component loading** (`components.py`): each `[databases]`/`[caches]`/etc. entry is `name = module` or a bare `name` (the module defaults to the name). A `+pkg.mod[.Class]` value imports a third-party module. The loader takes the first class in the module that has a `_` classmethod and calls `await cls._(component_name, **ini_section_named_component_name)`. Each package's `__init__.py` defines the base class (`Database`, `Record`, `Cache`, `Login`, `Support`) and its `_` factory. Caches and logins build a dynamic subclass whose INI keys become `_`-prefixed class attributes (`_.prefix`).

**Records** (`_/records/`): these turn a Python module into SQLAlchemy tables, REST handlers, and JSON/binary (de)serialisers.
- `data.py`: plain classes or dataclasses. `_.<name>.no_table`, `.no_handler`, `.pkey`, `.uniq`, `.refs` and `.handles` are decorators used inside the data module.
- `protobuf.py`: compiled `*_pb2` messages. Field options come from `Protobuf.proto`. `relational =` and `handlers =` INI flags control table style and handler creation.
- Records share `RecordsInterface` (`_as_dict`, `_as_json`, `_from_dict`, `_from_json`, plus `_as_binary`/`_from_binary` and protobuf `_as_pb`/`_from_pb`). `HandlerInterface` is the generic CRUD handler; `?type=` picks JSON or binary.
- Nested messages and dataclasses become child tables keyed back to the parent.

**Auth** (`auth.py`, `handlers.py`): `_.handlers.Protected` loads the session from the `session_id` secure cookie through `_.sessions`. `_.auth.protected` and `_.auth.records` are module-level decorators that apps can replace *before* `settings.load` runs, which changes the access policy for every component handler (see `skeleton/skeleton/skeleton.py`). Login components call the app's `on_<component>_login_success`, falling back to `on_login_success`, which must return a session dict.

## Conventions

- Raise `_.error(fmt, *args)` for user-facing failures. It's caught and logged in `main`/`settings.load`.
- Use `await _.wait(x)` to call hooks that may be either sync or async.
- `_/utils.py` replaces `json._default_encoder` globally, so `json.dumps` handles bytes (base64), UUIDs, datetimes, and anything with `_as_dict`.
- `tmp/` is untracked scratch space.
