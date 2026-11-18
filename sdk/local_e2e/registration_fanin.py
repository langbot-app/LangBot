from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace


from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.bounded_executor import configure_bounded_default_executor
from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from langbot_plugin.runtime.io.connections.stdio import StdioConnection


class Manager:
    def __init__(self) -> None:
        self.registered = asyncio.Event()
        self.calls = 0
        self.plugins = []

    async def register_plugin(self, *_args, **_kwargs) -> None:
        self.calls += 1
        self.registered.set()

    async def remove_plugin_handler(self, _handler) -> None:
        return None


async def child() -> None:
    if os.environ.get("REGISTRATION_FANIN_STDOUT_NOISE") == "1":
        sys.stdout.write("plugin-import-noise\n")
        sys.stdout.flush()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_running_loop().connect_read_pipe(
        lambda: protocol, sys.stdin.buffer
    )
    transport, writer_protocol = await asyncio.get_running_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(
        transport, writer_protocol, reader, asyncio.get_running_loop()
    )
    conn = StdioConnection(reader, writer)
    payload = {
        "plugin_container": {
            "manifest": {
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "first-frame",
                    "version": "1.0.0",
                    "label": {"en_US": "First Frame"},
                    "description": {"en_US": "x" * 100_000},
                },
                "spec": {"components": {}},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
            "status": "mounted",
        },
        "prod_mode": True,
        "plugin_debug_key": "",
        "registration_capability": "x" * 40,
    }
    # Use the real protocol encoder/order. The action is intentionally not assumed
    # to occur in the first 256 bytes.
    from langbot_plugin.entities.io.req import ActionRequest

    req = ActionRequest.make_request(
        1, PluginToRuntimeAction.REGISTER_PLUGIN.value, payload, None
    )
    await conn.send(json.dumps(req.model_dump()))
    await asyncio.sleep(10)


async def parent() -> None:
    loop = asyncio.get_running_loop()
    executor = configure_bounded_default_executor(
        loop, max_workers=6, max_pending=0, max_inflight_per_scope=3
    )
    release = threading.Event()
    started = [threading.Event() for _ in range(6)]
    blockers = [
        executor.submit(lambda e=e: (e.set(), release.wait(30)), e)[0]
        if False
        else None
        for e in []
    ]
    blockers = []
    for event in started:

        def block(e=event):
            e.set()
            release.wait(30)

        blockers.append(executor.submit(block))
    assert all(event.wait(2) for event in started)

    procs = []
    tasks = []
    managers = []
    try:
        for _ in range(6):
            child_env = {
                **os.environ,
                "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
            }
            if args.noise:
                child_env["REGISTRATION_FANIN_STDOUT_NOISE"] = "1"
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                __file__,
                "--child",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=child_env,
            )
            assert process.stdout is not None and process.stdin is not None
            manager = Manager()
            context = SimpleNamespace(
                plugin_mgr=manager,
                control_handler=SimpleNamespace(),
                runtime_profile="shared",
                workspace_binding=None,
                workspace_debug_tokens=SimpleNamespace(
                    binding_for_token=lambda _token: None
                ),
                validate_plugin_registration_capability=lambda *_args: ActionContext(
                    instance_uuid="instance-1",
                    workspace_uuid=None,
                    placement_generation=1,
                ),
            )
            handler = PluginConnectionHandler(
                StdioConnection(
                    process.stdout,
                    process.stdin,
                    process=process,
                    reserve_first_message_decode=True,
                    reserve_first_message_send=True,
                ),
                context,
                certified_shared_stdio=True,
            )
            # Isolate codec admission from manager ownership details.
            handler.actions[PluginToRuntimeAction.REGISTER_PLUGIN.value] = (
                lambda _data, manager=manager: _register_response(manager)
            )
            managers.append(manager)
            procs.append(process)
            tasks.append(asyncio.create_task(handler.run()))

        registered = await asyncio.wait_for(
            asyncio.gather(*(manager.registered.wait() for manager in managers)),
            timeout=5,
        )
        print(json.dumps({"registered": len(registered), "handlers": len(managers)}))
    finally:
        release.set()
        for process in procs:
            if process.returncode is None:
                process.terminate()
        await asyncio.gather(
            *(process.wait() for process in procs), return_exceptions=True
        )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        executor.shutdown()


def _register_response(manager: Manager):
    from langbot_plugin.entities.io.resp import ActionResponse

    manager.calls += 1
    manager.registered.set()
    return ActionResponse.success({})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--noise", action="store_true")
    args = parser.parse_args()
    asyncio.run(child() if args.child else parent())
