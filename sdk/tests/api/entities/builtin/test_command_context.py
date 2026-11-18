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


def _context(**kwargs) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=_session(),
        command_text="draw cat",
        full_command_text="/draw cat",
        command="draw",
        crt_command="draw",
        params=["cat"],
        crt_params=["cat"],
        privilege=1,
        **kwargs,
    )


def test_execute_context_config_defaults_to_empty_mapping():
    context = _context()

    assert context.config == {}
    assert context.model_dump(mode="json")["config"] == {}


def test_execute_context_config_round_trips_over_the_wire():
    context = _context(config={"style": "anime", "count": 2})

    restored = ExecuteContext.model_validate(context.model_dump(mode="json"))

    assert restored.config == {"style": "anime", "count": 2}


def test_execute_context_accepts_payloads_from_hosts_without_config():
    payload = _context().model_dump(mode="json")
    payload.pop("config")

    assert ExecuteContext.model_validate(payload).config == {}


def test_command_plugin_config_remains_independent_of_instance_config():
    from types import SimpleNamespace
    from langbot_plugin.api.definition.components.command.command import Command

    component = Command()
    component.plugin = SimpleNamespace(get_config=lambda: {"style": "plugin"})
    context = _context(config={"style": "instance"})
    assert component.get_plugin_config() == {"style": "plugin"}
    assert context.config == {"style": "instance"}
