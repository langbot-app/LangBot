from __future__ import annotations

import abc
import typing
import enum
import quart
import traceback
from quart.typing import RouteCallable

from ....core import app

# Maximum file upload size limit (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


preregistered_groups: list[type[RouterGroup]] = []
"""Pre-registered list of RouterGroup"""


def group_class(name: str, path: str) -> typing.Callable[[typing.Type[RouterGroup]], typing.Type[RouterGroup]]:
    """注册一个 RouterGroup"""

    def decorator(cls: typing.Type[RouterGroup]) -> typing.Type[RouterGroup]:
        cls.name = name
        cls.path = path
        preregistered_groups.append(cls)
        return cls

    return decorator


class AuthType(enum.Enum):
    """Authentication type"""

    NONE = 'none'
    USER_TOKEN = 'user-token'
    API_KEY = 'api-key'
    USER_TOKEN_OR_API_KEY = 'user-token-or-api-key'


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
        """Register a route"""

        def decorator(f: RouteCallable) -> RouteCallable:
            nonlocal rule
            rule = self.path + rule

            async def handler_error(*args, **kwargs):
                if auth_type == AuthType.USER_TOKEN:
                    # get token from Authorization header
                    token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                    if not token:
                        return self.http_status(401, -1, 'No valid user token provided')

                    try:
                        user_email = await self.ap.user_service.verify_jwt_token(token)

                        # check if this account exists
                        user = await self.ap.user_service.get_user_by_email(user_email)
                        if not user:
                            return self.http_status(401, -1, 'User not found')

                        # check if f accepts user_email parameter
                        if 'user_email' in f.__code__.co_varnames:
                            kwargs['user_email'] = user_email
                    except Exception as e:
                        return self.http_status(401, -1, str(e))

                elif auth_type == AuthType.API_KEY:
                    # get API key from Authorization header or X-API-Key header
                    api_key = quart.request.headers.get('X-API-Key', '')
                    if not api_key:
                        auth_header = quart.request.headers.get('Authorization', '')
                        if auth_header.startswith('Bearer '):
                            api_key = auth_header.replace('Bearer ', '')

                    if not api_key:
                        return self.http_status(401, -1, 'No valid API key provided')

                    try:
                        is_valid = await self.ap.apikey_service.verify_api_key(api_key)
                        if not is_valid:
                            return self.http_status(401, -1, 'Invalid API key')
                    except Exception as e:
                        return self.http_status(401, -1, str(e))

                elif auth_type == AuthType.USER_TOKEN_OR_API_KEY:
                    # Try API key first (check X-API-Key header)
                    api_key = quart.request.headers.get('X-API-Key', '')

                    if api_key:
                        # API key authentication
                        try:
                            is_valid = await self.ap.apikey_service.verify_api_key(api_key)
                            if not is_valid:
                                return self.http_status(401, -1, 'Invalid API key')
                        except Exception as e:
                            return self.http_status(401, -1, str(e))
                    else:
                        # Try user token authentication (Authorization header)
                        token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                        if not token:
                            return self.http_status(
                                401, -1, 'No valid authentication provided (user token or API key required)'
                            )

                        try:
                            user_email = await self.ap.user_service.verify_jwt_token(token)

                            # check if this account exists
                            user = await self.ap.user_service.get_user_by_email(user_email)
                            if not user:
                                return self.http_status(401, -1, 'User not found')

                            # check if f accepts user_email parameter
                            if 'user_email' in f.__code__.co_varnames:
                                kwargs['user_email'] = user_email
                        except Exception:
                            # If user token fails, maybe it's an API key in Authorization header
                            try:
                                is_valid = await self.ap.apikey_service.verify_api_key(token)
                                if not is_valid:
                                    return self.http_status(401, -1, 'Invalid authentication credentials')
                            except Exception as e:
                                return self.http_status(401, -1, str(e))

                try:
                    return await f(*args, **kwargs)

                except Exception as e:  # 自动 500
                    traceback.print_exc()
                    # return self.http_status(500, -2, str(e))
                    return self.http_status(500, -2, str(e))

            new_f = handler_error
            new_f.__name__ = (self.name + rule).replace('/', '__')
            new_f.__doc__ = f.__doc__

            self.quart_app.route(rule, **options)(new_f)
            return f

        return decorator

    def success(self, data: typing.Any = None) -> quart.Response:
        """Return a 200 response"""
        return quart.jsonify(
            {
                'code': 0,
                'msg': 'ok',
                'data': data,
            }
        )

    def fail(self, code: int, msg: str) -> quart.Response:
        """Return an error response"""

        return quart.jsonify(
            {
                'code': code,
                'msg': msg,
            }
        )

    def http_status(self, status: int, code: int, msg: str) -> typing.Tuple[quart.Response, int]:
        """返回一个指定状态码的响应"""
        return (self.fail(code, msg), status)
