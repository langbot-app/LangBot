import logging

import pkg
import importlib
import pkgutil
import pkg.utils.context


def walk(module, prefix=''):
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            walk(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.')
        else:
            logging.info('reload module: {}'.format(prefix + item.name))
            importlib.reload(__import__(module.__name__ + '.' + item.name, fromlist=['']))


def reload_all():
    context = pkg.utils.context.context
    walk(pkg)
    importlib.reload(__import__('config'))
    pkg.utils.context.context = context
