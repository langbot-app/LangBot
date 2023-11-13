import json
import logging

import openai
from openai.types.chat import chat_completion_message

from .model import RequestBase
from .. import funcmgr


class ChatCompletionRequest(RequestBase):
    """调用ChatCompletion接口的请求类。
    
    此类保证每一次返回的角色为assistant的信息的finish_reason一定为stop。
    若有函数调用响应，本类的返回瀑布是：函数调用请求->函数调用结果->...->assistant的信息->stop。
    """

    model: str
    messages: list[dict[str, str]]
    kwargs: dict

    stopped: bool = False

    pending_func_call: chat_completion_message.FunctionCall = None

    pending_msg: str

    def flush_pending_msg(self):
        self.append_message(
            role="assistant",
            content=self.pending_msg
        )
        self.pending_msg = ""

    def append_message(self, role: str, content: str, name: str=None, function_call: dict=None):
        msg = {
            "role": role,
            "content": content
        }

        if name is not None:
            msg['name'] = name

        if function_call is not None:
            msg['function_call'] = function_call

        self.messages.append(msg)

    def __init__(
        self,
        client: openai.Client,
        model: str,
        messages: list[dict[str, str]],
        **kwargs
    ):
        self.client = client
        self.model = model
        self.messages = messages.copy()

        self.kwargs = kwargs

        self.req_func = self.client.chat.completions.create

        self.pending_func_call = None

        self.stopped = False

        self.pending_msg = ""

    def __iter__(self):
        return self

    def __next__(self) -> dict:
        if self.stopped:
            raise StopIteration()

        if self.pending_func_call is None:  # 没有待处理的函数调用请求

            args = {
                "model": self.model,
                "messages": self.messages,
            }

            funcs = funcmgr.get_func_schema_list()

            if len(funcs) > 0:
                args['functions'] = funcs

            # 拼接kwargs
            args = {**args, **self.kwargs}
            
            from openai.types.chat import chat_completion

            resp: chat_completion.ChatCompletion = self._req(**args)

            choice0 = resp.choices[0]

            # 如果不是函数调用，且finish_reason为stop，则停止迭代
            if choice0.finish_reason == 'stop':  #  and choice0["finish_reason"] == "stop"
                self.stopped = True
            
            if hasattr(choice0.message, 'function_call') and choice0.message.function_call is not None:
                self.pending_func_call = choice0.message.function_call

                self.append_message(
                    role="assistant",
                    content=choice0.message.content,
                    function_call=choice0.message.function_call
                )

                return {
                    "id": resp.id,
                    "choices": [
                        {
                            "index": choice0.index,
                            "message": {
                                "role": "assistant",
                                "type": "function_call",
                                "content": choice0.message.content,
                                "function_call": {
                                    "name": choice0.message.function_call.name,
                                    "arguments": choice0.message.function_call.arguments
                                }
                            },
                            "finish_reason": "function_call"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens": resp.usage.total_tokens
                    }
                }
            else:

                # self.pending_msg += choice0['message']['content']
                # 普通回复一定处于最后方，故不用再追加进内部messages

                return {
                    "id": resp.id,
                    "choices": [
                        {
                            "index": choice0.index,
                            "message": {
                                "role": "assistant",
                                "type": "text",
                                "content": choice0.message.content
                            },
                            "finish_reason": choice0.finish_reason
                        }
                    ],
                    "usage": {
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens": resp.usage.total_tokens
                    }
                }
        else:  # 处理函数调用请求

            cp_pending_func_call = self.pending_func_call.copy()
            
            self.pending_func_call = None

            func_name = cp_pending_func_call.name
            arguments = {}

            try:

                try:
                    arguments = json.loads(cp_pending_func_call.arguments)
                # 若不是json格式的异常处理
                except json.decoder.JSONDecodeError:
                    # 获取函数的参数列表
                    func_schema = funcmgr.get_func_schema(func_name)

                    arguments = {
                        func_schema['parameters']['required'][0]: cp_pending_func_call.arguments
                    }
                
                logging.info("执行函数调用: name={}, arguments={}".format(func_name, arguments))

                # 执行函数调用
                ret = ""
                try:
                    ret = funcmgr.execute_function(func_name, arguments)

                    logging.info("函数执行完成。")
                except Exception as e:
                    ret = "error: execute function failed: {}".format(str(e))
                    logging.error("函数执行失败: {}".format(str(e)))

                self.append_message(
                    role="function",
                    content=json.dumps(ret, ensure_ascii=False),
                    name=func_name
                )

                return {
                    "id": -1,
                    "choices": [
                        {
                            "index": -1,
                            "message": {
                                "role": "function",
                                "type": "function_return",
                                "function_name": func_name,
                                "content": json.dumps(ret, ensure_ascii=False)
                            },
                            "finish_reason": "function_return"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }

            except funcmgr.ContentFunctionNotFoundError:
                raise Exception("没有找到函数: {}".format(func_name))
