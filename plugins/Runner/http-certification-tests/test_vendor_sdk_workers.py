"""Actual child processes and installed vendor SDKs; transport replies are fixtures."""

import asyncio
import importlib
import os
from pathlib import Path

import pytest
from test_isolation import load


@pytest.mark.parametrize("name", ["dashscope", "tbox"])
def test_real_vendor_sdk_child_request_contract_and_isolated_secrets(name, tmp_path, monkeypatch):
    with load(name):
        module = importlib.import_module("pkg." + name + "_client")
        transport = importlib.import_module("pkg.vendor_process")
        worker = Path(module.__file__).with_name("vendor_worker.py")
        wrapper = tmp_path / "transport_fixture.py"
        if name == "dashscope":
            fixture = """from dashscope import Application
from dashscope.app.application import ApplicationResponse
def call(**kwargs):
    assert kwargs['api_key'] in ('scope-A','scope-B')
    assert kwargs['stream'] and kwargs['incremental_output']
    assert kwargs.get('has_thoughts') is False or kwargs.get('flow_stream_mode')=='message_format'
    return iter([ApplicationResponse(status_code=200,request_id='fixture',output={'text':kwargs['api_key'],'session_id':kwargs['session_id'],'finish_reason':'stop'},usage={})])
Application.call=call
"""
        else:
            fixture = """from tboxsdk.core.httpclient import HttpClient

def post(self,path,**kwargs):
    assert path=='/api/chat'
    body=kwargs['data']
    assert body['appId']=='app' and body['query']=='hello' and body['stream'] is False
    assert body['files']==[{'fileId':'file-fixture','type':'IMAGE'}]
    return {'errorCode':'0','data':{'conversationId':body['conversationId'],'result':[{'chunk':body['userId']}]}}
HttpClient.post=post
"""
        wrapper.write_text(
            'import sys,os,runpy,socket,resource\nresource.setrlimit(resource.RLIMIT_FSIZE,(8388608,8388608))\nassert "UNRELATED_SECRET" not in os.environ\n'
            + 'def deny(*a,**k): raise AssertionError("fixture must not call network")\nsocket.create_connection=deny\n'
            + fixture
            + f'runpy.run_path({str(worker)!r},run_name="__main__")\n'
        )
        original = transport.vendor_stream

        def scoped(payload, *, timeout):
            return original(payload, timeout=timeout, worker=wrapper)

        monkeypatch.setattr(module, "vendor_stream", scoped)
        monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-inherited")

        async def run():
            async def one(scope):
                if name == "dashscope":
                    client = module.DashScopeClient(scope, "app", timeout=5)
                    gen = client.iter_agent("hello", session_id=scope, enable_thinking=False)
                else:
                    client = module.AsyncTboxClient(scope, timeout=5)
                    gen = client.chat(
                        "app",
                        scope,
                        "hello",
                        stream=False,
                        conversation_id=scope,
                        files=[{"file_id": "file-fixture", "type": "image"}],
                    )
                values = [x async for x in gen]
                return values

            a, b = await asyncio.gather(one("scope-A"), one("scope-B"))
            assert "scope-A" in str(a) and "scope-B" not in str(a)
            assert "scope-B" in str(b) and "scope-A" not in str(b)

        asyncio.run(run())


def test_tbox_hung_upload_reaped_and_temp_file_removed(tmp_path):
    with load("tbox"):
        module = importlib.import_module("pkg.tbox_client")
        transport = importlib.import_module("pkg.vendor_process")
        worker = Path(module.__file__).with_name("vendor_worker.py")
        wrapper = tmp_path / "upload_fixture.py"
        wrapper.write_text(
            """import sys,runpy,time,os,json
from tboxsdk.tbox import TboxClient
def upload(self,path):
    assert open(path,'rb').read()==b'fixture'
    sys.__stdout__.write(json.dumps({'item':{'path':path,'pid':os.getpid()}})+'\\n')
    sys.__stdout__.flush()
    time.sleep(60)
TboxClient.upload_file=upload
"""
            + f'runpy.run_path({str(worker)!r},run_name="__main__")\n'
        )

        async def run():
            gen = transport.vendor_stream(
                dict(operation="upload", api_key="fixture", data="Zml4dHVyZQ==", suffix=".txt"),
                timeout=3,
                worker=wrapper,
            )
            first = await anext(gen)
            assert Path(first["path"]).is_file()
            await gen.aclose()
            assert not Path(first["path"]).exists()
            assert not Path(first["path"]).parent.exists()
            with pytest.raises(ProcessLookupError):
                os.kill(first["pid"], 0)

        asyncio.run(run())


