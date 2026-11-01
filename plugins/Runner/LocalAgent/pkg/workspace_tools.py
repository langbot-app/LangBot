"""Workspace Application API tools and progressive disclosure for LocalAgent."""

from __future__ import annotations

import collections.abc
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool

from pkg.config import (
    DEFAULT_MAX_TOOL_RESULT_CHARS,
    get_workspace_direct_threshold,
)

logger = logging.getLogger(__name__)

# Default domain metadata for LangBot Application API
DOMAINS_METADATA: dict[str, dict[str, Any]] = {
    "monitoring": {
        "label": {"zh_Hans": "仪表盘", "en_US": "Monitoring"},
        "summary": "Inspect system metrics, service health, runtime alerts, and statistics.",
    },
    "stats": {
        "label": {"zh_Hans": "统计", "en_US": "Statistics"},
        "summary": "Basic usage statistics and activity summaries.",
    },
    "bot": {
        "label": {"zh_Hans": "机器人", "en_US": "Bot"},
        "summary": "Manage chat bots, configure message routing rules, and send outbound messages.",
    },
    "adapter": {
        "label": {"zh_Hans": "适配器", "en_US": "Adapter"},
        "summary": "Inspect IM platforms and chat network adapters available in the workspace.",
    },
    "agent": {
        "label": {"zh_Hans": "智能体", "en_US": "Agent"},
        "summary": "Create and manage autonomous AI agents, inspect execution traces, and debug agent runs.",
    },
    "pipeline": {
        "label": {"zh_Hans": "流水线", "en_US": "Pipeline"},
        "summary": "Create, configure, and manage message processing pipelines and node topologies.",
    },
    "knowledge": {
        "label": {"zh_Hans": "知识库", "en_US": "Knowledge Base"},
        "summary": "Manage knowledge bases, index documents, and retrieve relevant knowledge chunks.",
    },
    "plugin": {
        "label": {"zh_Hans": "插件", "en_US": "Plugin"},
        "summary": "Discover, install, configure, and inspect LangBot plugins and component manifests.",
    },
    "mcp": {
        "label": {"zh_Hans": "MCP 服务", "en_US": "MCP"},
        "summary": "Manage Model Context Protocol (MCP) server connections and access their resources.",
    },
    "skill": {
        "label": {"zh_Hans": "技能", "en_US": "Skill"},
        "summary": "Author, inspect, and update agent skills, specialized instructions, and prompts.",
    },
    "extension": {
        "label": {"zh_Hans": "扩展", "en_US": "Extension"},
        "summary": "List and inspect available workspace extensions and capabilities.",
    },
    "tool": {
        "label": {"zh_Hans": "工具", "en_US": "Tool"},
        "summary": "Manage workspace custom tools, functions, and external integrations.",
    },
    "model": {
        "label": {"zh_Hans": "模型", "en_US": "Model"},
        "summary": "Configure language models, fallback strategies, credentials, and parameters.",
    },
    "provider": {
        "label": {"zh_Hans": "供应商", "en_US": "Provider"},
        "summary": "Manage upstream AI model providers, endpoints, and credentials.",
    },
    "requester": {
        "label": {"zh_Hans": "请求器", "en_US": "Requester"},
        "summary": "Configure upstream HTTP clients, proxies, retry policies, and timeouts.",
    },
}

PROGRESSIVE_GUIDANCE = (
    "For workspace capabilities, follow progressive disclosure: first use `workspace_search` to discover operations, "
    "then inspect schemas with `workspace_describe`, and finally execute with `workspace_call` "
    "(先 search → describe → call)."
)

TRUNCATION_HINT = (
    "Result exceeded maximum tool result characters limit and was truncated. "
    "Use pagination or filtering parameters to narrow the results. "
    "(结果超过长度上限已截断，请使用分页或过滤参数缩小结果。)"
)


@dataclass(frozen=True)
class NormalizedOperation:
    """Normalized representation of an authorized workspace operation."""

    id: str
    domain: str
    label: dict[str, str]
    summary: str
    description: str
    risk: str  # 'read' | 'write' | 'dangerous'
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


