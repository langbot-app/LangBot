"""Shared listener and connection tasks must not inherit an invocation Context.

The asset gateway listener is shared by every installation of the plugin, while
an invocation Context carries one installation's configuration and revocable
authority.  ``asyncio`` copies the Context that is current when a callback is
scheduled, so a listener created inside the registering invocation would pin
that invocation's state to the shared listener.  These tests assert the listener
and its connection tasks run in a tenant-free Context.
"""

from __future__ import annotations

import asyncio
import contextvars
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from pkg import asset_gateway  # noqa: E402

INVOCATION_MARKER: contextvars.ContextVar[str | None] = contextvars.ContextVar("invocation_marker", default=None)


def test_shared_listener_and_connection_tasks_are_tenant_free():
    accepted: list[str | None] = []
    served: list[str | None] = []

    async def scenario() -> None:
        async def handle(reader, writer) -> None:
            accepted.append(INVOCATION_MARKER.get())
            writer.close()

        # Stand in for the registering invocation: this state must not reach the
        # shared listener, its accept callbacks or its connection tasks.
        INVOCATION_MARKER.set("tenant-a")

        server = await asset_gateway._create_tenant_free_listener(handle, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            for _ in range(100):
                if accepted:
                    break
                await asyncio.sleep(0.02)
            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

        gateway = asset_gateway.Gateway(5.0)

        async def fake_serve(reader, writer) -> None:
            served.append(INVOCATION_MARKER.get())

        gateway.serve = fake_serve  # type: ignore[method-assign]
        gateway.connected(None, None)
        pending = tuple(gateway.tasks)
        await asyncio.gather(*pending, return_exceptions=True)

        assert INVOCATION_MARKER.get() == "tenant-a"

    asyncio.run(scenario())

    assert accepted == [None], "the shared listener's accept callback retained the invocation Context"
    assert served == [None], "the shared listener's connection task inherited the invocation Context"
