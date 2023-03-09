# 多情景预设值管理

__current__ = "default"
"""当前默认使用的情景预设的名称

由管理员使用`!default <名称>`指令切换
"""

__prompts_from_files__ = {}
"""从文件中读取的情景预设值"""


def read_prompt_from_file() -> str:
    """从文件读取预设值"""
    # 读取prompts/目录下的所有文件，以文件名为键，文件内容为值
    # 保存在__prompts_from_files__中
    global __prompts_from_files__
    import os

    __prompts_from_files__ = {}
    for file in os.listdir("prompts"):
        with open(os.path.join("prompts", file), encoding="utf-8") as f:
            __prompts_from_files__[file] = f.read()


def get_prompt_dict() -> dict:
    """获取预设值字典"""
    import config
    default_prompt = config.default_prompt
    if type(default_prompt) == str:
        default_prompt = {"default": default_prompt}
    elif type(default_prompt) == dict:
        pass
    else:
        raise TypeError("default_prompt must be str or dict")

    # 将文件中的预设值合并到default_prompt中
    for key in __prompts_from_files__:
        default_prompt[key] = __prompts_from_files__[key]

    return default_prompt


def set_current(name):
    global __current__
    for key in get_prompt_dict():
        if key.lower().startswith(name.lower()):
            __current__ = key
            return
    raise KeyError("未找到情景预设: " + name)


def get_current():
    global __current__
    return __current__


def set_to_default():
    global __current__
    default_dict = get_prompt_dict()

    if "default" in default_dict:
        __current__ = "default"
    else:
        __current__ = list(default_dict.keys())[0]


def get_prompt(name: str = None) -> str:
    """获取预设值"""
    if name is None:
        name = get_current()

    default_dict = get_prompt_dict()

    for key in default_dict:
        if key.lower().startswith(name.lower()):
            return default_dict[key]

    raise KeyError("未找到情景预设: " + name)
