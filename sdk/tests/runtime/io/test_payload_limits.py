import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.errors import ActionCallError
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.handler import Handler, MAX_STREAM_FRAME_BYTES
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.connections.stdio import StdioConnection
from tests.helpers.protocol import ProtocolConnection


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["websocket", "stdio"])
async def test_inline_attachment_limit_reports_remedy_without_sending(transport):
    stream = SimpleNamespace(send=AsyncMock(), close=AsyncMock(), write=Mock())
    connection = (
        WebSocketConnection(stream)
        if transport == "websocket"
        else StdioConnection(None, stream)
    )
    handler = Handler(connection)
    payload = base64.b64encode(b"x" * (12 * 1024 * 1024)).decode("ascii")
    with pytest.raises(ActionCallError, match="16777216.*reference"):
        await handler.call_action(
            CommonAction.PING, {"image": {"base64": payload}}, timeout=0.01
        )
    stream.send.assert_not_awaited()
    stream.close.assert_not_awaited()
    stream.write.assert_not_called()
    assert not handler.resp_waiters


@pytest.mark.asyncio
async def test_stream_frame_limit_reports_distinct_budget_and_remedy():
    connection = ProtocolConnection()
    handler = Handler(connection)
    response = ActionResponse.success({"text": "x" * MAX_STREAM_FRAME_BYTES})
    response.stream_index = 0
    with pytest.raises(ActionCallError, match="1048576.*smaller chunks"):
        await handler._send_message(response)
    assert not connection.sent
    assert not connection.closed
    await handler._send_message(ActionResponse.success({"ok": True}))
    assert len(connection.sent) == 1
