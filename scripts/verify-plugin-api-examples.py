"""Run the API documentation snippets with the installed SDK and a mock Host.

Usage: python scripts/verify-plugin-api-examples.py
This checks SDK calls and result shapes, not external platform delivery.
"""

from __future__ import annotations

import asyncio
import argparse
import ast
import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.errors import (
    AgentAPIError,
    AgentAPIException,
)
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.event_context import EventContextProxy
from langbot_plugin.api.proxies.execute_context import ExecuteContextProxy
from langbot_plugin.api.entities.builtin.provider.session import Session
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.api.entities.builtin.provider.message import Message

ROOT = Path(__file__).resolve().parents[1]


class Host:
    def __init__(self):
        self.calls = []
        self.closed_streams = 0

    async def call_action(self, action, data, timeout=15):
        name = action.value
        self.calls.append((name, data))
        responses = {
            "invoke_llm": {
                "message": {"role": "assistant", "content": "Hello!"},
                "usage": {"total_tokens": 8},
            },
            "invoke_rerank": {"results": [{"index": 0, "relevance_score": 0.9}]},
            "list_parsers": {
                "parsers": [{"plugin_author": "demo", "plugin_name": "Parser"}]
            },
            "invoke_parser": {"text": "guide", "sections": [], "metadata": {}},
            "vector_list": {
                "items": [{"id": "chunk", "document": "guide", "metadata": {}}],
                "total": 1,
            },
            "list_plugins_manifest": {"plugins": []},
            "list_commands": {"commands": []},
            "call_platform_api": {"result": {"id": "123456", "name": "Example"}},
            "call_tool": {"result": {"id": "alice"}},
            "reply_stream": {"result": {"ok": True, "mock": True}},
            "history_page": {
                "items": [],
                "has_more": not data.get("before_cursor"),
                "prev_cursor": "older",
                "next_cursor": None,
            },
            "reply_message": {},
            "set_query_var": {},
            "state_set": {"success": True},
            "state_get": {"value": "setup"},
        }
        if name not in responses:
            raise AssertionError(f"Unexpected Host action: {name}")
        return responses[name]

    async def call_action_generator(self, action, data, timeout=15):
        assert action.value == "invoke_llm_stream"
        self.calls.append((action.value, data))
        try:
            yield {"chunk": {"role": "assistant", "content": "Hello", "is_final": False}}
            yield {"chunk": {"role": "assistant", "content": "!", "is_final": True}}
            yield {"usage": {"total_tokens": 8}}
        finally:
            self.closed_streams += 1


def context():
    return RunnerContext.model_validate(
        {
            "run_id": "docs-run",
            "trigger": {"type": "user_message"},
            "event": {
                "event_id": "docs-event",
                "event_type": "message.received",
                "source": "test",
            },
            "input": {"content": "Hello"},
            "delivery": {"surface": "test"},
            "runtime": {},
            "resources": {
                "models": [{"model_id": "model"}],
                "tools": [
                    {"tool_name": "event_get_actor"},
                    {"tool_name": "event_reply"},
                ],
            },
            "context": {
                "available_apis": {
                    "history_page": True,
                    "state": True,
                    "reply_stream": True,
                }
            },
        }
    )


def snippets(locale, page):
    source = (ROOT / locale / f"plugin/dev/apis/{page}.mdx").read_text(encoding="utf-8")
    if page == "common":
        headings = {
            "zh": ("### 模型流式输出与用量", "## 其他资源 API"),
            "en": ("### Model streaming and usage", "## Additional resource APIs"),
            "ja": ("### モデルのストリーミングと使用量", "## その他のリソース API"),
        }[locale]
        start = source.index(headings[0])
        end = source.index("\n### ", start + len(headings[0]))
        source = source[start:end] + source[source.index(headings[1]) :]
    return re.findall(r"^```python\n(.*?)^```", source, re.M | re.S)


