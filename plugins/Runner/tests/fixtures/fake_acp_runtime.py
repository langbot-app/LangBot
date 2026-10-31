"""Unpaid local ACP protocol fixture; never launches a real provider."""

from __future__ import annotations

import json
import sys


def send(payload):
    print(json.dumps({"jsonrpc": "2.0", **payload}), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        continue
    if method == "initialize":
        result = {"protocolVersion": 1, "agentCapabilities": {"loadSession": False, "promptCapabilities": {}}}
    elif method == "session/new":
        result = {"sessionId": "fixture-acp-session"}
    elif method == "session/prompt":
        send(
            {
                "method": "session/update",
                "params": {
                    "sessionId": "fixture-acp-session",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "FIXTURE_OK"},
                    },
                },
            }
        )
        result = {"stopReason": "end_turn"}
    else:
        send({"id": request_id, "error": {"code": -32601, "message": f"Unexpected fixture method {method}"}})
        continue
    send({"id": request_id, "result": result})
