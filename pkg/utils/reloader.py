import logging
import threading

import importlib
import pkgutil
import pkg.utils.context


def walk(module, prefix=''):
    """遍历并重载所有模块"""
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            walk(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.')
        else:
            logging.info('reload module: {}'.format(prefix + item.name))
            importlib.reload(__import__(module.__name__ + '.' + item.name, fromlist=['']))


def reload_all(notify=True):
    # 解除bot的事件注册
    import pkg
    pkg.utils.context.get_qqbot_manager().unsubscribe_all()
    # 执行关闭流程
    logging.info("执行程序关闭流程")
    import main
    main.stop()

    # 重载所有模块
    pkg.utils.context.context['exceeded_keys'] = pkg.utils.context.get_openai_manager().key_mgr.exceeded
    context = pkg.utils.context.context
    walk(pkg)
    importlib.reload(__import__('config'))
    importlib.reload(__import__('main'))
    pkg.utils.context.context = context

    # 执行启动流程
    logging.info("执行程序启动流程")
    threading.Thread(target=main.main, args=(False,), daemon=False).start()

    logging.info('程序启动完成')
    if notify:
        pkg.utils.context.get_qqbot_manager().notify_admin("重载完成")
