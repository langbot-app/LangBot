from langbot.pkg.workspace.policy import (
    CloudWorkspacePolicy,
    SingleWorkspacePolicy,
    open_core_workspace_policy,
)


def test_open_source_policy_is_single_workspace() -> None:
    policy = open_core_workspace_policy()

    assert policy.workspace_limit == 1
    assert policy.multi_workspace_enabled is False


def test_cloud_policy_is_not_exported_as_the_default_policy() -> None:
    # CloudWorkspacePolicy remains a contract for the future verified, closed
    # bootstrap.  Constructing it explicitly must not change the OSS default.
    assert CloudWorkspacePolicy().multi_workspace_enabled is True
    assert isinstance(open_core_workspace_policy(), SingleWorkspacePolicy)
