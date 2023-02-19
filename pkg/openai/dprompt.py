# 多情景预设值管理

__current__ = "default"

def get_prompt_dict() -> dict:
    """获取预设值字典"""
    import config
    default_prompt = config.default_prompt
    if type(default_prompt) == str:
        return {"default": default_prompt}
    elif type(default_prompt) == dict:
        return default_prompt
    else:
        raise TypeError("default_prompt must be str or dict")


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
