from __future__ import annotations

import pytest

from langbot_plugin.api.entities.builtin.command.context import (
    CommandReturn,
    ExecuteContext,
)
from langbot_plugin.api.entities.builtin.command.errors import (
    CommandError,
    CommandNotFoundError,
    CommandOperationError,
    CommandPrivilegeError,
    ParamNotEnoughError,
)
from langbot_plugin.api.entities.builtin.provider.session import (
    LauncherTypes,
    Session,
)


def _session() -> Session:
    return Session(
        launcher_type=LauncherTypes.PERSON,
        launcher_id="launcher",
        sender_id="sender",
    )


def test_command_return_serializes_command_error_to_message():
    ret = CommandReturn(error=CommandError(message="failed"))

    assert ret.error.message == "failed"
    assert ret.model_dump(mode="json", by_alias=True)["error"] == "failed"


def test_command_return_validates_str_error_without_attribute_error():
    # Validating serialized dict with error as string
    ret1 = CommandReturn.model_validate({"error": "failed"})
    assert isinstance(ret1.error, CommandError)
    assert ret1.error.message == "failed"

    # Direct string assignment
    ret2 = CommandReturn(error="direct error string")
    assert isinstance(ret2.error, CommandError)
    assert ret2.error.message == "direct error string"

    # Dict error assignment
    ret3 = CommandReturn.model_validate({"error": {"message": "dict error"}})
    assert isinstance(ret3.error, CommandError)
    assert ret3.error.message == "dict error"


def test_execute_context_shift_advances_current_command_and_params():
    context = ExecuteContext(
        query_id=1,
        session=_session(),
        command_text="plugin on demo",
        full_command_text="/plugin on demo",
        command="plugin",
        crt_command="plugin",
        params=["on", "demo"],
        crt_params=["on", "demo"],
        privilege=0,
    )

    assert context.shift() is context
    assert context.crt_command == "on"
    assert context.crt_params == ["demo"]

    context.shift()
    assert context.crt_command == "demo"
    assert context.crt_params == []

    context.shift()
    assert context.crt_command == ""
    assert context.crt_params == []


def test_execute_context_propagates_workspace_scope_to_session():
    context = ExecuteContext(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=2,
        query_id=1,
        session=_session(),
        command_text="plugin on demo",
        full_command_text="/plugin on demo",
        command="plugin",
        crt_command="plugin",
        params=["on", "demo"],
        crt_params=["on", "demo"],
        privilege=0,
    )

    assert context.session.instance_uuid == "instance-1"
    assert context.session.workspace_uuid == "workspace-a"
    assert context.session.placement_generation == 2


def test_command_not_found_error_default_message_should_be_constructible():
    assert str(CommandNotFoundError()) == "未知命令: "


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (CommandNotFoundError("demo"), "未知命令: demo"),
        (CommandPrivilegeError("demo"), "权限不足: demo"),
        (ParamNotEnoughError("demo"), "参数不足: demo"),
        (CommandOperationError("demo"), "操作失败: demo"),
    ],
)
def test_command_errors_prefix_user_visible_message(error, expected):
    assert str(error) == expected
