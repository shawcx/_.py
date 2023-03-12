#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import importlib
import os
import sys

root = os.path.dirname(__file__)
root = os.path.join(root, '..')
root = os.path.abspath(root)

# this is a custom importer that searches for __<dirname>__.py instead of __init__.py
class DirInit:
    def find_spec(self, fullname, path, target=None):
        # split that module name
        parts = fullname.split('.')
        # only load files from underscore
        if parts[0] != '_':
            return
        # check if there is a regularfile
        fullpath = os.path.join(root, *parts)
        if os.path.exists(fullpath + '.py'):
            loader = importlib.machinery.SourceFileLoader(fullname, fullpath+'.py')
            return importlib.util.spec_from_loader(fullname, loader)
        # ignore non-directories
        if not os.path.isdir(fullpath):
            return
        # check for the custom name
        fullpath = os.path.join(fullpath, f'__{parts[-1]}__.py')
        if not os.path.exists(fullpath):
            return
        # let Python know this class is going to load the module
        spec = importlib.machinery.ModuleSpec(fullname, self)
        spec.fullpath = fullpath
        return spec

    def create_module(self, spec):
        loader = importlib.machinery.SourceFileLoader(spec.name, spec.fullpath)
        spec   = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = spec.name
        module.__path__    = [os.path.abspath(os.path.join(*spec.name.split('.')))]
        return module

    def exec_module(self, module):
        module.__loader__.exec_module(module)

sys.meta_path.insert(0, DirInit())


from .utils import *

from . import version
from . import settings
from . import auth
from . import handlers
from . import components

from .application import Application

# placeholder for comonents
caches    = Container()
databases = Container()
logins    = Container()
records   = Container()
supports  = Container()
