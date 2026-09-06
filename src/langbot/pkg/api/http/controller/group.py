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
from ....utils import bounded_executor
from ....workspace.collaboration import MembershipPermissionError, WorkspaceCollaborationError
from ....workspace.errors import WorkspaceNotFoundError
from ....cloud.entitlements import EntitlementUnavailableError
from ....core.errors import TaskCapacityError
from ....provider.modelmgr.codex_errors import CodexProviderError
from ..authz import (
    AuthenticationDeniedError,
    AuthorizationError,
    Permission,
    PermissionDeniedError,
    WorkspaceRequiredError,
    permissions_for_role,
    require_permission,
)
from ..context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from ....cloud.support_admin import SupportAdminSessionError

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


_SUPPORT_ADMIN_DENIED_PERMISSIONS = frozenset(
    {
        Permission.MEMBER_VIEW.value,
        Permission.MEMBER_INVITE.value,
        Permission.MEMBER_UPDATE_ROLE.value,
        Permission.MEMBER_REMOVE.value,
    }
)


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
                request_context: RequestContext | None = None
                if auth_type == AuthType.ACCOUNT_TOKEN:
                    authorization = quart.request.headers.get('Authorization', '')
                    if not authorization.startswith('Bearer '):
                        return self.http_status(401, -1, 'No valid user token provided')
                    token = authorization.removeprefix('Bearer ')
                    if not token:
                        return self.http_status(401, -1, 'No valid user token provided')

                    try:
                        if self._is_support_admin_token(token):
                            raise AuthenticationDeniedError(
                                'Support admin tokens cannot be refreshed or used on account endpoints'
                            )
                        account, user_email = await self._authenticate_account(token)
                        # Account-token routes deliberately stop before Workspace
                        # selection. They may bootstrap a selector, but cannot
                        # receive RequestContext or enforce Workspace permissions.
                        self._inject_handler_context(f, kwargs, user_email, None, account)
                    except Exception as e:
                        return self._auth_error_response(e)

                elif auth_type == AuthType.USER_TOKEN:
                    # get token from Authorization header
                    token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')

                    if not token:
                        return self.http_status(401, -1, 'No valid user token provided')

                    try:
                        request_context = await self._authenticate_support_admin(token, auth_type)
                        if request_context is not None:
                            self._require_support_admin_route_allowed(rule, f, permission)
                            user_email = None
                        else:
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
                    token = quart.request.headers.get('Authorization', '').replace('Bearer ', '')
                    if token and self._is_support_admin_token(token):
                        try:
                            request_context = await self._authenticate_support_admin(token, auth_type)
                            if request_context is None:
                                raise AuthenticationDeniedError('Invalid support admin token')
                            self._require_support_admin_route_allowed(rule, f, permission)
                            if permission is not None:
                                require_permission(request_context, permission)
                            self._inject_handler_context(f, kwargs, None, request_context)
                        except Exception as e:
                            return self._auth_error_response(e)
                    # Try API key first (check X-API-Key header)
                    elif api_key := quart.request.headers.get('X-API-Key', ''):
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
                    if request_context is not None:
                        with bounded_executor.blocking_work_scope(request_context.workspace_uuid):
                            persistence_mgr = getattr(
                                self.ap,
                                'persistence_mgr',
                                None,
                            )
                            tenant_scope_descriptor = getattr(
                                type(persistence_mgr),
                                'tenant_scope',
                                None,
                            )
                            if callable(tenant_scope_descriptor):
                                # Authorization discovery is complete. Carry
                                # the trusted Workspace identity across the
                                # handler, but do not reserve a database
                                # connection while it waits on providers,
                                # runtimes, uploads, or streamed clients.
                                # Services that need atomic writes open a UoW.
                                async with persistence_mgr.tenant_scope(request_context.workspace_uuid):
                                    return await f(*args, **kwargs)
                            return await f(*args, **kwargs)
                    return await f(*args, **kwargs)

                except Exception as e:  # 自动 500
                    if isinstance(e, CodexProviderError):
                        return self.http_status(e.status_code, e.error_code, str(e))
                    if isinstance(e, AuthorizationError):
                        return self.http_status(e.status_code, e.error_code, str(e))
                    if isinstance(e, WorkspaceNotFoundError):
                        return self.http_status(404, 'resource_not_found', 'Resource not found')
                    if isinstance(e, MembershipPermissionError):
                        return self.http_status(403, e.code, str(e))
                    if isinstance(e, WorkspaceCollaborationError):
                        return self.http_status(400, e.code, str(e))
                    if isinstance(e, TaskCapacityError):
                        return self.http_status(429, 'task_capacity_exceeded', str(e))
                    if isinstance(
                        e,
                        bounded_executor.BlockingWorkCapacityError,
                    ):
                        return self.http_status(
                            429,
                            'blocking_work_capacity_exceeded',
                            str(e),
                        )
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

    def _is_support_admin_token(self, token: str) -> bool:
        service = getattr(self.ap, 'support_admin_session_service', None)
        detector = getattr(service, 'is_support_admin_token', None)
        return callable(detector) and detector(token) is True

    async def _authenticate_support_admin(
        self,
        token: str,
        auth_type: AuthType,
        *,
        workspace_uuid: str | None = None,
        request_id: str | None = None,
    ) -> RequestContext | None:
        service = getattr(self.ap, 'support_admin_session_service', None)
        detector = getattr(service, 'is_support_admin_token', None)
        if service is None or not callable(detector) or detector(token) is not True:
            return None

        requested_workspace_uuid = (
            workspace_uuid if workspace_uuid is not None else quart.request.headers.get('X-Workspace-Id')
        )
        if not requested_workspace_uuid:
            raise WorkspaceRequiredError('Support admin token requires an explicit Workspace selector')
        try:
            identity = await service.authenticate_token(
                token,
                requested_workspace_uuid=requested_workspace_uuid,
            )
        except SupportAdminSessionError as exc:
            raise AuthenticationDeniedError(str(exc)) from exc

        entitlement_revision = await self._resolve_entitlement_revision(
            identity.instance_uuid,
            identity.workspace_uuid,
        )
        request_context = RequestContext(
            instance_uuid=identity.instance_uuid,
            placement_generation=identity.placement_generation,
            request_id=request_id or self.request_id(),
            auth_type=auth_type.value,
            principal=PrincipalContext(
                principal_type=PrincipalType.SUPPORT_ADMIN,
                actor_account_uuid=identity.actor_account_uuid,
                support_session_id=identity.grant_jti_hash,
            ),
            workspace=WorkspaceContext(
                workspace_uuid=identity.workspace_uuid,
                membership_uuid=None,
                role='owner',
                permissions=permissions_for_role('owner') - _SUPPORT_ADMIN_DENIED_PERMISSIONS,
                membership_revision=0,
            ),
            entitlement_revision=entitlement_revision,
        )
        quart.g.request_context = request_context
        quart.g.workspace_membership = None
        return request_context

    @staticmethod
    def _require_support_admin_route_allowed(
        rule: str,
        handler: RouteCallable,
        permission: Permission | str | None,
    ) -> None:
        parameters = inspect.signature(handler).parameters
        if rule.startswith('/api/v1/user/') or 'account' in parameters or 'user_email' in parameters:
            raise AuthenticationDeniedError('Support admin tokens are not permitted on account endpoints')
        permission_value = permission.value if isinstance(permission, Permission) else permission
        if permission_value in _SUPPORT_ADMIN_DENIED_PERMISSIONS:
            raise PermissionDeniedError(permission_value)

    async def _resolve_account_context(
        self,
        account: typing.Any,
        auth_type: AuthType,
        *,
        token: str | None = None,
    ) -> RequestContext | None:
        collaboration_service = getattr(self.ap, 'workspace_collaboration_service', None)
        account_uuid = getattr(account, 'uuid', None)
        # Compatibility for isolated controller tests that do not wire the tenancy kernel.
        if collaboration_service is None or not isinstance(account_uuid, str):
            return None

        requested_workspace_uuid = quart.request.headers.get('X-Workspace-Id')
        access = await collaboration_service.resolve_account_workspace(account_uuid, requested_workspace_uuid)
        entitlement_revision = await self._resolve_entitlement_revision(
            access.execution.instance_uuid,
            access.workspace.uuid,
        )
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
            entitlement_revision=entitlement_revision,
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
                    entitlement_revision = await self._resolve_entitlement_revision(
                        identity.instance_uuid,
                        identity.workspace_uuid,
                    )
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
                        entitlement_revision=entitlement_revision,
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

    async def _resolve_entitlement_revision(self, instance_uuid: str, workspace_uuid: str) -> int:
        deployment = getattr(self.ap, 'deployment', None)
        if deployment is None or not getattr(deployment, 'multi_workspace_enabled', False):
            return 0
        resolver = getattr(self.ap, 'entitlement_resolver', None)
        if resolver is None:
            raise EntitlementUnavailableError('Workspace entitlement resolver is unavailable')
        if instance_uuid != resolver.instance_uuid:
            raise EntitlementUnavailableError('Workspace entitlement targets another LangBot instance')
        snapshot = await resolver.resolve(workspace_uuid)
        return snapshot.entitlement_revision

    @staticmethod
    def _inject_handler_context(
        handler: RouteCallable,
        kwargs: dict[str, typing.Any],
        user_email: str | None,
        request_context: RequestContext | None,
        account: typing.Any = None,
    ) -> None:
        parameters = inspect.signature(handler).parameters
        if user_email is not None and 'user_email' in parameters:
            kwargs['user_email'] = user_email
        if account is not None and 'account' in parameters:
            kwargs['account'] = account
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
        if isinstance(error, EntitlementUnavailableError):
            return self.http_status(403, 'entitlement_unavailable', str(error))
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
