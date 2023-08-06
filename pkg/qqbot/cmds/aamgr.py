import importlib
import inspect
import logging
import copy
import pkgutil
import traceback
import types
import json


__command_list__ = {}

import tips as tips_custom

"""命令树

结构：
{
    'cmd1': {
        'description': 'cmd1 description',
        'usage': 'cmd1 usage',
        'aliases': ['cmd1 alias1', 'cmd1 alias2'],
        'privilege': 0,
        'parent': None,
        'cls': <class 'pkg.qqbot.cmds.cmd1.CommandCmd1'>,
        'sub': [
            'cmd1-1'
        ]
    },
    'cmd1.cmd1-1: {
        'description': 'cmd1-1 description',
        'usage': 'cmd1-1 usage',
        'aliases': ['cmd1-1 alias1', 'cmd1-1 alias2'],
        'privilege': 0,
        'parent': 'cmd1',
        'cls': <class 'pkg.qqbot.cmds.cmd1.CommandCmd1_1'>,
        'sub': []
    },
    'cmd2': {
        'description': 'cmd2 description',
        'usage': 'cmd2 usage',
        'aliases': ['cmd2 alias1', 'cmd2 alias2'],
        'privilege': 0,
        'parent': None,
        'cls': <class 'pkg.qqbot.cmds.cmd2.CommandCmd2'>,
        'sub': [
            'cmd2-1'
        ]
    },
    'cmd2.cmd2-1': {
        'description': 'cmd2-1 description',
        'usage': 'cmd2-1 usage',
        'aliases': ['cmd2-1 alias1', 'cmd2-1 alias2'],
        'privilege': 0,
        'parent': 'cmd2',
        'cls': <class 'pkg.qqbot.cmds.cmd2.CommandCmd2_1'>,
        'sub': [
            'cmd2-1-1'
        ]
    },
    'cmd2.cmd2-1.cmd2-1-1': {
        'description': 'cmd2-1-1 description',
        'usage': 'cmd2-1-1 usage',
        'aliases': ['cmd2-1-1 alias1', 'cmd2-1-1 alias2'],
        'privilege': 0,
        'parent': 'cmd2.cmd2-1',
        'cls': <class 'pkg.qqbot.cmds.cmd2.CommandCmd2_1_1'>,
        'sub': []
    },
}
"""

__tree_index__: dict[str, list] = {}
"""命令树索引

结构：
{
    'pkg.qqbot.cmds.cmd1.CommandCmd1': 'cmd1',  # 顶级指令
    'pkg.qqbot.cmds.cmd1.CommandCmd1_1': 'cmd1.cmd1-1',  # 类名: 节点路径
    'pkg.qqbot.cmds.cmd2.CommandCmd2': 'cmd2',
    'pkg.qqbot.cmds.cmd2.CommandCmd2_1': 'cmd2.cmd2-1',
    'pkg.qqbot.cmds.cmd2.CommandCmd2_1_1': 'cmd2.cmd2-1.cmd2-1-1',
}
"""


