#
# (c) 2015-2023 Matthew Shaw
#
# Authors
# =======
# Matthew Shaw <mshaw.cx@gmail.com>
#

import importlib
import logging

import tornado.web

import _


class Component(type(_)):
    def __init__(self, module):
        super(Component, self).__init__(module.__name__)
        self.module = module
        self._components = {}

    def __getattr__(self, name):
        return getattr(self.module, name)

    def __getitem__(self, name):
        try:
            return getattr(self.module, name)
        except AttributeError:
            raise KeyError(name)


async def load(component_type):
    # skip components not specified in the config
    if component_type not in _.config:
        return

    module = importlib.import_module(f'_.components.{component_type}')
    setattr(_.components, 'databases', Component(module))

    # iterate over the components specified in the config
    for name in _.config[component_type]:
        # check if the component is aliased
        component = _.config[component_type][name]
        if component is None:
            component = name

        if component.startswith('+'):
            try:
                component,attr = component.rsplit('.', 1)
            except ValueError:
                attr = None
            import_path = component[1:]
        else:
            attr = None
            import_path = f'_.components.{component_type}.{component}'

        try:
            module = importlib.import_module(import_path)
        except ModuleNotFoundError:
            raise _.error('Unknown module: %s', import_path)

        cls = None
        if not attr:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if not isinstance(attr, type):
                    continue
                if not hasattr(attr, '_'):
                    continue
                cls = attr
        else:
            cls = getattr(module, attr)

        if not cls:
            logging.error('%s: %s module not found', component, component_type)
            continue

        try:
            kwds = dict(_.config[name])
        except KeyError:
            kwds = {}

        await cls._(name, **kwds)