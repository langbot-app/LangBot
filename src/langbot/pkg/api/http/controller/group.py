from __future__ import annotations

import abc
import typing
import enum
import quart
import traceback
import inspect
import uuid
from quart.typing import RouteCallable

from ....utils import constants
from ....workspace.collaboration import MembershipPermissionError, WorkspaceCollaborationError
from ....workspace.errors import WorkspaceNotFoundError
from ..authz import AuthorizationError, Permission, permissions_for_role, require_permission
from ..context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

if typing.TYPE_CHECKING:
    from ....core.app import Application

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
    ACCOUNT_TOKEN = 'account-token'
    USER_TOKEN = 'user-token'
    API_KEY = 'api-key'
    USER_TOKEN_OR_API_KEY = 'user-token-or-api-key'


class RouterGroup(abc.ABC):
    name: str

    path: str

    ap: Application

    quart_app: quart.Quart

    def __init__(self, ap: Application, quart_app: quart.Quart) -> None:
        self.ap = ap
        self.quart_app = quart_app

    @abc.abstractmethod
    async def initialize(self) -> None:
        pass

    def route(
        self,
        rule: str,
        auth_type: AuthType = AuthType.USER_TOKEN,
        permission: Permission | str | None = None,
        **options: typing.Any,
    ) -> typing.Callable[[RouteCallable], RouteCallable]:  # decorator
        """Register a route"""

        if auth_type == AuthType.ACCOUNT_TOKEN and permission is not None:
            raise ValueError('Account-token routes cannot declare Workspace permissions')

        def decorator(f: RouteCallable) -> RouteCallable:
            nonlocal rule
            rule = self.path + rule

            async def handler_error(*args, **kwargs):
                if auth_type == AuthType.ACCOUNT_TOKEN:
                    authorization = quart.request.headers.get('Authorization', '')
                    if not authorization.startswith('Bearer '):
                        return self.http_status(401, -1, 'No valid user token provided')
                    token = authorization.removeprefix('Bearer ')
                    if not token:
                        return self.http_status(401, -1, 'No valid user token provided')

                    try:
                        _, user_email = await self._authenticate_account(token)
                        # Account-token routes deliberately stop before Workspace
                        # selection. They may bootstrap a selector, but cannot
                        # receive RequestContext or enforce Workspace permissions.
                        self._inject_handler_context(f, kwargs, user_email, None)
                    except Exception as e:
                        return self._auth_error_response(e)

                elif auth_type == AuthType.USER_TOKEN:
                    # get token from Authorization header
                    token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                    if not token:
                        return self.http_status(401, -1, 'No valid user token provided')

                    try:
                        account, user_email = await self._authenticate_account(token)
                        request_context = await self._resolve_account_context(account, auth_type)
                        if permission is not None:
                            if request_context is None:
                                raise AuthorizationError('Workspace authorization is unavailable')
                            require_permission(request_context, permission)
                        self._inject_handler_context(f, kwargs, user_email, request_context)
                    except Exception as e:
                        return self._auth_error_response(e)

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
                        request_context = await self._authenticate_api_key(api_key, auth_type)
                        if permission is not None:
                            require_permission(request_context, permission)
                        self._inject_handler_context(f, kwargs, None, request_context)
                    except Exception as e:
                        return self._auth_error_response(e)

                elif auth_type == AuthType.USER_TOKEN_OR_API_KEY:
                    # Try API key first (check X-API-Key header)
                    api_key = quart.request.headers.get('X-API-Key', '')

                    if api_key:
                        # API key authentication
                        try:
                            request_context = await self._authenticate_api_key(api_key, auth_type)
                            if permission is not None:
                                require_permission(request_context, permission)
                            self._inject_handler_context(f, kwargs, None, request_context)
                        except Exception as e:
                            return self._auth_error_response(e)
                    else:
                        # Try user token authentication (Authorization header)
                        token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                        if not token:
                            return self.http_status(
                                401, -1, 'No valid authentication provided (user token or API key required)'
                            )

                        try:
                            account, user_email = await self._authenticate_account(token)
                            request_context = await self._resolve_account_context(account, auth_type)
                            if permission is not None:
                                if request_context is None:
                                    raise AuthorizationError('Workspace authorization is unavailable')
                                require_permission(request_context, permission)
                            self._inject_handler_context(f, kwargs, user_email, request_context)
                        except (AuthorizationError, WorkspaceNotFoundError, MembershipPermissionError) as e:
                            # Authentication succeeded and authorization was
                            # evaluated. Do not reinterpret a denied user token
                            # as an API key, which would mask the stable 403/404.
                            return self._auth_error_response(e)
                        except Exception:
                            # If user token fails, maybe it's an API key in Authorization header
                            try:
                                request_context = await self._authenticate_api_key(token, auth_type)
                                if permission is not None:
                                    require_permission(request_context, permission)
                                self._inject_handler_context(f, kwargs, None, request_context)
                            except Exception as e:
                                return self._auth_error_response(e)

                try:
                    return await f(*args, **kwargs)

                except Exception as e:  # 自动 500
                    if isinstance(e, AuthorizationError):
                        return self.http_status(e.status_code, e.error_code, str(e))
                    if isinstance(e, WorkspaceNotFoundError):
                        return self.http_status(404, 'resource_not_found', 'Resource not found')
                    if isinstance(e, MembershipPermissionError):
                        return self.http_status(403, e.code, str(e))
                    if isinstance(e, WorkspaceCollaborationError):
                        return self.http_status(400, e.code, str(e))
                    request_id = self.request_id()
                    logger = getattr(self.ap, 'logger', self.quart_app.logger)
                    logger.error(
                        f'Unhandled HTTP error request_id={request_id} '
                        f'method={quart.request.method} path={quart.request.path}\n{traceback.format_exc()}'
                    )
                    return self.internal_error_response(request_id)

            new_f = handler_error
            # Quart/Flask requires a unique endpoint name even when the same URL
            # intentionally has separate handlers for different HTTP methods.
            # Include the method set so CRUD routes can declare distinct
            # permissions without colliding during application startup.
            methods = options.get('methods') or ['GET']
            method_suffix = '__'.join(sorted(str(method).upper() for method in methods))
            new_f.__name__ = (self.name + rule + '__' + method_suffix).replace('/', '__')
            new_f.__doc__ = f.__doc__

            self.quart_app.route(rule, **options)(new_f)
            return f

        return decorator

    async def _authenticate_account(self, token: str) -> tuple[typing.Any, str]:
        account: typing.Any = None
        resolver = getattr(self.ap.user_service, 'get_authenticated_account', None)
        if callable(resolver):
            resolved = resolver(token)
            if inspect.isawaitable(resolved):
                account = await resolved

        if isinstance(account, str) or account is None:
            user_email = account or await self.ap.user_service.verify_jwt_token(token)
            account = await self.ap.user_service.get_user_by_email(user_email)
        if account is None:
            raise ValueError('User not found')
        return account, account.user

    async def _resolve_account_context(
        self,
        account: typing.Any,
        auth_type: AuthType,
    ) -> RequestContext | None:
        collaboration_service = getattr(self.ap, 'workspace_collaboration_service', None)
        account_uuid = getattr(account, 'uuid', None)
        # Compatibility for isolated controller tests that do not wire the tenancy kernel.
        if collaboration_service is None or not isinstance(account_uuid, str):
            return None

        requested_workspace_uuid = quart.request.headers.get('X-Workspace-Id')
        access = await collaboration_service.resolve_account_workspace(account_uuid, requested_workspace_uuid)
        request_context = RequestContext(
            instance_uuid=access.execution.instance_uuid,
            placement_generation=access.execution.placement_generation,
            request_id=self.request_id(),
            auth_type=auth_type.value,
            principal=PrincipalContext(
                principal_type=PrincipalType.ACCOUNT,
                account_uuid=account_uuid,
            ),
            workspace=WorkspaceContext(
                workspace_uuid=access.workspace.uuid,
                membership_uuid=access.membership.uuid,
                role=access.membership.role,
                permissions=permissions_for_role(access.membership.role),
                membership_revision=access.membership.projection_revision,
            ),
        )
        quart.g.request_context = request_context
        quart.g.workspace_membership = access.membership
        return request_context

    async def _authenticate_api_key(self, api_key: str, auth_type: AuthType) -> RequestContext:
        authenticator = getattr(self.ap.apikey_service, 'authenticate_api_key', None)
        if callable(authenticator):
            authenticated = authenticator(api_key)
            if inspect.isawaitable(authenticated):
                identity = await authenticated
                if identity is not None:
                    request_context = RequestContext(
                        instance_uuid=identity.instance_uuid,
                        placement_generation=identity.placement_generation,
                        request_id=self.request_id(),
                        auth_type=auth_type.value,
                        principal=PrincipalContext(
                            principal_type=PrincipalType.API_KEY,
                            api_key_uuid=identity.api_key_uuid,
                        ),
                        workspace=WorkspaceContext(
                            workspace_uuid=identity.workspace_uuid,
                            membership_uuid=None,
                            role=None,
                            permissions=identity.permissions,
                        ),
                    )
                    quart.g.request_context = request_context
                    return request_context

        if not await self.ap.apikey_service.verify_api_key(api_key):
            raise ValueError('Invalid API key')
        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise ValueError('API key Workspace binding is unavailable')
        binding = await workspace_service.get_local_execution_binding()
        request_context = RequestContext(
            instance_uuid=binding.instance_uuid or constants.instance_id,
            placement_generation=binding.placement_generation,
            request_id=self.request_id(),
            auth_type=auth_type.value,
            principal=PrincipalContext(
                principal_type=PrincipalType.API_KEY,
                api_key_uuid='legacy-oss-api-key',
            ),
            workspace=WorkspaceContext(
                workspace_uuid=binding.workspace_uuid,
                membership_uuid=None,
                role=None,
                permissions=frozenset(item.value for item in Permission),
            ),
        )
        quart.g.request_context = request_context
        return request_context

    @staticmethod
    def _inject_handler_context(
        handler: RouteCallable,
        kwargs: dict[str, typing.Any],
        user_email: str | None,
        request_context: RequestContext | None,
    ) -> None:
        parameters = handler.__code__.co_varnames
        if user_email is not None and 'user_email' in parameters:
            kwargs['user_email'] = user_email
        if request_context is not None:
            if 'request_context' in parameters:
                kwargs['request_context'] = request_context
            elif 'ctx' in parameters:
                kwargs['ctx'] = request_context

    def _auth_error_response(self, error: Exception) -> typing.Any:
        if isinstance(error, AuthorizationError):
            return self.http_status(error.status_code, error.error_code, str(error))
        if isinstance(error, WorkspaceNotFoundError):
            return self.http_status(404, 'resource_not_found', 'Resource not found')
        if isinstance(error, MembershipPermissionError):
            return self.http_status(403, error.code, str(error))
        request_id = self.request_id()
        logger = getattr(self.ap, 'logger', self.quart_app.logger)
        logger.warning(f'Authentication failed request_id={request_id} error_type={type(error).__name__}: {error}')
        return self.http_status(
            401,
            'invalid_authentication',
            'Invalid authentication credentials',
        )

    def request_id(self) -> str:
        """Return one stable request ID for authentication, logs, and errors."""

        request_context = getattr(quart.g, 'request_context', None)
        request_id = getattr(request_context, 'request_id', None) or getattr(quart.g, 'request_id', None)
        if not request_id:
            candidate = str(quart.request.headers.get('X-Request-Id') or '').strip()
            if not candidate or len(candidate) > 128 or any(ord(char) < 32 for char in candidate):
                candidate = str(uuid.uuid4())
            request_id = candidate
            quart.g.request_id = request_id
        return str(request_id)

    def internal_error_response(self, request_id: str | None = None) -> typing.Tuple[quart.Response, int]:
        """Return a stable 500 response without exposing the underlying exception."""

        resolved_request_id = request_id or self.request_id()
        response = quart.jsonify(
            {
                'code': 'internal_error',
                'msg': 'Internal server error',
                'request_id': resolved_request_id,
            }
        )
        response.headers['X-Request-Id'] = resolved_request_id
        return response, 500

    def success(self, data: typing.Any = None) -> quart.Response:
        """Return a 200 response"""
        return quart.jsonify(
            {
                'code': 0,
                'msg': 'ok',
                'data': data,
            }
        )

    def fail(self, code: int | str, msg: str) -> quart.Response:
        """Return an error response"""

        return quart.jsonify(
            {
                'code': code,
                'msg': msg,
            }
        )

    def http_status(self, status: int, code: int | str, msg: str) -> typing.Tuple[quart.Response, int]:
        """返回一个指定状态码的响应"""
        return (self.fail(code, msg), status)
