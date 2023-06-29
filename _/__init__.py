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
