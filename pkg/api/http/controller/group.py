from __future__ import annotations

import abc
import typing
import quart
from quart.typing import RouteCallable

from ....core import app


preregistered_groups: list[type[RouterGroup]] = []
"""RouterGroup 的预注册列表"""

def group_class(name: str, path: str) -> None:
    """注册一个 RouterGroup"""

    def decorator(cls: typing.Type[RouterGroup]) -> typing.Type[RouterGroup]:
        cls.name = name
        cls.path = path
        preregistered_groups.append(cls)
        return cls

    return decorator


class RouterGroup(abc.ABC):

    name: str

    path: str

    ap: app.Application

    quart_app: quart.Quart

    def __init__(self, ap: app.Application, quart_app: quart.Quart) -> None:
        self.ap = ap
        self.quart_app = quart_app

    @abc.abstractmethod
    async def initialize(self) -> None:
        pass

    def route(self, rule: str, **options: typing.Any) -> typing.Callable[[RouteCallable], RouteCallable]:  # decorator
        """注册一个路由"""
        def decorator(f: RouteCallable) -> RouteCallable:
            nonlocal rule
            rule = self.path + rule

            async def handler_error(*args, **kwargs):
                try:
                    return await f(*args, **kwargs)
                except Exception as e:  # 自动 500
                    return self.http_status(500, -2, str(e))
                
            new_f = handler_error
            new_f.__name__ = (self.name + rule).replace('/', '__')
            new_f.__doc__ = f.__doc__

            self.quart_app.route(rule, **options)(new_f)
            return f

        return decorator
    
    def _cors(self, response: quart.Response) -> quart.Response:
        # Quart-Cors 似乎很久没维护了，所以自己写
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Methods'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    def success(self, data: typing.Any = None) -> quart.Response:
        """返回一个 200 响应"""
        return self._cors(quart.jsonify({
            'code': 0,
            'msg': 'ok',
            'data': data,
        }))
    
    def fail(self, code: int, msg: str) -> quart.Response:
        """返回一个异常响应"""

        return self._cors(quart.jsonify({
            'code': code,
            'msg': msg,
        }))
    
    def http_status(self, status: int, code: int, msg: str) -> quart.Response:
        """返回一个指定状态码的响应"""
        return self.fail(code, msg), status
