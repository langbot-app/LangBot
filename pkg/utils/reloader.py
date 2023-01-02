import logging
import os
import threading

import colorlog

import pkg
import importlib
import pkgutil
import pkg.utils.context
from main import log_colors_config


def walk(module, prefix=''):
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            walk(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.')
        else:
            logging.info('reload module: {}'.format(prefix + item.name))
            importlib.reload(__import__(module.__name__ + '.' + item.name, fromlist=['']))


def reload_all():
    # 解除bot的事件注册
    import pkg
    pkg.utils.context.get_qqbot_manager().unsubscribe_all()
    # 执行关闭流程
    logging.info("执行程序关闭流程")
    import main
    main.stop()

    context = pkg.utils.context.context
    walk(pkg)
    importlib.reload(__import__('config'))
    importlib.reload(__import__('main'))
    pkg.utils.context.context = context

    # 执行启动流程
    logging.info("执行程序启动流程")
    main.main()

    logging.info('程序启动完成')
