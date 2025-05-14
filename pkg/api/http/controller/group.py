from __future__ import annotations

import abc
import typing
import enum
import quart
import traceback
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


class AuthType(enum.Enum):
    """认证类型"""

    NONE = 'none'
    USER_TOKEN = 'user-token'


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

    def route(
        self,
        rule: str,
        auth_type: AuthType = AuthType.USER_TOKEN,
        **options: typing.Any,
    ) -> typing.Callable[[RouteCallable], RouteCallable]:  # decorator
        """注册一个路由"""

        def decorator(f: RouteCallable) -> RouteCallable:
            nonlocal rule
            rule = self.path + rule

            async def handler_error(*args, **kwargs):
                if auth_type == AuthType.USER_TOKEN:
                    # 从Authorization头中获取token
                    token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                    if not token:
                        return self.http_status(401, -1, '未提供有效的用户令牌')

                    try:
                        user_email = await self.ap.user_service.verify_jwt_token(token)

                        # check if this account exists
                        user = await self.ap.user_service.get_user_by_email(user_email)
                        if not user:
                            return self.http_status(401, -1, '用户不存在')

                        # 检查f是否接受user_email参数
                        if 'user_email' in f.__code__.co_varnames:
                            kwargs['user_email'] = user_email
                    except Exception as e:
                        return self.http_status(401, -1, str(e))

                try:
                    return await f(*args, **kwargs)
                except Exception:  # 自动 500
                    traceback.print_exc()
                    # return self.http_status(500, -2, str(e))
                    return self.http_status(500, -2, 'internal server error')

            new_f = handler_error
            new_f.__name__ = (self.name + rule).replace('/', '__')
            new_f.__doc__ = f.__doc__

            self.quart_app.route(rule, **options)(new_f)
            return f

        return decorator

    def success(self, data: typing.Any = None) -> quart.Response:
        """返回一个 200 响应"""
        return quart.jsonify(
            {
                'code': 0,
                'msg': 'ok',
                'data': data,
            }
        )

    def fail(self, code: int, msg: str) -> quart.Response:
        """返回一个异常响应"""

        return quart.jsonify(
            {
                'code': code,
                'msg': msg,
            }
        )

    def http_status(self, status: int, code: int, msg: str) -> quart.Response:
        """返回一个指定状态码的响应"""
        return self.fail(code, msg), status
