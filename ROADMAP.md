Roadmap
=======

Protobuf records
----------------

- **Unused options in `Protobuf.proto`.** `refs`, `paired` and `subtype`
  are declared but have no effect; their intended behaviour still needs
  defining.
- **Field names that are Python keywords** such as `from` or `class` raise
  an error, because record fields are Python attributes. Store them as
  `from_` while keeping the column and message name `from`.
- **Well-known types.** `google.protobuf.Timestamp` is stored as a JSON
  `{seconds, nanos}` object; map it to `TIMESTAMPTZ`, and consider
  `Duration` and the wrapper types.
- **Consistent JSON API output.** Top-level 64-bit integers are JSON
  numbers and enums are numbers, but nested ones use proto3 JSON form
  (strings and names). Pick one form for the whole record.

Smaller items
-------------

- Only top-level records are checked against their message before saving;
  updating a relational child row on its own skips the check.
- The schema check can't see a table whose message was removed, and keeps
  no migration history.
- Importing `_` replaces the `json` module's default encoder for the whole
  process.
- dblogin catches `AttributeError` where a missing database raises
  `KeyError`.
- Skeleton: `static/images/skeleton.png` and `favicon.ico` aren't in the
  repo; the UI hasn't been checked in a browser; `--nginx` and `--systemd`
  are untested.
