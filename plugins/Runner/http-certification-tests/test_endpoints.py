import asyncio
import importlib

import pytest
from test_isolation import load


@pytest.mark.parametrize("name", ["coze", "dify", "deerflow", "weknora", "langflow", "n8n"])
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:secret@example.org",
        "http://example.org/#fragment",
        "http://example.org/\nheader",
    ],
)
def test_invalid_endpoint_rejected_before_io(name, url):
    with load(name):
        m = importlib.import_module("pkg." + name + "_client")
        cls = getattr(
            m,
            {
                "coze": "AsyncCozeClient",
                "dify": "AsyncDifyClient",
                "deerflow": "AsyncDeerFlowClient",
                "weknora": "AsyncWeKnoraClient",
                "langflow": "AsyncLangflowClient",
                "n8n": "AsyncN8nClient",
            }[name],
        )
        kwargs = {"api_key": "fixture"} if name != "n8n" else {}
        kwargs["webhook_url" if name == "n8n" else "api_base" if name in ("coze", "deerflow") else "base_url"] = url
        with pytest.raises(ValueError):
            cls(**kwargs)


@pytest.mark.parametrize("name", ["coze", "dify"])
def test_no_redirect_file_download_or_upload(name):
    from aiohttp import web

    async def run():
        visits = []

        async def redirect(request):
            visits.append("redirect")
            return web.Response(status=307, headers={"Location": "/sink"})

        async def sink(request):
            visits.append("sink")
            return web.json_response({"code": 0, "data": {"id": "id"}})

        app = web.Application()
        app.router.add_route("*", "/sink", sink)
        app.router.add_route("*", "/{path:.*}", redirect)
        server = web.AppRunner(app)
        await server.setup()
        site = web.TCPSite(server, "127.0.0.1", 0)
        await site.start()
        base = "http://127.0.0.1:" + str(site._server.sockets[0].getsockname()[1])
        try:
            with load(name):
                m = importlib.import_module("pkg." + name + "_client")
                if name == "coze":
                    client = m.AsyncCozeClient("fixture", api_base=base)
                    try:
                        await client.upload_file(b"x", "x.txt")
                    except Exception:
                        pass
                    finally:
                        await client.close()
                else:
                    client = m.AsyncDifyClient("fixture", base_url=base)
                    try:
                        await client.download_file(base + "/file")
                    except Exception:
                        pass
                assert visits == ["redirect"]
        finally:
            await server.cleanup()

    asyncio.run(run())
