"""Translate business failures into stable application errors without HTTP imports."""

from __future__ import annotations

from langbot_plugin.box.errors import BoxAdmissionError
from pydantic import ValidationError


from ...cloud.entitlements import EntitlementUnavailableError
from ...core.errors import TaskCapacityError
from ...utils.bounded_executor import BlockingWorkCapacityError
from ...workspace.collaboration import MembershipPermissionError, WorkspaceCollaborationError
from ...workspace.errors import WorkspaceExecutionUnavailableError, WorkspaceNotFoundError
from ..authz import AuthorizationError
from ..http.service.bot_errors import BotApplyError
from .contracts import ApplicationAPIError, ApplicationAPIException


def error_from_exception(exc: Exception, *, operation_id: str = '') -> ApplicationAPIError:
    from ...agent.runner.errors import (
        RunnerError,
        RunnerExecutionError,
        RunnerNotAuthorizedError,
        RunnerNotFoundError,
        RunnerProtocolError,
    )

    if isinstance(exc, ApplicationAPIException):
        return exc.error
    if isinstance(exc, AuthorizationError):
        return ApplicationAPIError(exc.error_code, str(exc), exc.status_code)
    if isinstance(exc, (WorkspaceNotFoundError, FileNotFoundError)):
        return ApplicationAPIError('resource_not_found', 'Resource not found', 404)
    if isinstance(exc, WorkspaceExecutionUnavailableError):
        return ApplicationAPIError('workspace_unavailable', 'Workspace execution is unavailable', 409)
    if isinstance(exc, MembershipPermissionError):
        return ApplicationAPIError(exc.code, str(exc), 403)
    if isinstance(exc, WorkspaceCollaborationError):
        return ApplicationAPIError(exc.code, str(exc), 400)
    if isinstance(exc, BoxAdmissionError):
        return ApplicationAPIError('managed_sandbox_unavailable', str(exc), 403)
    if isinstance(exc, EntitlementUnavailableError):
        code = 'managed_sandbox_unavailable' if operation_id.startswith('box.') else 'entitlement_unavailable'
        return ApplicationAPIError(code, str(exc), 403)
    if isinstance(exc, TaskCapacityError):
        return ApplicationAPIError('task_capacity_exceeded', str(exc), 429)
    if isinstance(exc, BlockingWorkCapacityError):
        return ApplicationAPIError('blocking_work_capacity_exceeded', str(exc), 429)
    if isinstance(exc, BotApplyError):
        return ApplicationAPIError('bot_apply_failed', str(exc), 400, details={'uuid': exc.bot_uuid})
    if isinstance(exc, RunnerExecutionError):
        return ApplicationAPIError(exc.error_code or 'runner_execution_failed', exc.message, 422)
    if isinstance(exc, RunnerNotFoundError):
        return ApplicationAPIError('runner_not_found', 'The configured Agent runner is unavailable', 409)
    if isinstance(exc, RunnerNotAuthorizedError):
        return ApplicationAPIError('runner_not_authorized', 'The configured Agent runner is not authorized', 403)
    if isinstance(exc, RunnerProtocolError):
        return ApplicationAPIError('runner_protocol_error', 'The Agent runner returned an invalid response', 502)
    if isinstance(exc, RunnerError):
        return ApplicationAPIError('runner_error', 'The Agent runner could not complete this test', 502)
    code = getattr(exc, 'error_code', None) or getattr(exc, 'code', None)
    status = getattr(exc, 'status_code', None) or getattr(exc, 'status', None)
    if isinstance(code, str) and type(status) is int and 400 <= status <= 599:
        return ApplicationAPIError(code, str(exc), status)
    if isinstance(exc, ValidationError):
        # Pydantic's normal text includes raw provider/plugin configuration values.
        return ApplicationAPIError('validation_error', 'Invalid operation data', 400)
    if isinstance(exc, ValueError):
        return ApplicationAPIError('validation_error', str(exc), 400)
    return ApplicationAPIError('application_error', 'Application operation failed', 500)