def operation_id_to_tool_name(operation_id: str) -> str:
    """Convert operation ID to direct tool name: 'bot.list' -> 'ws_bot__list'.

    Tool name starts with 'ws_', replaces '.' with '__', and length is bounded <= 64.
    If length exceeds 64 chars, a stable 8-char SHA256 suffix is appended to prevent collision.
    """
    cleaned = operation_id.replace(".", "__")
    tool_name = f"ws_{cleaned}"
    if len(tool_name) > 64:
        digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:8]
        tool_name = f"{tool_name[:55]}_{digest}"
    return tool_name


def tool_name_to_operation_id(tool_name: str) -> str:
    """Reverse tool name back to operation ID: 'ws_bot__list' -> 'bot.list'."""
    if tool_name.startswith("ws_"):
        return tool_name[3:].replace("__", ".")
    return tool_name.replace("__", ".")


def normalize_operation(op: Any) -> NormalizedOperation:
    """Normalize operation from dict or SDK WorkspaceOperationResource."""
    if isinstance(op, Mapping):
        op_id = str(op.get("id") or "")
        domain = str(op.get("domain") or (op_id.split(".")[0] if "." in op_id else ""))
        label = op.get("label") or {}
        summary = str(op.get("summary") or "")
        description = str(op.get("description") or summary or "")
        risk = str(op.get("risk") or "read")
        input_schema = op.get("input_schema") or {}
        output_schema = op.get("output_schema") or {}
    else:
        op_id = str(getattr(op, "id", "") or "")
        domain = str(getattr(op, "domain", None) or (op_id.split(".")[0] if "." in op_id else ""))
        label = getattr(op, "label", None) or {}
        summary = str(getattr(op, "summary", None) or "")
        description = str(getattr(op, "description", None) or summary or "")
        risk = str(getattr(op, "risk", None) or "read")
        input_schema = getattr(op, "input_schema", None) or {}
        output_schema = getattr(op, "output_schema", None) or {}

    if not isinstance(label, dict):
        label = {}
    if not isinstance(input_schema, dict):
        input_schema = {}
    if not isinstance(output_schema, dict):
        output_schema = {}

    return NormalizedOperation(
        id=op_id,
        domain=domain,
        label=label,
        summary=summary,
        description=description,
        risk=risk,
        input_schema=input_schema,
        output_schema=output_schema,
    )


def format_domains_overview(domain_list: list[dict[str, Any]], max_chars: int = 1500) -> str:
    """Format domain overview with a strict character budget (<= 1500 chars)."""
    if not domain_list:
        return ""
    header = "Available workspace capability domains:\n"
    lines: list[str] = []
    current_len = len(header)
    for d in domain_list:
        name = d.get("domain", "")
        label = d.get("label") or {}
        zh = label.get("zh_Hans") or label.get("en_US") or name
        count = d.get("count", 0)
        summary = d.get("summary", "")
        line = f"- {name} ({zh}, {count} ops): {summary}" if summary else f"- {name} ({zh}, {count} ops)"
        if current_len + len(line) + 1 > max_chars:
            prefix = f"- {name} ({zh}, {count} ops): "
            available = max_chars - current_len - len(prefix) - 4
            if available > 10:
                lines.append(f"{prefix}{summary[:available]}...")
            break
        lines.append(line)
        current_len += len(line) + 1
    return (header + "\n".join(lines))[:max_chars]


def build_domains_from_operations(operations: list[NormalizedOperation]) -> list[dict[str, Any]]:
    """Build domain list summarizing operation counts and descriptions."""
    domain_counts: dict[str, int] = {}
    for op in operations:
        d = op.domain or (op.id.split(".")[0] if "." in op.id else "other")
        domain_counts[d] = domain_counts.get(d, 0) + 1

    result = []
    for d, count in sorted(domain_counts.items()):
        meta = DOMAINS_METADATA.get(d, {})
        label = meta.get("label", {"zh_Hans": d, "en_US": d.capitalize()})
        summary = meta.get("summary", "")
        result.append(
            {
                "domain": d,
                "label": label,
                "summary": summary,
                "count": count,
            }
        )
    return result


