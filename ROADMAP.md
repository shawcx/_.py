Roadmap
=======

Protobuf records
----------------

- **Unused options in `Protobuf.proto`.** `refs`, `paired` and `subtype`
  are declared but have no effect; their intended behaviour still needs
  defining.

Smaller items
-------------

- The schema check can't see a table whose message was removed, and keeps
  no migration history.
- Skeleton: the UI hasn't been checked in a browser; `--nginx` and
  `--systemd` are untested.
