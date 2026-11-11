"""Declarative Runner external tool registration."""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pydantic


@dataclasses.dataclass(frozen=True)
class AgentToolSpec:
    """Metadata used to expose a run-scoped Runner tool."""

    name: str
    description: str
    args_model: type[pydantic.BaseModel]
    read_only: bool = False

    def input_schema(self) -> dict[str, typing.Any]:
        return self.args_model.model_json_schema()

    def to_mcp_tool(self) -> dict[str, typing.Any]:
        tool: dict[str, typing.Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema(),
        }
        if self.read_only:
            tool["annotations"] = {"readOnlyHint": True}
        return tool


@dataclasses.dataclass(frozen=True)
class BoundAgentTool:
    spec: AgentToolSpec
    handler: typing.Callable[[pydantic.BaseModel], typing.Awaitable[typing.Any]]


def agent_tool(
    *,
    name: str,
    description: str,
    args_model: type[pydantic.BaseModel],
    read_only: bool = False,
) -> typing.Callable[
    [typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]
]:
    """Mark a method as safe to expose through external Runner adapters."""

    def decorator(
        func: typing.Callable[..., typing.Any],
    ) -> typing.Callable[..., typing.Any]:
        setattr(
            func,
            "__langbot_agent_tool__",
            AgentToolSpec(
                name=name,
                description=description,
                args_model=args_model,
                read_only=read_only,
            ),
        )
        return func

    return decorator


def _tool_spec(method: typing.Any) -> AgentToolSpec | None:
    spec = getattr(method, "__langbot_agent_tool__", None)
    if isinstance(spec, AgentToolSpec):
        return spec
    func = getattr(method, "__func__", None)
    spec = getattr(func, "__langbot_agent_tool__", None)
    if isinstance(spec, AgentToolSpec):
        return spec
    return None


def collect_agent_tools(obj: object) -> dict[str, BoundAgentTool]:
    """Collect explicitly annotated tools from an object instance."""

    tools: dict[str, BoundAgentTool] = {}
    for attr_name in dir(obj):
        method = getattr(obj, attr_name)
        spec = _tool_spec(method)
        if spec is None:
            continue
        if not callable(method):
            continue
        if not inspect.iscoroutinefunction(method):
            raise TypeError(f"Agent tool {spec.name} must be async")
        if spec.name in tools:
            raise ValueError(f"Duplicate Agent tool name: {spec.name}")
        tools[spec.name] = BoundAgentTool(spec=spec, handler=method)
    return tools
