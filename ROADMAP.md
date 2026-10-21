Roadmap
=======

Protobuf records
----------------


Smaller items
-------------

- The schema check can't see a table whose message was removed, and keeps
  no migration history.
- The nginx template serves `/static/` from `/var/www/static`, so an app's
  static files have to be copied there; it could point at the app's own
  `static` directory instead.
