"""Remote-image fetching: bounded streaming and validation."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


@contextlib.contextmanager
def serve(payload=PNG, *, status=200, content_type="image/png", send_length=True):
    """Serve ``payload`` from a throwaway local HTTP server."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if send_length:
                self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # silence test output
            return None

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = httpd.server_address
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}/image.png"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_add_from_url_stores_image(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        with serve() as url:
            item = await plugin.add_sticker_from_url("remote-cat", url)
        assert item["slug"] == "remote-cat"
        assert item["mime"] == "image/png"
        assert item["size"] == len(PNG)
        assert item["url"].startswith("http://localhost:5300/api/v1/plugins/")
        stored = await plugin.get_sticker_bytes("remote-cat")
        assert stored is not None
        assert stored[0] == PNG
    run(scenario())


def test_add_from_url_rejects_non_http(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with pytest.raises(ValueError, match="http"):
            await plugin.add_sticker_from_url("cat", "ftp://example.com/cat.png")
        with pytest.raises(ValueError, match="url is required"):
            await plugin.add_sticker_from_url("cat", "   ")
    run(scenario())


def test_add_from_url_rejects_error_status(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with serve(status=404) as url:
            with pytest.raises(ValueError, match="status 404"):
                await plugin.add_sticker_from_url("cat", url)
    run(scenario())


def test_add_from_url_rejects_oversized_content_length(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"max_sticker_mb": 1})
        big = PNG + b"\x00" * (2 * 1024 * 1024)
        with serve(big) as url:
            with pytest.raises(ValueError, match="larger than"):
                await plugin.add_sticker_from_url("cat", url)
    run(scenario())


def test_add_from_url_rejects_oversized_stream(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"max_sticker_mb": 1})
        big = PNG + b"\x00" * (2 * 1024 * 1024)
        with serve(big, send_length=False) as url:
            with pytest.raises(ValueError, match="exceeds"):
                await plugin.add_sticker_from_url("cat", url)
    run(scenario())


def test_add_from_url_uses_declared_content_type(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with serve(PNG, content_type="image/png; charset=binary") as url:
            item = await plugin.add_sticker_from_url("cat", url)
        assert item["mime"] == "image/png"
    run(scenario())