class Context:
    """命令执行上下文"""
    command: str
    """顶级指令文本"""

    crt_command: str
    """当前子指令文本"""

    params: list
    """完整参数列表"""

    crt_params: list
    """当前子指令参数列表"""

    session_name: str
    """会话名"""

    text_message: str
    """指令完整文本"""

    launcher_type: str
    """指令发起者类型"""

    launcher_id: int
    """指令发起者ID"""

    sender_id: int
    """指令发送者ID"""

    is_admin: bool
    """[过时]指令发送者是否为管理员"""

    privilege: int
    """指令发送者权限等级"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class AbstractCommandNode:
    """指令抽象类"""

    parent: type
    """父指令类"""

    name: str
    """指令名"""

    description: str
    """指令描述"""

    usage: str
    """指令用法"""

    aliases: list[str]
    """指令别名"""

    privilege: int
    """指令权限等级, 权限大于等于此值的用户才能执行指令"""

    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        """指令处理函数
        
        :param ctx: 指令执行上下文

        :return: (是否执行, 回复列表(若执行))

        若未执行，将自动以下一个参数查找并执行子指令
        """
        raise NotImplementedError
    
    @classmethod
    def help(cls) -> str:
        """获取指令帮助信息"""
        return '指令: {}\n描述: {}\n用法: \n{}\n别名: {}\n权限: {}'.format(
            cls.name,
            cls.description,
            cls.usage,
            ', '.join(cls.aliases),
            cls.privilege
        )

    @staticmethod
    def register(
        parent: type = None,
        name: str = None,
        description: str = None,
        usage: str = None,
        aliases: list[str] = None,
        privilege: int = 0
    ):
        """注册指令
        
        :param cls: 指令类
        :param name: 指令名
        :param parent: 父指令类
        """
        global __command_list__, __tree_index__
        
        def wrapper(cls):
            cls.name = name
            cls.parent = parent
            cls.description = description
            cls.usage = usage
            cls.aliases = aliases
            cls.privilege = privilege

            logging.debug("cls: {}, name: {}, parent: {}".format(cls, name, parent))

            if parent is None:
                # 顶级指令注册
                __command_list__[name] = {
                    'description': cls.description,
                    'usage': cls.usage,
                    'aliases': cls.aliases,
                    'privilege': cls.privilege,
                    'parent': None,
                    'cls': cls,
                    'sub': []
                }
                # 更新索引
                __tree_index__[cls.__module__ + '.' + cls.__name__] = name
            else:
                # 获取父节点名称
                path = __tree_index__[parent.__module__ + '.' + parent.__name__]
                
                parent_node = __command_list__[path]
                # 链接父子指令
                __command_list__[path]['sub'].append(name)
                # 注册子指令
                __command_list__[path + '.' + name] = {
                    'description': cls.description,
                    'usage': cls.usage,
                    'aliases': cls.aliases,
                    'privilege': cls.privilege,
                    'parent': path,
                    'cls': cls,
                    'sub': []
                }
                # 更新索引
                __tree_index__[cls.__module__ + '.' + cls.__name__] = path + '.' + name

            return cls
        
        return wrapper


class CommandPrivilegeError(Exception):
    """指令权限不足或不存在异常"""
    pass


# 传入Context对象，广搜命令树，返回执行结果
# 若命令被处理，返回reply列表
# 若命令未被处理，继续执行下一级指令
# 若命令不存在，报异常
def execute(context: Context) -> list:
    """执行指令
    
    :param ctx: 指令执行上下文

    :return: 回复列表
    """
    global __command_list__

    # 拷贝ctx
    ctx: Context = copy.deepcopy(context)

    # 从树取出顶级指令
    node = __command_list__
    
    path = ctx.command

    while True:
        try:
            node = __command_list__[path]
            logging.debug('执行指令: {}'.format(path))

            # 检查权限
            if ctx.privilege < node['privilege']:
                raise CommandPrivilegeError(tips_custom.command_admin_message+"{}".format(path))
            
            # 执行
            execed, reply = node['cls'].process(ctx)
            if execed:
                return reply
            else:
                # 删除crt_params第一个参数
                ctx.crt_command = ctx.crt_params.pop(0)
                # 下一个path
                path = path + '.' + ctx.crt_command
        except KeyError:
            traceback.print_exc()
            raise CommandPrivilegeError(tips_custom.command_err_message+"{}".format(path))


def register_all():
    """启动时调用此函数注册所有指令
    
    递归处理pkg.qqbot.cmds包下及其子包下所有模块的所有继承于AbstractCommand的类
    """
    # 模块：遍历其中的继承于AbstractCommand的类，进行注册
    # 包：递归处理包下的模块
    # 排除__开头的属性
    global __command_list__, __tree_index__

    import pkg.qqbot.cmds

    def walk(module, prefix, path_prefix):
        # 排除不处于pkg.qqbot.cmds中的包
        if not module.__name__.startswith('pkg.qqbot.cmds'):
            return
        
        logging.debug('walk: {}, path: {}'.format(module.__name__, module.__path__))
        for item in pkgutil.iter_modules(module.__path__):
            if item.name.startswith('__'):
                continue

            if item.ispkg:
                walk(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.', path_prefix + item.name + '/')
            else:
                m = __import__(module.__name__ + '.' + item.name, fromlist=[''])
                # for name, cls in inspect.getmembers(m, inspect.isclass):
                #     # 检查是否为指令类
                #     if cls.__module__ == m.__name__ and issubclass(cls, AbstractCommandNode) and cls != AbstractCommandNode:
                #         cls.register(cls, cls.name, cls.parent)

    walk(pkg.qqbot.cmds, '', '')
    logging.debug(__command_list__)


def apply_privileges():
    """读取cmdpriv.json并应用指令权限"""
    # 读取内容
    json_str = ""
    with open('cmdpriv.json', 'r', encoding="utf-8") as f:
        json_str = f.read()

    data = json.loads(json_str)
    for path, priv in data.items():
        if path == 'comment':
            continue
        
        if path not in __command_list__:
            continue
        
        if __command_list__[path]['privilege'] != priv:
            logging.debug('应用权限: {} -> {}(default: {})'.format(path, priv, __command_list__[path]['privilege']))

        __command_list__[path]['privilege'] = priv
