from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import websockets


CONTROL_URL = "ws://127.0.0.1:5410/control/ws"
PLUGIN_ID = ("Codex", "EBAEventProbe")


class RuntimeControlClient:
    def __init__(self, websocket):
        self.websocket = websocket
        self.seq = 0
        self.waiters: dict[int, asyncio.Future[dict[str, Any]]] = {}

    async def start_reader(self):
        async for message in self.websocket:
            payload = json.loads(message)
            if "action" in payload:
                await self._handle_runtime_action(payload)
            elif "code" in payload:
                seq_id = payload["seq_id"]
                waiter = self.waiters.pop(seq_id, None)
                if waiter and not waiter.done():
                    waiter.set_result(payload)

    async def _handle_runtime_action(self, payload: dict[str, Any]):
        action = payload["action"]

        if action == "initialize_plugin_settings":
            response_data: dict[str, Any] = {}
        elif action == "get_plugin_settings":
            response_data = {
                "enabled": True,
                "priority": 0,
                "plugin_config": {},
                "install_source": "debug",
                "install_info": {},
            }
        else:
            response_data = {}

        await self.websocket.send(
            json.dumps(
                {
                    "seq_id": payload["seq_id"],
                    "code": 0,
                    "message": "success",
                    "data": response_data,
                    "chunk_status": "continue",
                }
            )
        )

    async def call(
        self, action: str, data: dict[str, Any], timeout: float = 10.0
    ) -> dict[str, Any]:
        self.seq += 1
        seq_id = self.seq
        waiter: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self.waiters[seq_id] = waiter
        await self.websocket.send(
            json.dumps({"seq_id": seq_id, "action": action, "data": data})
        )
        response = await asyncio.wait_for(waiter, timeout)
        if response["code"] != 0:
            raise RuntimeError(response["message"])
        return response["data"]


def event_context(event_name: str, event: dict[str, Any], eid: int) -> dict[str, Any]:
    return {
        "query_id": 0,
        "eid": eid,
        "event_name": event_name,
        "event": {"event_name": event_name, **event},
        "is_prevent_default": False,
        "is_prevent_postorder": False,
    }


def probe_events() -> list[dict[str, Any]]:
    group = {"id": "group-1", "name": "Probe Group"}
    user = {"id": "user-1", "nickname": "Probe User", "is_bot": False}
    return [
        event_context(
            "MessageReceived",
            {
                "message_id": "msg-1",
                "message_chain": [{"type": "Plain", "text": "hello"}],
                "sender": user,
                "chat_type": "private",
                "chat_id": "user-1",
                "group": None,
            },
            1,
        ),
        event_context(
            "MessageEdited",
            {
                "message_id": "msg-2",
                "new_content": [{"type": "Plain", "text": "edited"}],
                "editor": user,
                "chat_type": "private",
                "chat_id": "user-1",
                "group": None,
            },
            2,
        ),
        event_context(
            "MessageReactionReceived",
            {
                "message_id": "msg-3",
                "user": user,
                "reaction": "👍",
                "is_add": True,
                "chat_type": "group",
                "chat_id": "group-1",
                "group": group,
            },
            3,
        ),
        event_context(
            "FeedbackReceived",
            {
                "feedback_id": "fb-1",
                "feedback_type": 2,
                "feedback_content": "not accurate",
                "inaccurate_reasons": ["wrong_answer"],
                "user_id": "user-1",
                "session_id": "person_user-1",
                "message_id": "msg-4",
                "stream_id": "stream-1",
            },
            4,
        ),
        event_context(
            "GroupMemberJoined",
            {"group": group, "member": user, "inviter": user, "join_type": "invite"},
            5,
        ),
        event_context(
            "GroupMemberLeft",
            {"group": group, "member": user, "is_kicked": True, "operator": user},
            6,
        ),
        event_context(
            "GroupMemberBanned",
            {"group": group, "member": user, "operator": user, "duration": 60},
            7,
        ),
        event_context(
            "BotInvitedToGroup",
            {"group": group, "inviter": user, "request_id": "req-1"},
            8,
        ),
        event_context("BotRemovedFromGroup", {"group": group, "operator": user}, 9),
        event_context(
            "BotMuted", {"group": group, "operator": user, "duration": 60}, 10
        ),
        event_context("BotUnmuted", {"group": group, "operator": user}, 11),
        event_context(
            "PlatformSpecificEventReceived",
            {
                "adapter_name": "telegram",
                "action": "callback_query",
                "data": {"data": "button"},
            },
            12,
        ),
    ]


async def wait_for_probe_plugin(client: RuntimeControlClient):
    for _ in range(30):
        plugins = await client.call("list_plugins", {})
        for plugin in plugins["plugins"]:
            metadata = plugin["manifest"]["manifest"]["metadata"]
            if (metadata["author"], metadata["name"]) == PLUGIN_ID:
                return
        await asyncio.sleep(1)
    raise TimeoutError("EBAEventProbe did not register with standalone runtime")


async def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("eba_event_probe.jsonl")
    if log_path.exists():
        log_path.unlink()

    async with websockets.connect(CONTROL_URL, open_timeout=10) as websocket:
        client = RuntimeControlClient(websocket)
        reader_task = asyncio.create_task(client.start_reader())
        try:
            await wait_for_probe_plugin(client)
            for event_ctx in probe_events():
                result = await client.call(
                    "emit_event",
                    {
                        "event_context": event_ctx,
                        "include_plugins": ["Codex/EBAEventProbe"],
                    },
                    timeout=20,
                )
                if not result["emitted_plugins"]:
                    raise RuntimeError(
                        f"Event was not emitted: {event_ctx['event_name']}"
                    )

            for _ in range(20):
                if log_path.exists():
                    lines = [
                        json.loads(line)
                        for line in log_path.read_text(encoding="utf-8").splitlines()
                    ]
                    if len(lines) >= len(probe_events()):
                        seen = [line["event_name"] for line in lines]
                        expected = [event["event_name"] for event in probe_events()]
                        if seen[-len(expected) :] == expected:
                            print(
                                json.dumps(
                                    {"ok": True, "events": seen[-len(expected) :]},
                                    ensure_ascii=False,
                                )
                            )
                            return 0
                await asyncio.sleep(0.5)

            raise TimeoutError("Probe plugin did not write all expected events")
        finally:
            reader_task.cancel()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
