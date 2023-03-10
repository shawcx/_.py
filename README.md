
underscore.py
-------------

This is a framework for me that has morphed overtime. Some "features" are broken because I have not needed them for my own projects for quite some time. Eventually those bugs will be resolved.

For anyone confused by Python files like `_/databases/__databases__.py` I wrote a custom import loader that looks for `__dirname__.py` files before `__init__.py` because I find it easier to track the files that way. Very experimental, and probably fragile, but maybe I'll submit a PEP for it someday.
