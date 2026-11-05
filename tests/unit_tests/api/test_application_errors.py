"""Application errors preserve business meaning and hide internal failure data."""

import pytest
from langbot_plugin.box.errors import BoxAdmissionError
from pydantic import BaseModel, ValidationError

from langbot.pkg.agent.runner.errors import (
    RunnerExecutionError,
    RunnerNotAuthorizedError,
    RunnerNotFoundError,
    RunnerProtocolError,
)
from langbot.pkg.api.application.errors import error_from_exception
from langbot.pkg.api.http.service.bot_errors import BotApplyError
from langbot.pkg.cloud.entitlements import EntitlementUnavailableError
from langbot.pkg.core.errors import TaskCapacityError
from langbot.pkg.provider.modelmgr.codex_errors import CodexProviderError
from langbot.pkg.utils.bounded_executor import BlockingWorkCapacityError
from langbot.pkg.workspace.collaboration import LastOwnerError, MembershipPermissionError
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError


@pytest.mark.parametrize(
    ('exc', 'code', 'status'),
    [
        (RunnerExecutionError('runner', 'failed', error_code='tool_failed'), 'tool_failed', 422),
        (RunnerNotAuthorizedError('runner', []), 'runner_not_authorized', 403),
        (RunnerNotFoundError('runner'), 'runner_not_found', 409),
        (RunnerProtocolError('runner', 'wrong protocol'), 'runner_protocol_error', 502),
        (MembershipPermissionError('denied'), 'permission_denied', 403),
        (LastOwnerError('last owner'), 'last_owner_required', 400),
        (BoxAdmissionError('no grant'), 'managed_sandbox_unavailable', 403),
        (EntitlementUnavailableError('expired'), 'entitlement_unavailable', 403),
        (TaskCapacityError('full'), 'task_capacity_exceeded', 429),
        (BlockingWorkCapacityError('full'), 'blocking_work_capacity_exceeded', 429),
        (CodexProviderError('known safe error', 429, 'rate_limited'), 'rate_limited', 429),
        (FileNotFoundError('/private/file'), 'resource_not_found', 404),
        (WorkspaceGenerationMismatchError('stale placement'), 'workspace_unavailable', 409),
    ],
)
def test_business_error_mapping(exc, code, status):
    result = error_from_exception(exc)
    assert (result.code, result.status_code) == (code, status)


def test_box_entitlement_and_saved_bot_identity_are_preserved():
    result = error_from_exception(EntitlementUnavailableError('expired'), operation_id='box.status')
    assert (result.code, result.status_code) == ('managed_sandbox_unavailable', 403)
    result = error_from_exception(BotApplyError('Saved configuration could not be applied', bot_uuid='bot-a'))
    assert (result.code, result.status_code, result.details) == ('bot_apply_failed', 400, {'uuid': 'bot-a'})


def test_unknown_and_pydantic_errors_do_not_expose_raw_configuration():
    class CredentialInput(BaseModel):
        token: int

    with pytest.raises(ValidationError) as failure:
        CredentialInput(token='sensitive-value')
    assert 'sensitive-value' not in error_from_exception(failure.value).message
    assert error_from_exception(RuntimeError('raw sensitive backend error')).message == 'Application operation failed'


def test_typed_assistant_and_migration_errors_keep_original_status():
    class ServiceError(ValueError):
        code = 'stale_turn'
        status = 409

    result = error_from_exception(ServiceError('stale_turn'))
    assert (result.code, result.status_code) == ('stale_turn', 409)