def verify_context_reference():
    source = (ROOT / "zh/plugin/dev/apis/agent-run.mdx").read_text(encoding="utf-8")
    query_methods = {
        "reply",
        "get_bot_uuid",
        "set_query_var",
        "get_query_var",
        "get_query_vars",
        "create_new_conversation",
        "list_pipeline_knowledge_bases",
        "retrieve_knowledge",
    }
    runner_methods = {
        name
        for name, value in RunnerContext.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    runner_methods.discard("model_post_init")

    for prefix in ("event_context", "context"):
        missing = sorted(
            name for name in query_methods if f"{prefix}.{name}(" not in source
        )
        assert not missing, f"{prefix} methods missing from context reference: {missing}"

    for name in ("prevent_default", "prevent_postorder"):
        assert f"event_context.{name}(" in source

    missing = sorted(name for name in runner_methods if f"ctx.{name}(" not in source)
    assert not missing, f"RunnerContext methods missing from context reference: {missing}"
    assert "`platform_event`" in source

    required_fields = {
        "instance_uuid",
        "workspace_uuid",
        "placement_generation",
        "query_id",
        "query_uuid",
        "eid",
        "event_name",
        "event",
        "is_prevent_default",
        "is_prevent_postorder",
        "session",
        "command_text",
        "full_command_text",
        "command",
        "crt_command",
        "params",
        "crt_params",
        "privilege",
        *RunnerContext.model_fields,
    }
    missing = sorted(name for name in required_fields if f"`{name}`" not in source)
    assert not missing, f"Context fields missing from context reference: {missing}"
    assert "spec.permissions" not in source
    assert "spec.capabilities" not in source


async def execute(block, namespace):
    # Examples are function bodies; signature reference blocks may include stubs.
    function = "async def example():\n" + "\n".join(
        "    " + line for line in block.splitlines()
    )
    tree = ast.parse(function)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = ast.unparse(node.func.value)
        cls = (
            LangBotAPIProxy
            if owner == "self.plugin"
            else EventContextProxy
            if owner == "event_context"
            else ExecuteContextProxy
            if owner == "context"
            else RunnerContext
            if owner == "ctx"
            else RunnerAPIProxy
            if owner == "api"
            else None
        )
        if cls is not None:
            signature = inspect.signature(getattr(cls, node.func.attr))
            signature.bind(
                None,
                *([None] * len(node.args)),
                **{kw.arg: None for kw in node.keywords},
            )
    exec(compile(tree, "plugin-api-doc-example", "exec"), namespace)
    await namespace["example"]()


async def main(pages):
    verify_context_reference()
    total = 0
    for page in pages:
        blocks = snippets("zh", page)
        for locale in ("en", "ja"):
            assert blocks == snippets(locale, page), f"{page}: {locale} code differs"
        for block in blocks:
            host = Host()
            ctx = context()
            api = RunnerAPIProxy(ctx, host)
            ctx._api = api
            ctx._results = asyncio.Queue()
            session = Session(launcher_type="group", launcher_id="docs-group", sender_id="docs-user")
            namespace = {
                "event_context": EventContextProxy.model_construct(
                    query_id=42,
                    event=SimpleNamespace(sender_id="docs-user"),
                    plugin_runtime_handler=host,
                ),
                "context": ExecuteContextProxy.model_construct(
                    query_id=43,
                    plugin_runtime_handler=host,
                    crt_params=["Hello!"],
                    session=session,
                ),
                "session": session,
                "Any": Any,
                "Message": Message,
                "api": api,
                "ctx": ctx,
                "self": SimpleNamespace(
                    plugin=LangBotAPIProxy(host), get_run_api=lambda _: api
                ),
                "model_uuid": "model",
                "rerank_model_uuid": "model",
                "collection_id": "collection",
                "storage_path": "files/guide.pdf",
                "bot_uuid": "bot",
                "print": lambda *args: None,
            }
            with bind_invocation(host, api):
                await execute(block, namespace)
            if page == "llm-requests":
                expected = 0 if "aclosing" in block else 1
                llm_calls = [data for name, data in host.calls if name.startswith("invoke_llm")]
                assert len(llm_calls) == 1
                assert llm_calls[0]["extra_args"]["request_policy"]["retries"] == expected
                if "aclosing" in block:
                    assert host.closed_streams == 1, "Early close did not reach the Host stream"
            for name, data in host.calls:
                if name in {"reply_message", "set_query_var"}:
                    expected_query = 42 if "event_context" in block else 43
                    assert data["query_id"] == expected_query
                    assert "run_id" not in data
            if "reply.update" in block:
                ops = [
                    data["operation"]
                    for name, data in host.calls
                    if name == "reply_stream"
                ]
                assert ops == ["update", "update", "finish"], ops
            if "older =" in block:
                pages = [data for name, data in host.calls if name == "history_page"]
                assert len(pages) == 2 and pages[1]["before_cursor"] == "older"
            if "except PermissionDeniedError" in block:
                # Exercise both documented error handlers with the real SDK proxy.
                api._allowed_tool_names = frozenset()
                await execute(block, namespace)
                ctx.log.assert_awaited()
                api._allowed_tool_names = frozenset({"event_get_actor"})
                host.call_action = AsyncMock(
                    side_effect=AgentAPIException(
                        AgentAPIError(
                            code="host.action_error", message="Failed", retryable=False
                        )
                    )
                )
                await execute(block, namespace)
                assert ctx.log.await_count == 2
            total += 1
    print(
        f"{total} API examples passed; all three locales have identical code. Host delivery is mocked."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--page", action="append",
        choices=("common", "agent-run", "platform", "llm-requests"),
        help="Verify selected pages (repeatable); defaults to all pages.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.page or ("common", "agent-run", "platform", "llm-requests")))
