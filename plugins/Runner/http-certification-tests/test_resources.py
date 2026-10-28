"""Failure reproductions and bounded subprocess transport tests."""

import asyncio
import importlib
import os
import threading

import pytest
from test_isolation import load


@pytest.mark.parametrize("name", ["dashscope", "tbox"])
def test_cancel_hung_vendor_does_not_leave_threads(name):
    with load(name):
        module = importlib.import_module("pkg." + name + "_client")
        # RED on the old implementation. New transport removes this unsafe API.
        if not hasattr(module, "_iterate_sync_in_thread"):
            assert hasattr(module, "vendor_stream")
            return
        release = threading.Event()
        baseline = set(threading.enumerate())

        def stuck():
            release.wait(5)
            yield {}

        async def run():
            gen = module._iterate_sync_in_thread(stuck, timeout=30)
            task = asyncio.create_task(anext(gen))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await gen.aclose()
            assert not (set(threading.enumerate()) - baseline)

        try:
            asyncio.run(run())
        finally:
            release.set()


@pytest.mark.parametrize("name", ["dashscope", "tbox"])
def test_process_cancel_timeout_backpressure_and_reaping(name, tmp_path):
    with load(name):
        module = importlib.import_module("pkg.vendor_process")
        script = tmp_path / "fixture.py"
        script.write_text(
            'import sys,json,time,os\np=json.loads(sys.stdin.readline())\nprint(json.dumps({"item":{"pid":os.getpid()}}),flush=True)\nif p["operation"]=="hang": time.sleep(60)\nelse:\n while True: print(json.dumps({"item":{"text":"x"*10000}}),flush=True)\n'
        )

        async def run():
            for mode in ["hang", "fast"]:
                for _ in range(3):
                    gen = module.vendor_stream({"operation": mode}, timeout=0.3, worker=script)
                    first = await anext(gen)
                    pid = first["pid"]
                    await asyncio.sleep(0.05)
                    await gen.aclose()
                    with pytest.raises(ProcessLookupError):
                        os.kill(pid, 0)
            gen = module.vendor_stream({"operation": "hang"}, timeout=0.15, worker=script)
            pid = (await anext(gen))["pid"]
            with pytest.raises(TimeoutError):
                await anext(gen)
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
            gen = module.vendor_stream({"operation": "hang"}, timeout=30, worker=script)
            pid = (await anext(gen))["pid"]
            task = asyncio.create_task(anext(gen))
            await asyncio.sleep(0.03)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

        asyncio.run(run())


@pytest.mark.parametrize("name", ["dashscope", "tbox"])
def test_vendor_deadline_never_cancels_consumer(name, tmp_path):
    with load(name):
        module = importlib.import_module("pkg.vendor_process")
        script = tmp_path / "fixture.py"
        script.write_text(
            'import sys,json,time\np=json.loads(sys.stdin.readline())\nprint(json.dumps({"item":{}}),flush=True)\ntime.sleep(60)\n'
        )

        async def run():
            gen = module.vendor_stream({}, timeout=0.1, worker=script)
            await anext(gen)
            try:
                await asyncio.sleep(0.2)
                with pytest.raises(TimeoutError):
                    await anext(gen)
            finally:
                await gen.aclose()

        asyncio.run(run())