def test_dashscope_real_sdk_does_not_follow_redirects():
    from aiohttp import web

    async def run():
        visits = []

        async def redirect(request):
            visits.append(request.path)
            return web.Response(status=307, headers={"Location": "/sink"})

        async def sink(request):
            visits.append("sink")
            return web.json_response({"output": {"text": "forbidden"}})

        app = web.Application()
        app.router.add_route("*", "/sink", sink)
        app.router.add_route("*", "/{path:.*}", redirect)
        server = web.AppRunner(app)
        await server.setup()
        site = web.TCPSite(server, "127.0.0.1", 0)
        await site.start()
        base = "http://127.0.0.1:" + str(site._server.sockets[0].getsockname()[1])
        try:
            with load("dashscope"):
                transport = importlib.import_module("pkg.vendor_process")
                gen = transport.vendor_stream(
                    {
                        "kwargs": {
                            "app_id": "fixture",
                            "api_key": "fixture",
                            "prompt": "hello",
                            "stream": True,
                            "base_address": base,
                        }
                    },
                    timeout=5,
                )
                try:
                    async for _ in gen:
                        pass
                except RuntimeError:
                    pass
                finally:
                    await gen.aclose()
            assert visits and "sink" not in visits
        finally:
            await server.cleanup()

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["success", "cancel", "timeout"])
def test_tbox_actual_sdk_upload_temp_lifecycle(mode, tmp_path, monkeypatch):
    import json

    with load("tbox"):
        module = importlib.import_module("pkg.tbox_client")
        transport = importlib.import_module("pkg.vendor_process")
        worker = Path(module.__file__).with_name("vendor_worker.py")
        proof = tmp_path / "upload.json"
        wrapper = tmp_path / "upload_fixture.py"
        wrapper.write_text(
            "import os,json,time,runpy\nfrom pathlib import Path\nfrom tboxsdk.core.httpclient import HttpClient\n"
            + "def post_file(self,path,files,**kwargs):\n"
            + " assert path=='/api/file/upload'\n file=files['file'][1]\n assert file.read()==b'fixture-file'\n"
            + f" Path({str(proof)!r}).write_text(json.dumps({{'pid':os.getpid(),'file':file.name,'directory':os.environ['TMPDIR']}}))\n"
            + (" time.sleep(60)\n" if mode != "success" else "")
            + " return {'errorCode':'0','data':'fixture-file-id'}\nHttpClient.post_file=post_file\n"
            + f"runpy.run_path({str(worker)!r},run_name='__main__')\n"
        )

        async def stream(payload, **kwargs):
            gen = transport.vendor_stream(payload, worker=wrapper, **kwargs)
            try:
                async for item in gen:
                    yield item
            finally:
                await gen.aclose()

        monkeypatch.setattr(module, "vendor_stream", stream)

        async def run():
            client = module.AsyncTboxClient("fixture", timeout=2 if mode == "timeout" else 10)
            task = asyncio.create_task(client.upload_file(b"fixture-file", "image.png"))
            async with asyncio.timeout(4):
                while not proof.exists():
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
            info = json.loads(proof.read_text())
            if mode == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            elif mode == "timeout":
                with pytest.raises(module.TboxAPIError, match="timed out"):
                    await task
            else:
                assert await task == "fixture-file-id"
            assert not Path(info["file"]).exists()
            assert not Path(info["directory"]).exists()
            with pytest.raises(ProcessLookupError):
                os.kill(info["pid"], 0)

        asyncio.run(run())
