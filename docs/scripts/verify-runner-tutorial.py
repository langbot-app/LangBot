"""Execute the published tutorial with the matching 4.11 SDK installed.

Run: python scripts/verify-runner-tutorial.py
The tool API is mocked; real Host/runtime checks are a separate validation layer.
"""

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import yaml
from langbot_plugin.api.definition.components.runner import RunnerContext


ROOT = Path(__file__).resolve().parents[1]


def load_tutorial():
    examples = []
    for locale in ("zh", "en", "ja"):
        path = ROOT / locale / "plugin/dev/components/runner.mdx"
        source = path.read_text()
        python = re.findall(r"^```python\n(.*?)^```", source, re.M | re.S)
        manifests = [
            block
            for block in re.findall(r"^```yaml\n(.*?)^```", source, re.M | re.S)
            if "kind: Runner" in block
        ]
        python = [block for block in python if "class Welcome(Runner):" in block]
        assert len(python) == len(manifests) == 1, path
        examples.append((python[0], manifests[0]))
    assert examples[0] == examples[1] == examples[2], "Locale examples differ"
    code, manifest = examples[0]
    namespace = {}
    exec(compile(code, "runner.mdx", "exec"), namespace)
    manifest = yaml.safe_load(manifest)
    assert manifest["spec"]["events"] == ["group.member_joined", "message.received"]
    assert manifest["spec"]["capabilities"]["tool_calling"] is True
    assert manifest["spec"]["permissions"]["tools"] == ["detail", "call"]
    defaults = {field["name"]: field["default"] for field in manifest["spec"]["config"]}
    return namespace[manifest["execution"]["python"]["attr"]], defaults


async def main():
    component_class, defaults = load_tutorial()
    component = component_class()
    await component.initialize()
    cases = [
        (
            "join",
            {
                "type": "group.member_joined",
                "member": {"id": "alice", "nickname": "Alice"},
            },
            {},
            "Alice, Welcome aboard!",
        ),
        (
            "nickname-fallback",
            {"type": "group.member_joined", "member": {"id": "alice"}},
            {},
            "alice, Welcome aboard!",
        ),
        (
            "join-disabled",
            {"type": "group.member_joined"},
            {"reply_enabled": False},
            None,
        ),
        (
            "command-disabled",
            {
                "type": "message.received",
                "message_chain": [{"type": "Plain", "text": "/hello"}],
            },
            {"reply_enabled": False},
            None,
        ),
        (
            "ordinary-text",
            {
                "type": "message.received",
                "message_chain": [{"type": "Plain", "text": "hello"}],
            },
            {},
            None,
        ),
        ("empty-message", {"type": "message.received", "message_chain": []}, {}, None),
        (
            "image-only",
            {
                "type": "message.received",
                "message_chain": [
                    {"type": "Image", "url": "https://example.com/image.png"}
                ],
            },
            {},
            None,
        ),
    ]
    for chat_type in ("private", "group"):
        cases.append(
            (
                chat_type,
                {
                    "type": "message.received",
                    "chat_type": chat_type,
                    "message_chain": [{"type": "Plain", "text": " /hello "}],
                },
                {"greeting": "你好 🧩"},
                "你好 🧩",
            )
        )

    async def execute(name, data, config, reply, *, failure=False):
        api = SimpleNamespace(
            call_tool=AsyncMock(
                side_effect=RuntimeError("Delivery failed") if failure else None,
                return_value={"mock": True},
            )
        )
        component.get_run_api = Mock(return_value=api)
        context = RunnerContext.model_validate({
            "run_id": name, "trigger": {"type": data["type"]},
            "event": {"event_id": name, "event_type": data["type"], "source": "test", "data": data},
            "config": {**defaults, **config}, "input": {}, "delivery": {"surface": "test"}, "resources": {}, "runtime": {},
        })
        results = []
        try:
            async for result in component.invoke(context):
                results.append(result)
        except RuntimeError as exc:
            assert failure and str(exc) == "Delivery failed"
        else:
            assert not failure, "Delivery failure was swallowed"
        assert sum(r.type == "run.completed" for r in results) == int(not failure)
        assert all(r.run_id == name for r in results)
        if reply is None:
            api.call_tool.assert_not_called()
        else:
            api.call_tool.assert_awaited_once_with("event_reply", {"text": reply})
            started = [
                r.data["tool_call_id"] for r in results if r.type == "tool.call.started"
            ]
            completed = [
                r.data["tool_call_id"]
                for r in results
                if r.type == "tool.call.completed"
            ]
            assert len(started) == 1 and started == completed
        if failure:
            assert any(r.type == "processor.log" for r in results)
            assert any(r.data.get("error") == "Delivery failed" for r in results)
        print(f"PASS {name}")

    for case in cases:
        await execute(*case)
    await execute("delivery-failure", cases[0][1], {}, cases[0][3], failure=True)
    print(
        "All 10 tutorial cases passed; Chinese, English and Japanese code is identical."
    )


if __name__ == "__main__":
    asyncio.run(main())
