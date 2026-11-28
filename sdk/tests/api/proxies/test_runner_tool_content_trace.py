"""Model content returns intact while retained tool traces contain no inline bytes."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.api.proxies.runner.tracing import _TracedRunAPI


@pytest.mark.anyio
async def test_tool_content_list_is_valid_trace_output_and_binary_is_redacted():
    payload = "data:image/png;base64,cHJpdmF0ZS1ieXRlcw=="
    result = [
        {"type": "text", "text": "image metadata"},
        {"type": "image_base64", "image_base64": payload},
    ]
    queue = asyncio.Queue()
    api = _TracedRunAPI(
        SimpleNamespace(call_tool=AsyncMock(return_value=result)), "run-1", queue
    )
    returned = await api.call_tool("read", {"ref": "att-1"})
    assert returned is result and returned[1]["image_base64"] == payload
    started, completed = queue.get_nowait(), queue.get_nowait()
    assert (
        started.type.value == "tool.call.started"
        and completed.type.value == "tool.call.completed"
    )
    assert completed.data["result"]["value"][0]["text"] == "image metadata"
    assert completed.data["result"]["value"][1]["content_redacted"] is True
    assert payload not in json.dumps(completed.data)
