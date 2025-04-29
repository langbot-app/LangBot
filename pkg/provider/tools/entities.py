from __future__ import annotations

import typing

import pydantic.v1 as pydantic


class LLMFunction(pydantic.BaseModel):
    """函数"""

    name: str
    """函数名"""

    human_desc: str

    description: str
    """给LLM识别的函数描述"""

    parameters: dict

    func: typing.Callable
    """供调用的python异步方法
    
    此异步方法第一个参数接收当前请求的query对象，可以从其中取出session等信息。
    query参数不在parameters中，但在调用时会自动传入。
    但在当前版本中，插件提供的内容函数都是同步的，且均为请求无关的，故在此版本的实现（以及考虑了向后兼容性的版本）中，
    对插件的内容函数进行封装并存到这里来。
    """

    class Config:
        arbitrary_types_allowed = True
