from langbot.pkg.api.http import authz
from langbot.pkg.api.http.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext


def _context(role: authz.WorkspaceRole) -> RequestContext:
    return RequestContext(
        instance_uuid='instance-test',
        placement_generation=1,
        request_id='request-test',
        auth_type='user-token',
        principal=PrincipalContext(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid='account-test',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='workspace-test',
            membership_uuid='membership-test',
            role=role.value,
            permissions=authz.permissions_for_role(role),
        ),
    )


def test_owner_has_every_fixed_permission():
    ctx = _context(authz.WorkspaceRole.OWNER)

    assert ctx.workspace.permissions == frozenset(permission.value for permission in authz.Permission)


def test_admin_cannot_transfer_owner_delete_workspace_or_link_billing():
    ctx = _context(authz.WorkspaceRole.ADMIN)

    assert not authz.has_permission(ctx, authz.Permission.OWNER_TRANSFER)
    assert not authz.has_permission(ctx, authz.Permission.WORKSPACE_DELETE)
    assert not authz.has_permission(ctx, authz.Permission.BILLING_LINK_MANAGE)
    assert authz.has_permission(ctx, authz.Permission.MEMBER_INVITE)


def test_operator_can_run_but_cannot_manage_resources_or_secrets():
    ctx = _context(authz.WorkspaceRole.OPERATOR)

    assert authz.has_permission(ctx, authz.Permission.RUNTIME_OPERATE)
    assert not authz.has_permission(ctx, authz.Permission.RESOURCE_MANAGE)
    assert not authz.has_permission(ctx, authz.Permission.PROVIDER_SECRET_MANAGE)


def test_unknown_role_has_no_permissions():
    assert authz.permissions_for_role('unknown') == frozenset()


def test_require_permission_reports_stable_permission():
    ctx = _context(authz.WorkspaceRole.VIEWER)

    try:
        authz.require_permission(ctx, authz.Permission.RESOURCE_MANAGE)
    except authz.PermissionDeniedError as exc:
        assert exc.permission == authz.Permission.RESOURCE_MANAGE.value
        assert exc.error_code == 'permission_denied'
    else:
        raise AssertionError('PermissionDeniedError was not raised')


def test_execution_context_preserves_workspace_and_generation():
    from langbot.pkg.api.http.context import ExecutionContext

    ctx = _context(authz.WorkspaceRole.DEVELOPER)
    execution = ExecutionContext.from_request(ctx, bot_uuid='bot-test', pipeline_uuid='pipeline-test')

    assert execution.instance_uuid == 'instance-test'
    assert execution.workspace_uuid == 'workspace-test'
    assert execution.placement_generation == 1
    assert execution.bot_uuid == 'bot-test'
    assert execution.pipeline_uuid == 'pipeline-test'
    assert execution.trigger_principal == ctx.principal
