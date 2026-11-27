from __future__ import annotations

import typing

import pydantic


class LLMTool(pydantic.BaseModel):
    """LLM Tool"""

    name: str
    """Tool name"""

    human_desc: str

    description: str
    """Description for LLM to recognize"""

    parameters: dict

    func: typing.Callable = pydantic.Field(exclude=True)
    """Python asynchronous method for calling
    
    The first parameter of this asynchronous method receives the current request's query object, from which session information can be obtained.
    The query parameter is not in parameters, but is automatically passed in when calling.
    However, in the current version, the content functions provided by plugins are all synchronous and request-independent, so in the implementation of this version (and considering backward compatibility),
    the content functions of plugins are encapsulated and stored here.
    """

    class Config:
        arbitrary_types_allowed = True
