"""Workspace application boundary; protocol consumers opt in separately."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager, aclosing
import time
import asyncio
import logging

from pydantic import TypeAdapter, ValidationError

from ..authz import AuthenticationDeniedError, require_permission
from ..context import PrincipalType, RequestContext
from ...i18n import language_scope
from ...i18n.workspace import get_workspace_language
from ...utils.bounded_executor import blocking_work_scope
from .contracts import ApplicationAPIError, ApplicationAPIException, Input, Operation
from .streaming import isolated_stream


class ApplicationAPI:
    def __init__(self, ap, *, operations: Iterable[Operation] | None = None):
        self.ap = ap
        if operations is None:
            from .service_operations import operations as service_operations
            from .auxiliary import operations as auxiliary_operations
            from .plugin_operations import operations as plugin_operations
            from .platform_setup import operations as platform_operations
            from .connection_operations import operations as connection_operations
            from .workspace_streams import operations as workspace_streams

            operations = [
                *service_operations(),
                *auxiliary_operations(),
                *plugin_operations(),
                *platform_operations(),
                *connection_operations(),
                *workspace_streams(),
            ]
        self._operations: dict[str, Operation] = {}
        for spec in operations:
            if spec.operation_id in self._operations:
                raise ValueError(f'Duplicate application operation: {spec.operation_id}')
            self._operations[spec.operation_id] = spec

    def operation_catalog(self) -> list[dict]:
        return [spec.as_dict() for spec in self._operations.values()]

    def _operation(self, operation_id, streaming):
        spec = self._operations.get(operation_id)
        if spec is None:
            raise ApplicationAPIException(
                ApplicationAPIError('unknown_operation', 'Unknown application operation', 404)
            )
        if spec.streaming != streaming:
            raise ApplicationAPIException(
                ApplicationAPIError('invalid_execution_mode', 'Use the operation execution mode', 400)
            )
        return spec

    @asynccontextmanager
    async def _scope(self, spec, context, input):
        if not isinstance(context, RequestContext) or not context.workspace_uuid.strip():
            raise AuthenticationDeniedError('An authenticated Workspace context is required')
        if context.principal.principal_type not in {
            PrincipalType.ACCOUNT,
            PrincipalType.API_KEY,
            PrincipalType.SUPPORT_ADMIN,
        }:
            raise AuthenticationDeniedError('This principal cannot invoke Workspace management operations')
        if spec.principals is not None and context.principal.principal_type not in spec.principals:
            raise AuthenticationDeniedError('This operation requires a different principal')
        require_permission(context, spec.permission)
        try:
            payload = spec.input_type.model_validate(input)
        except ValidationError as exc:
            # Validation errors may contain credentials; never include their input values.
            fields = ', '.join('.'.join(map(str, e['loc'])) for e in exc.errors(include_input=False))
            raise ApplicationAPIException(
                ApplicationAPIError('invalid_input', f'Invalid fields: {fields}', 400)
            ) from exc
        binding = await self.ap.workspace_service.get_execution_binding(
            context.workspace_uuid,
            expected_generation=context.placement_generation,
        )
        if binding.instance_uuid != context.instance_uuid:
            raise AuthenticationDeniedError('Workspace belongs to a different instance')
        async with self.ap.persistence_mgr.tenant_scope(context.workspace_uuid):
            with blocking_work_scope(context.workspace_uuid):
                with language_scope(await get_workspace_language(self.ap, context.workspace_uuid)):
                    yield payload

    @staticmethod
    def _validate_result(spec, result):
        try:
            return TypeAdapter(spec.output_type).validate_python(result, strict=True)
        except ValidationError as exc:
            raise ApplicationAPIException(
                ApplicationAPIError('invalid_output', 'Application operation returned an invalid result', 500)
            ) from exc

    async def execute(self, operation_id: str, context: RequestContext, input: dict | Input):
        spec = self._operation(operation_id, streaming=False)
        observed_at = time.monotonic()
        payload = None
        started = False
        outcome, status = 'ok', 200
        try:
            async with self._scope(spec, context, input) as payload:
                started = True
                result = await spec.handler(self.ap, context, payload)
            return self._validate_result(spec, result)
        except asyncio.CancelledError:
            outcome, status = ('unknown' if started and spec.side_effect else 'error'), 499
            raise
        except Exception as exc:
            from .errors import error_from_exception

            error = error_from_exception(exc, operation_id=operation_id)
            outcome, status = self._failure_outcome(spec, error, started), error.status_code
            if isinstance(exc, ApplicationAPIException):
                raise
            raise ApplicationAPIException(error) from exc
        finally:
            await self._record(spec, context, observed_at, payload, outcome=outcome, status=status, started=started)

    async def stream(self, operation_id: str, context: RequestContext, input: dict | Input):
        spec = self._operation(operation_id, streaming=True)
        observed_at = time.monotonic()

        async def produce():
            payload = None
            started = False
            outcome, status = 'ok', 200
            try:
                async with self._scope(spec, context, input) as payload:
                    started = True
                    source = await spec.handler(self.ap, context, payload)
                    async with aclosing(source):
                        async for item in source:
                            yield self._validate_result(spec, item)
            except (asyncio.CancelledError, GeneratorExit):
                outcome, status = ('unknown' if started and spec.side_effect else 'error'), 499
                raise
            except Exception as exc:
                from .errors import error_from_exception

                error = error_from_exception(exc, operation_id=operation_id)
                outcome, status = self._failure_outcome(spec, error, started), error.status_code
                if isinstance(exc, ApplicationAPIException):
                    raise
                raise ApplicationAPIException(error) from exc
            finally:
                await self._record(spec, context, observed_at, payload, outcome=outcome, status=status, started=started)

        async with aclosing(isolated_stream(produce())) as responses:
            async for response in responses:
                yield response

    @staticmethod
    def _failure_outcome(spec, error, started):
        if error.status_code in {401, 403}:
            return 'denied'
        if started and spec.side_effect and error.code in {'invalid_output', 'application_error', 'bot_apply_failed'}:
            return 'unknown'
        return 'error'

    async def _record(self, spec, context, observed_at, payload=None, *, outcome='ok', status=200, started=False):
        from ..context import PrincipalContext, WorkspaceContext

        if not (
            isinstance(context, RequestContext)
            and isinstance(context.principal, PrincipalContext)
            and isinstance(context.workspace, WorkspaceContext)
            and isinstance(context.workspace_uuid, str)
            and context.workspace_uuid.strip()
            and context.instance_uuid
            and type(context.placement_generation) is int
            and context.placement_generation > 0
            and context.principal.principal_type
            in {
                PrincipalType.ACCOUNT,
                PrincipalType.API_KEY,
                PrincipalType.SUPPORT_ADMIN,
            }
        ):
            return
        principal_id = (
            context.principal.api_key_uuid
            if context.principal.principal_type == PrincipalType.API_KEY
            else context.principal.actor_account_uuid
            if context.principal.principal_type == PrincipalType.SUPPORT_ADMIN
            else context.account_uuid
        )
        if not isinstance(principal_id, str) or not principal_id.strip():
            return
        # These successful handlers already emit their richer domain records.
        if outcome == 'ok' and spec.operation_id in {
            'workspace.member.update',
            'workspace.member.remove',
            'workspace.invitation.create',
            'settings.governance.update',
        }:
            return
        service = getattr(self.ap, 'workspace_settings_service', None)
        if service is None:
            return
        from ...operation_trace.service import ActionRule, bucket_allows

        try:
            if not started:
                # Authorization can fail before the normal execution fence. Never
                # publish a trace into an unknown or foreign Workspace.
                binding = await self.ap.workspace_service.get_execution_binding(
                    context.workspace_uuid,
                    expected_generation=context.placement_generation,
                )
                if binding.instance_uuid != context.instance_uuid:
                    return
            level = await service.effective_level(context.workspace_uuid, context.workspace.role)
            bucket = 'write' if spec.side_effect else 'read'
            if not bucket_allows(bucket, level):
                return
            parts = spec.operation_id.split('.')
            if not spec.side_effect:
                action = 'export' if 'export' in parts else 'view'
            elif any(part in {'delete', 'remove', 'revoke', 'uninstall'} for part in parts):
                action = 'delete'
            elif any(part in {'create', 'install', 'upload', 'copy', 'add', 'import'} for part in parts):
                action = 'create'
            else:
                action = 'update'
            # Only named resource identifiers from validated DTOs enter the trace.
            # Config objects, file bytes, URLs, credentials and request text never do.
            identity = {}
            if isinstance(payload, Input):
                for name in type(payload).model_fields:
                    if name.endswith(('_uuid', '_id')) or name in {
                        'author',
                        'plugin_author',
                        'plugin_name',
                        'skill_name',
                        'server_name',
                        'owner',
                        'repo',
                    }:
                        value = getattr(payload, name)
                        if type(value) in {str, int} and value != '':
                            identity[name] = str(value)[:256]
            resource_id = None
            for names in (('author', 'plugin_name'), ('plugin_author', 'plugin_name'), ('owner', 'repo')):
                if all(name in identity for name in names):
                    resource_id = '/'.join(identity[name] for name in names)
                    break
            if resource_id is None and identity:
                resource_id = next(iter(identity.values()))
            await service.record(
                context.workspace_uuid,
                rule=ActionRule(action, 'resource', bucket, parts[0]),
                level=level,
                actor_account_uuid=context.principal.actor_account_uuid or context.account_uuid,
                actor_role=context.workspace.role,
                principal_type=context.principal.principal_type.value,
                api_key_uuid=context.principal.api_key_uuid,
                auth_type=context.auth_type,
                request_id=context.request_id,
                route=spec.operation_id,
                resource_id=resource_id,
                outcome=outcome,
                status_code=status,
                detail={'operation': spec.operation_id, 'version': spec.version},
                duration_ms=int((time.monotonic() - observed_at) * 1000),
            )
        except Exception:
            # Audit failures must preserve the original operation result or error.
            try:
                getattr(self.ap, 'logger', logging.getLogger(__name__)).exception('Application operation trace failed')
            except Exception:
                pass

    async def invoke(self, operation_id: str, context: RequestContext, input: dict | Input):
        return await self.execute(operation_id, context, input)
