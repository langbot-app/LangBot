"""Workspace governance settings routes.

Exposes the "成员操作日志溯源" (member operation traceability) surface:

* ``GET  /api/v1/settings/governance``            read level + template table
* ``PUT  /api/v1/settings/governance``            change level / retention
* ``GET  /api/v1/settings/operation-logs``        page through records
* ``GET  /api/v1/settings/operation-logs/filters`` available filter values
* ``POST /api/v1/settings/operation-logs/prune``  enforce retention now
* ``DEL  /api/v1/settings/operation-logs``        clear records

Every route requires ``audit.view``, which is granted to the Workspace owner
and admin only. Write routes additionally require an owning/admin role so a
future permission grant cannot silently widen who may reconfigure tracing.
"""

from __future__ import annotations

import datetime
import json
import typing

import quart

from ...authz import Permission
from ...context import RequestContext
from ...service import settings as settings_service
from .. import group


def _parse_timestamp(value: str | None) -> datetime.datetime | None:
    """Parse an ISO-8601 query parameter, tolerating a trailing ``Z``."""

    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith('Z'):
        candidate = candidate[:-1] + '+00:00'
    try:
        parsed = datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    # Stored timestamps are naive UTC; normalise aware inputs before comparing.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _csv_cell(value: typing.Any) -> str:
    """Render one CSV cell with the standard quoting rules."""

    if value is None:
        return ''
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return '"' + text.replace('"', '""') + '"'


@group.group_class('settings', '/api/v1/settings')
class SettingsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/governance',
            methods=['GET', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> typing.Any:
            service = self.ap.workspace_settings_service
            if quart.request.method == 'GET':
                return self.success(data=await service.describe_governance(request_context.workspace_uuid))

            if not settings_service.role_may_configure(request_context.workspace.role):
                return self.http_status(
                    403,
                    'permission_denied',
                    'Only Workspace owners and admins can change tracing settings',
                )

            data = await quart.request.get_json(silent=True) or {}
            # The previous level is captured before the write so the trace can
            # answer "what was changed into what" for the governance change
            # itself, not only for the resources it protects.
            before = await service.describe_governance(request_context.workspace_uuid)
            updated = await service.set_operation_level(
                request_context.workspace_uuid,
                data.get('level', before['configured_level']),
                retention_days=data.get('retention_days'),
                max_rows=data.get('max_rows'),
                dedupe_window_seconds=data.get('dedupe_window_seconds'),
            )

            account_name = None
            if request_context.account_uuid and self.ap.user_service is not None:
                account = await self.ap.user_service.get_user_by_uuid(request_context.account_uuid)
                account_name = account.user if account is not None else None

            changes = settings_service.changed_fields(
                {
                    'configured_level': before['configured_level'],
                    'retention_days': before['retention_days'],
                    'max_rows': before['max_rows'],
                    'dedupe_window_seconds': before['dedupe_window_seconds'],
                },
                {
                    'configured_level': updated['configured_level'],
                    'retention_days': updated['retention_days'],
                    'max_rows': updated['max_rows'],
                    'dedupe_window_seconds': updated['dedupe_window_seconds'],
                },
            )
            if changes:
                await service.record(
                    request_context.workspace_uuid,
                    rule=settings_service.ACTION_RULES_BY_ACTION['settings_update'],
                    level=max(
                        await service.effective_level(
                            request_context.workspace_uuid,
                            request_context.workspace.role,
                        ),
                        settings_service.OPERATION_LEVEL_MUTATION,
                    ),
                    actor_account_uuid=request_context.account_uuid,
                    actor_name=account_name,
                    actor_role=request_context.workspace.role,
                    principal_type=request_context.principal.principal_type.value,
                    request_id=request_context.request_id,
                    http_method=quart.request.method,
                    route='/api/v1/settings/governance',
                    outcome='ok',
                    summary=settings_service.build_summary(
                        settings_service.ACTION_RULES_BY_ACTION['settings_update'], changes
                    ),
                    changes=changes,
                )
            return self.success(data=updated)

        @self.route(
            '/operation-logs',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> typing.Any:
            # Read-only by design: operation records are immutable and cannot
            # be deleted on demand. Only the retention policy may prune them.
            service = self.ap.workspace_settings_service

            args = quart.request.args
            level_raw = args.get('level')
            result = await service.query_logs(
                request_context.workspace_uuid,
                limit=_parse_int(args.get('limit'), settings_service.DEFAULT_PAGE_SIZE),
                offset=_parse_int(args.get('offset'), 0),
                action=args.get('action') or None,
                resource_type=args.get('resource_type') or None,
                actor_account_uuid=args.get('actor') or None,
                level=_parse_int(level_raw, 0) if level_raw not in (None, '') else None,
                since=_parse_timestamp(args.get('since')),
                until=_parse_timestamp(args.get('until')),
            )
            return self.success(data=result)

        @self.route(
            '/operation-logs/filters',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> typing.Any:
            service = self.ap.workspace_settings_service
            options = await service.list_filter_options(request_context.workspace_uuid)
            options['governance'] = await service.describe_governance(request_context.workspace_uuid)
            return self.success(data=options)

        @self.route(
            '/operation-logs/export',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> typing.Any:
            """Download the filtered records as a CSV attachment.

            The export is read-only and shares the exact filters of the panel,
            so what an operator sees is what the artifact contains.
            """

            args = quart.request.args
            level_raw = args.get('level')
            service = self.ap.workspace_settings_service
            document = await service.export_logs(
                request_context.workspace_uuid,
                action=args.get('action') or None,
                resource_type=args.get('resource_type') or None,
                actor_account_uuid=args.get('actor') or None,
                level=_parse_int(level_raw, 0) if level_raw not in (None, '') else None,
                since=_parse_timestamp(args.get('since')),
                until=_parse_timestamp(args.get('until')),
            )

            columns = (
                'id',
                'created_at',
                'action',
                'resource_type',
                'resource_id',
                'actor_account_uuid',
                'actor_name',
                'actor_role',
                'principal_type',
                'http_method',
                'route',
                'outcome',
                'status_code',
                'level_name',
                'integrity_ok',
                'chain_ok',
                'tampered',
                'record_hash',
                'prev_hash',
                'duration_ms',
                'summary',
                'changes',
                'detail',
            )
            lines = [','.join(columns)]
            for record in document['records']:
                lines.append(','.join(_csv_cell(record.get(column)) for column in columns))

            # Prepend a UTF-8 BOM so spreadsheet tools detect the encoding.
            body = '\ufeff' + '\r\n'.join(lines) + '\r\n'
            filename = f"operation-logs-{document['exported_at'].replace(':', '')}.csv"
            response = quart.Response(body, mimetype='text/csv', content_type='text/csv; charset=utf-8')
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
