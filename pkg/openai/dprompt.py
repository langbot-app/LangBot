# 多情景预设值管理
import json
import logging

__current__ = "default"
"""当前默认使用的情景预设的名称

由管理员使用`!default <名称>`指令切换
"""

__prompts_from_files__ = {}
"""从文件中读取的情景预设值"""

__scenario_from_files__ = {}


def read_prompt_from_file():
    """从文件读取预设值"""
    # 读取prompts/目录下的所有文件，以文件名为键，文件内容为值
    # 保存在__prompts_from_files__中
    global __prompts_from_files__
    import os

    __prompts_from_files__ = {}
    for file in os.listdir("prompts"):
        with open(os.path.join("prompts", file), encoding="utf-8") as f:
            __prompts_from_files__[file] = f.read()


def read_scenario_from_file():
    """从JSON文件读取情景预设"""
    global __scenario_from_files__
    import os

    __scenario_from_files__ = {}
    for file in os.listdir("scenario"):
        if file == "default-template.json":
            continue
        with open(os.path.join("scenario", file), encoding="utf-8") as f:
            __scenario_from_files__[file] = json.load(f)


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


def get_prompt(name: str = None) -> list:
    global __scenario_from_files__
    import config
    preset_mode = config.preset_mode

    """获取预设值"""
    if name is None:
        name = get_current()

    # JSON预设方式
    if preset_mode == 'full_scenario':
        import os

        for key in __scenario_from_files__:
            if key.lower().startswith(name.lower()):
                logging.debug('成功加载情景预设从JSON文件: {}'.format(key))
                return __scenario_from_files__[key]['prompt']
        
    # 默认预设方式
    elif preset_mode == 'default' or preset_mode == 'normal':

        default_dict = get_prompt_dict()

        for key in default_dict:
            if key.lower().startswith(name.lower()):
                return [
                    {
                        "role": "user",
                        "content": default_dict[key]
                    },
                    {
                        "role": "assistant",
                        "content": "好的。"
                    }
                ]

    raise KeyError("未找到默认情景预设: " + name)
