"""Real SDK outer ownership, real packaged workers; vendor replies are fixtures."""

import asyncio
import importlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_isolation import context, load


@pytest.mark.parametrize("name,mode", [("dashscope", "agent"), ("dashscope", "workflow"), ("tbox", "agent")])
@pytest.mark.parametrize("scenario", ["error", "early_close", "repeated_cancel", "success"])
def test_outer_runner_owns_vendor_until_reaped(name, mode, scenario, tmp_path, monkeypatch):
    with load(name) as (_, runner):
        client = importlib.import_module("pkg." + name + "_client")
        transport = importlib.import_module("pkg.vendor_process")
        actual_worker = Path(transport.__file__).with_name("vendor_worker.py")
        if scenario == "error":
            frame = {"status_code": 500, "message": "fixture"} if name == "dashscope" else {"type": "error"}
            body = f" yield {frame!r}\n time.sleep(60)\n"
        else:
            frame = (
                {"status_code": 200, "output": {"text": "x"}}
                if name == "dashscope"
                else {"type": "chunk", "payload": {"text": "x"}}
            )
            body = f" yield {frame!r}\n" if scenario == "success" else f" while True: yield {frame!r}\n"
        fixture = (
            "import runpy,socket,time\n"
            "def deny(*a,**kw): raise AssertionError('no live network')\n"
            "socket.create_connection=deny\n"
            "def provider(*a,**kw):\n" + body
        )
        fixture += (
            "from dashscope import Application\nApplication.call=provider\n"
            if name == "dashscope"
            else "from tboxsdk.tbox import TboxClient\nTboxClient.chat=provider\n"
        )
        worker = tmp_path / "vendor_fixture.py"
        worker.write_text(fixture + f"runpy.run_path({str(actual_worker)!r},run_name='__main__')\n")
        original = transport.vendor_stream
        monkeypatch.setattr(
            client, "vendor_stream", lambda payload, timeout: original(payload, timeout=timeout, worker=worker)
        )
        spawn = asyncio.create_subprocess_exec
        processes, directories = [], []

        async def run():
            entered, release = asyncio.Event(), asyncio.Event()

            async def record(*args, **kwargs):
                proc = await spawn(*args, **kwargs)
                processes.append(proc)
                directories.append(Path(kwargs["cwd"]))
                if scenario == "repeated_cancel":
                    read = proc.stdout.read

                    async def held_cleanup(n=-1):
                        # Transport uses readline for frames, read only when reaping.
                        entered.set()
                        await release.wait()
                        return await read(n)

                    monkeypatch.setattr(proc.stdout, "read", held_cleanup)
                return proc

            monkeypatch.setattr(asyncio, "create_subprocess_exec", record)
            ctx = context()
            ctx.config.update(
                {"api-key": "fixture", "app-id": "fixture", "app-type": mode, "streaming": True, "timeout": 5}
            )
            runner.get_run_api = lambda ctx: SimpleNamespace()
            gen = runner.invoke(ctx)
            closing = None

            def assert_reaped():
                assert processes
                for proc in processes:
                    assert proc.returncode is not None, "outer boundary returned before child reap"
                    with pytest.raises(ProcessLookupError):
                        os.kill(proc.pid, 0)
                assert all(not directory.exists() for directory in directories)

            try:
                if scenario in ("error", "success"):
                    results = []
                    async for result in gen:
                        results.append(result)
                        if result.type in ("run.failed", "run.completed"):
                            # Check when terminal is visible, not after extra event-loop time.
                            assert_reaped()
                    assert results[-1].type == ("run.failed" if scenario == "error" else "run.completed")
                else:
                    await anext(gen)
                    async with asyncio.timeout(5):
                        while not ctx._results.full():
                            await asyncio.sleep(0)
                    if scenario == "early_close":
                        await gen.aclose()
                    else:
                        closing = asyncio.create_task(gen.aclose())
                        await asyncio.wait_for(entered.wait(), 2)
                        for _ in range(3):
                            closing.cancel()
                            # Schedule a turn, not a time-based cleanup allowance.
                            await asyncio.sleep(0)
                            assert not closing.done(), "repeated cancellation released cleanup ownership"
                            assert ctx._api is not None
                            assert all(directory.exists() for directory in directories)
                        release.set()
                        await closing
                    assert_reaped()
                assert ctx._api is None
            finally:
                release.set()
                if closing is not None:
                    await asyncio.gather(closing, return_exceptions=True)
                await gen.aclose()
                # Failure-only teardown never shares the transport's pipe reader.
                for proc in processes:
                    if proc.returncode is None:
                        try:
                            proc.kill()
                        except ProcessLookupError:
                            pass
                    await proc.wait()

        asyncio.run(run())
