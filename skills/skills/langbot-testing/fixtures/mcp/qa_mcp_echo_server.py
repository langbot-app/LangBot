from __future__ import annotations

import json
import sys
import typing

SERVER_INFO = {"name": "langbot-qa-stdio", "version": "0.1.0"}
TOOL_NAME = "qa_mcp_echo"


def _write_message(message: dict[str, typing.Any]) -> None:
    sys.stdout.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    sys.stdout.flush()


def _result(
    message_id: typing.Any, result: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: typing.Any, code: int, message: str) -> dict[str, typing.Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _tool_schema() -> dict[str, typing.Any]:
    return {
        "name": TOOL_NAME,
        "description": "Return a deterministic QA echo string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to include in the QA echo response.",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    }


def handle_message(message: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
    message_id = message.get("id")
    method = str(message.get("method") or "")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if message_id is None:
        return None

    if method == "initialize":
        return _result(
            message_id,
            {
                "protocolVersion": str(params.get("protocolVersion") or "2024-11-05"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "ping":
        return _result(message_id, {})

    if method == "tools/list":
        return _result(message_id, {"tools": [_tool_schema()]})

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        if name != TOOL_NAME:
            return _error(message_id, -32602, f"Unknown tool: {name}")
        text = str(arguments.get("text") or "")
        return _result(
            message_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": f"{TOOL_NAME}:{text}",
                    }
                ],
                "isError": False,
            },
        )

    return _error(message_id, -32601, f"Method not found: {method}")


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_message(_error(None, -32700, f"Parse error: {exc}"))
            continue
        if not isinstance(message, dict):
            _write_message(_error(None, -32600, "Invalid request"))
            continue
        response = handle_message(message)
        if response is not None:
            _write_message(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