class WorkspaceToolsManager:
    """Manages workspace operations discovery, presentation (direct vs progressive),
    system prompt injection, conflict resolution, and execution.
    """

    def __init__(
        self,
        operations: list[NormalizedOperation],
        domains: list[dict[str, Any]],
        mode: str | None,  # "direct", "progressive", or None
        tools: list[LLMTool],
        tool_name_to_op_id: dict[str, str] | None = None,
    ):
        self.operations = operations
        self.operations_by_id = {op.id: op for op in operations}
        self.domains = domains
        self.mode = mode
        self.tools = tools
        self._tool_names = {tool.name for tool in tools}
        self._tool_name_to_op_id = dict(tool_name_to_op_id or {})

    @classmethod
    async def discover(
        cls,
        api: Any,
        ctx: Any,
    ) -> WorkspaceToolsManager:
        """Discover authorized workspace operations and build the manager.

        Rule 1:
        优先读取本次运行资源中的 workspace_operations，没有时调用 api.workspace.list()。
        列表为空、或者 SDK / Core 不支持时，不注册任何相关工具，原有行为保持不变。
        """
        raw_ops: Any = None
        resources = getattr(ctx, "resources", None)
        if resources is not None:
            raw_ops = getattr(resources, "workspace_operations", None)

        domains: list[dict[str, Any]] = []
        normalized_ops: list[NormalizedOperation] = []

        if raw_ops:
            normalized_ops = [normalize_operation(op) for op in raw_ops if op]
            normalized_ops = [op for op in normalized_ops if op.id]
            domains = build_domains_from_operations(normalized_ops)
        else:
            # Fallback to api.workspace.list()
            workspace_proxy = getattr(api, "workspace", None)
            if workspace_proxy is not None and callable(getattr(workspace_proxy, "list", None)):
                try:
                    res = await workspace_proxy.list()
                    if isinstance(res, dict):
                        ops_list = res.get("operations") or []
                        normalized_ops = [normalize_operation(op) for op in ops_list if op]
                        normalized_ops = [op for op in normalized_ops if op.id]
                        domains = res.get("domains") or []
                        if not domains and normalized_ops:
                            domains = build_domains_from_operations(normalized_ops)
                except Exception as e:
                    logger.warning("Failed to list workspace operations via api.workspace.list(): %s", e)
                    normalized_ops = []
                    domains = []

        if not normalized_ops:
            return cls(operations=[], domains=[], mode=None, tools=[])

        config = getattr(ctx, "config", None) if isinstance(getattr(ctx, "config", None), dict) else {}
        threshold = get_workspace_direct_threshold(config)

        tool_name_map: dict[str, str] = {}
        if len(normalized_ops) <= threshold:
            mode = "direct"
            tools, tool_name_map = cls._build_direct_tools(normalized_ops)
        else:
            mode = "progressive"
            tools = cls._build_progressive_tools()

        return cls(
            operations=normalized_ops,
            domains=domains,
            mode=mode,
            tools=tools,
            tool_name_to_op_id=tool_name_map,
        )

    @staticmethod
    def _build_direct_tools(
        operations: list[NormalizedOperation],
    ) -> tuple[list[LLMTool], dict[str, str]]:
        """Build direct tools: ws_<op_id with . replaced by __>."""

        async def _placeholder(**kwargs: Any) -> Any:
            return kwargs

        tools: list[LLMTool] = []
        name_map: dict[str, str] = {}
        for op in operations:
            tool_name = operation_id_to_tool_name(op.id)
            name_map[tool_name] = op.id
            desc = op.description or op.summary or f"Workspace operation {op.id}"
            params = (
                op.input_schema
                if isinstance(op.input_schema, dict) and op.input_schema
                else {
                    "type": "object",
                    "properties": {},
                }
            )
            tools.append(
                LLMTool(
                    name=tool_name,
                    human_desc=desc,
                    description=desc,
                    parameters=params,
                    func=_placeholder,
                )
            )
        return tools, name_map

    @staticmethod
    def _build_progressive_tools() -> list[LLMTool]:
        """Build progressive disclosure meta tools: workspace_search, workspace_describe, workspace_call."""

        async def _placeholder(**kwargs: Any) -> Any:
            return kwargs

        search_tool = LLMTool(
            name="workspace_search",
            human_desc="Search authorized workspace operations by keyword or domain filter",
            description=(
                "Search authorized workspace operations by keyword or domain filter. "
                "Returns a list of matching operations with id, summary, and risk level."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Optional keyword to match against operation ID, summary, description, domain, or label."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Optional domain filter (e.g. 'bot', 'pipeline', 'monitoring', 'knowledge', 'model')."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (at most 10, default 10).",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
            },
            func=_placeholder,
        )

        describe_tool = LLMTool(
            name="workspace_describe",
            human_desc="Get schema and documentation for an authorized workspace operation",
            description="Get documentation, risk level, and JSON input schema for an authorized workspace operation.",
            parameters={
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "Exact operation ID to inspect.",
                    },
                },
                "required": ["operation_id"],
            },
            func=_placeholder,
        )

        call_tool = LLMTool(
            name="workspace_call",
            human_desc="Execute an authorized workspace operation",
            description="Execute an authorized workspace operation with input arguments matching its schema.",
            parameters={
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "Exact operation ID to execute.",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Input arguments matching the operation schema.",
                        "default": {},
                    },
                },
                "required": ["operation_id"],
            },
            func=_placeholder,
        )

        return [search_tool, describe_tool, call_tool]

    def resolve_conflicts(self, existing_tool_names: collections.abc.Set[str]) -> None:
        """Resolve conflicts with host tools, platform tools, or MCP tools.

        Rule: 工具名不能和宿主工具、平台工具、MCP 工具冲突，冲突时以原有工具为准，并记录 warning。
        """
        filtered_tools: list[LLMTool] = []
        for tool in self.tools:
            if tool.name in existing_tool_names:
                logger.warning(
                    "Workspace tool '%s' conflicts with existing tool; keeping existing tool",
                    tool.name,
                )
            else:
                filtered_tools.append(tool)
        self.tools = filtered_tools
        self._tool_names = {t.name for t in filtered_tools}

    def build_system_message(self) -> Message | None:
        """Build system prompt message for progressive mode.

        Rule: 渐进模式下，把领域概览（来自 domains，≤ 1500 字符）和“先 search → describe → call”
        的使用说明加进 LocalAgent 的系统提示。
        """
        if self.mode != "progressive" or not self.operations:
            return None

        overview = format_domains_overview(self.domains, max_chars=1500)
        if overview:
            content = f"{PROGRESSIVE_GUIDANCE}\n\n{overview}"
        else:
            content = PROGRESSIVE_GUIDANCE

        return Message(role="system", content=content)

    def is_workspace_tool(self, tool_name: str) -> bool:
        """Check if tool name is handled by this workspace manager."""
        return tool_name in self._tool_names

    def execute_search(
        self,
        query: str | None = None,
        domain: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search operations matching query and/or domain filter."""
        ops = list(self.operations)
        if domain:
            d_lower = str(domain).strip().lower()
            ops = [op for op in ops if op.domain.lower() == d_lower]

        if query:
            q = str(query).strip().lower()

            def _matches(op: NormalizedOperation) -> bool:
                if q in op.id.lower():
                    return True
                if op.summary and q in op.summary.lower():
                    return True
                if op.description and q in op.description.lower():
                    return True
                if op.domain and q in op.domain.lower():
                    return True
                if op.label:
                    for val in op.label.values():
                        if q in str(val).lower():
                            return True
                return False

            ops = [op for op in ops if _matches(op)]

        try:
            lim = max(1, min(int(limit), 10))
        except (ValueError, TypeError):
            lim = 10

        return [{"id": op.id, "summary": op.summary, "risk": op.risk} for op in ops[:lim]]

    def execute_describe(
        self,
        operation_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Describe operation documentation, risk, and input schema."""
        op = self.operations_by_id.get(operation_id)
        if op is None:
            return {"error": f"Operation '{operation_id}' not found or not authorized"}
        return {
            "id": op.id,
            "description": op.description,
            "risk": op.risk,
            "input_schema": op.input_schema,
        }

    async def execute(
        self,
        api: Any,
        tool_name: str,
        parameters: dict[str, Any],
        max_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
    ) -> Any:
        """Execute a workspace tool call."""
        if self.mode == "progressive":
            if tool_name == "workspace_search":
                res = self.execute_search(**parameters)
                return self._truncate_if_needed(res, max_result_chars)
            elif tool_name == "workspace_describe":
                op_id = parameters.get("operation_id", "")
                res = self.execute_describe(operation_id=op_id)
                return self._truncate_if_needed(res, max_result_chars)
            elif tool_name == "workspace_call":
                op_id = parameters.get("operation_id", "")
                raw_args = parameters.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        parsed = json.loads(raw_args)
                        if isinstance(parsed, dict):
                            raw_args = parsed
                    except Exception:
                        pass
                if not isinstance(raw_args, dict):
                    raw_args = {k: v for k, v in parameters.items() if k != "operation_id"}

                return await self._call_operation(
                    api=api,
                    operation_id=op_id,
                    arguments=raw_args,
                    max_result_chars=max_result_chars,
                )
            else:
                return {"error": f"Unknown workspace tool '{tool_name}'"}
        elif self.mode == "direct":
            op_id = self._tool_name_to_op_id.get(tool_name) or tool_name_to_operation_id(tool_name)
            return await self._call_operation(
                api=api,
                operation_id=op_id,
                arguments=parameters,
                max_result_chars=max_result_chars,
            )
        else:
            return {"error": f"Workspace tools not active for '{tool_name}'"}

    async def _call_operation(
        self,
        api: Any,
        operation_id: str,
        arguments: dict[str, Any],
        max_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
    ) -> dict[str, Any]:
        """Execute operation via api.workspace.call, enforce authorization and truncation."""
        if operation_id not in self.operations_by_id:
            return {
                "ok": False,
                "error": {
                    "code": "not_authorized",
                    "message": f"Operation '{operation_id}' is not authorized",
                },
            }

        # Guard against reserved keyword collision in SDK WorkspaceOperationsProxy.call(operation_id, _timeout, **arguments)
        for reserved_key in ("operation_id", "_timeout"):
            if reserved_key in arguments:
                return {
                    "ok": False,
                    "error": {
                        "code": "invalid_argument",
                        "message": (
                            f"Argument conflict: '{reserved_key}' is a reserved parameter in workspace.call. "
                            "Nested parameters should be used or this parameter should be renamed."
                        ),
                    },
                }

        workspace_proxy = getattr(api, "workspace", None)
        if workspace_proxy is None or not callable(getattr(workspace_proxy, "call", None)):
            return {
                "ok": False,
                "error": {
                    "code": "unsupported",
                    "message": "Workspace operations not supported by host or SDK",
                },
            }

        try:
            res = await workspace_proxy.call(operation_id, **arguments)
        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "code": "execution_failed",
                    "message": str(exc),
                },
            }

        # Rule 3: ok: false 时，把错误原样返回给模型，不重试写操作。
        if isinstance(res, dict) and res.get("ok") is False:
            return res

        # Rule 3: 返回结果超过 LocalAgent 现有工具结果的长度上限时截断，返回中给出提示：用分页或过滤参数缩小结果。
        return self._truncate_if_needed(res, max_result_chars)

    @staticmethod
    def _truncate_if_needed(res: Any, max_result_chars: int) -> Any:
        serialized = json.dumps(res, ensure_ascii=False, default=str)
        if len(serialized) > max_result_chars:
            preview_budget = max(0, max_result_chars - 300)
            return {
                "ok": res.get("ok", True) if isinstance(res, dict) else True,
                "truncated": True,
                "preview": serialized[:preview_budget],
                "hint": TRUNCATION_HINT,
            }
        return res
