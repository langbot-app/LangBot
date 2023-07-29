# 封装了function calling的一些支持函数
import logging


from pkg.plugin import host


class ContentFunctionNotFoundError(Exception):
    pass


def get_func_schema_list() -> list:
    """从plugin包中的函数结构中获取并处理成受GPT支持的格式"""
    if not host.__enable_content_functions__:
        return []

    schemas = []

    for func in host.__callable_functions__:
        if func['enabled']:
            fun_cp = func.copy()

            del fun_cp['enabled']

            schemas.append(fun_cp)

    return schemas

def get_func(name: str) -> callable:
    if name not in host.__function_inst_map__:
        raise ContentFunctionNotFoundError("没有找到内容函数: {}".format(name))

    return host.__function_inst_map__[name]

def get_func_schema(name: str) -> dict:
    for func in host.__callable_functions__:
        if func['name'] == name:
            return func
    raise ContentFunctionNotFoundError("没有找到内容函数: {}".format(name))

def execute_function(name: str, kwargs: dict) -> any:
    """执行函数调用"""

    logging.debug("executing function: name='{}', kwargs={}".format(name, kwargs))

    func = get_func(name)
    return func(**kwargs)
