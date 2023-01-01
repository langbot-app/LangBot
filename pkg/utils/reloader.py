import logging

import pkg
import importlib
import pkgutil


def walk(module, prefix=''):
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            walk(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.')
        else:
            logging.info('reload module: {}'.format(prefix + item.name))
            importlib.reload(__import__(module.__name__ + '.' + item.name, fromlist=['']))


def reload_all():
    walk(pkg)
    importlib.reload(__import__('config'))
