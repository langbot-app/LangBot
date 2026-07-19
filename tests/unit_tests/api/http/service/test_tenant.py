import pytest
import sqlalchemy

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.service.tenant import require_workspace_uuid, scope_statement


class _TenantRow:
    workspace_uuid = sqlalchemy.column('workspace_uuid')


def test_require_workspace_uuid_accepts_execution_context():
    context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
        trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
    )

    assert require_workspace_uuid(context) == 'workspace-test'


@pytest.mark.parametrize('context', [None, '', '   '])
def test_require_workspace_uuid_rejects_missing_context(context):
    with pytest.raises(WorkspaceRequiredError):
        require_workspace_uuid(context)


def test_scope_statement_adds_workspace_predicate():
    statement = scope_statement(sqlalchemy.select(_TenantRow.workspace_uuid), _TenantRow, 'workspace-test')

    assert 'workspace_uuid = :workspace_uuid_1' in str(statement)
    assert statement.compile().params == {'workspace_uuid_1': 'workspace-test'}
