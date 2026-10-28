"""Outbound-safety regression tests for the WebSearch ``visit_web`` tool.

These cover the two blocking certification findings:

* F1 - the user-supplied URL is an unvalidated server-side request target. The
  tests prove that loopback / link-local / private / metadata ranges, special
  addresses and non-HTTP(S) schemes are refused before a connection is made,
  that every redirect hop is re-validated, that the connection goes to the
  validated IP (so a later DNS answer cannot rebind it) and that TLS keeps the
  default verification settings.
* F2 - neither the download, the memory nor the parse work was bounded. The
  tests prove that a declared oversized body is refused without reading it, a
  streamed/compressed body is cut off at the cap without buffering it all, the
  HTML handed to the parser is capped, and the fetch is cooperatively
  cancellable with a bounded number of in-flight fetches.

Every assertion here fails against the pre-fix ``requests.get`` implementation.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import gzip
import http.client
import logging
import socket
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import components.tools.visit_web as visit_web_module  # noqa: E402
from components.tools.sites import model as site_model  # noqa: E402
from components.tools.sites import safe_fetch  # noqa: E402
from components.tools.sites.safe_fetch import (  # noqa: E402
    BlockedTargetError,
    FetchAbortedError,
    FetchError,
    IncompleteCompressedStreamError,
    ResponseTooLargeError,
    TrailingDataError,
    TruncatedResponseError,
)

PUBLIC_IP = "93.184.216.34"


# --------------------------------------------------------------------------- #
# Test HTTP server
# --------------------------------------------------------------------------- #
class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 - http.server API
        owner = self.server.owner
        owner.hits.append(self.path)
        responder = owner.responses.get(self.path)
        if responder is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        responder(self)

    def log_message(self, *args):  # keep the test output quiet
        pass


class _Server:
    """Local HTTP server whose per-path behaviour is set by the test."""

    def __init__(self) -> None:
        self.responses: dict[str, object] = {}
        self.hits: list[str] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.owner = self
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_Server":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)


def _send(handler, body: bytes, *, status: int = 200, ctype: str = "text/html; charset=utf-8", headers=()):
    handler.send_response(status)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    for name, value in headers:
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(body)


def _route_connections(monkeypatch, port: int, attempted: list | None = None):
    """Send every validated connection to the local test server.

    The address the client decided to use is still recorded (``attempted``),
    so a test can prove which target passed validation.
    """
    real_create_connection = socket.create_connection

    def fake_create_connection(address, *args, **kwargs):
        if attempted is not None:
            attempted.append(address)
        return real_create_connection(("127.0.0.1", port), *args, **kwargs)

    monkeypatch.setattr(safe_fetch.socket, "create_connection", fake_create_connection)


def _connect_to(port: int):
    """Replacement for ``socket.create_connection`` aimed at the test server."""
    real_create_connection = socket.create_connection

    def connect(address, *args, **kwargs):
        return real_create_connection(("127.0.0.1", port), *args, **kwargs)

    return connect


def _fetch(server: "_Server", path: str, **kwargs):
    """Fetch ``path`` from the test server through a validated public URL."""
    with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):
        return safe_fetch.fetch_document(f"http://{PUBLIC_IP}:{server.port}{path}", **kwargs)


def _tool() -> object:
    return visit_web_module.VisitWeb()


_SCRIPTED_PEERS: list = []
"""Scripted peers stay open for the whole session: closing one while the client
still has unread data makes Windows reset the connection (WSAECONNABORTED)."""


def _scripted_peer(monkeypatch, raw_response: bytes, *, on_connect=None):
    """Answer every connection with ``raw_response`` from a real socketpair.

    No HTTP server is involved: the peer sends the scripted bytes and then stops
    sending.  That reproduces, on every platform, the clean EOF a shut-down
    socket shows on Linux, which is what makes the abort/truncation checks below
    platform-independent.
    """

    def fake_create_connection(address, *args, **kwargs):
        peer, client = socket.socketpair()
        peer.sendall(raw_response)
        peer.shutdown(socket.SHUT_WR)  # the peer simply stops sending
        _SCRIPTED_PEERS.append(peer)
        if on_connect is not None:
            on_connect()
        return client

    monkeypatch.setattr(safe_fetch.socket, "create_connection", fake_create_connection)


# --------------------------------------------------------------------------- #
# F1 - target validation
# --------------------------------------------------------------------------- #
def test_loopback_literal_is_refused_before_any_connection():
    with _Server() as server:
        server.responses["/"] = lambda handler: _send(handler, b"<html>ok</html>")

        with pytest.raises(BlockedTargetError):
            safe_fetch.fetch_document(f"http://127.0.0.1:{server.port}/")

        assert server.hits == []


def test_visit_web_refuses_a_loopback_target_end_to_end():
    with _Server() as server:
        server.responses["/"] = lambda handler: _send(handler, b"<html>ok</html>")

        result = asyncio.run(_tool().call({"url": f"http://127.0.0.1:{server.port}/"}))

        assert isinstance(result, str) and result.startswith("error visit web:")
        assert "refusing non-public address" in result
        assert server.hits == []


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.1.2.3",
        "169.254.169.254",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",
        "0.0.0.0",
        "[::1]",
        "[fd00::1]",
        "[fe80::1]",
        "[::ffff:127.0.0.1]",
    ],
)
def test_non_public_targets_are_refused_before_connecting(host: str, monkeypatch):
    attempted: list = []

    def fail_connect(*args, **kwargs):
        attempted.append(args)
        pytest.fail("the client must not open a connection for a blocked target")

    monkeypatch.setattr(safe_fetch.socket, "create_connection", fail_connect)

    with pytest.raises(BlockedTargetError):
        safe_fetch.fetch_document(f"http://{host}/")

    assert attempted == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://example.com/", "data:text/html,x"])
def test_non_http_schemes_are_refused(url: str, monkeypatch):
    monkeypatch.setattr(
        safe_fetch.socket, "create_connection", lambda *a, **k: pytest.fail("no connection expected")
    )

    with pytest.raises(BlockedTargetError):
        safe_fetch.fetch_document(url)


@pytest.mark.parametrize("url", ["http://[::1/", "http://", "https:///path"])
def test_malformed_urls_are_refused(url: str, monkeypatch):
    monkeypatch.setattr(
        safe_fetch.socket, "create_connection", lambda *a, **k: pytest.fail("no connection expected")
    )

    with pytest.raises(BlockedTargetError):
        safe_fetch.fetch_document(url)


def test_redirect_to_private_address_is_refused_and_never_connected(monkeypatch):
    attempted: list = []
    with _Server() as server:
        server.responses["/start"] = lambda handler: _send(
            handler,
            b"",
            status=302,
            headers=[("Location", "http://169.254.169.254/latest/meta-data/")],
        )
        _route_connections(monkeypatch, server.port, attempted)

        with pytest.raises(BlockedTargetError) as excinfo:
            safe_fetch.fetch_document(f"http://{PUBLIC_IP}:{server.port}/start")

        assert "169.254.169.254" in str(excinfo.value)
        assert server.hits == ["/start"]
        # Only the validated first hop was dialled; the redirect target was not.
        assert [address[0] for address in attempted] == [PUBLIC_IP]


def test_connection_uses_the_validated_ip_so_dns_cannot_rebind(monkeypatch):
    resolutions: list[str] = []

    def fake_getaddrinfo(host, port, **kwargs):
        resolutions.append(host)
        address = "93.184.216.34" if len(resolutions) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    attempted: list = []

    def fake_create_connection(address, *args, **kwargs):
        attempted.append(address)
        raise OSError("unreachable in this test")

    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(safe_fetch.socket, "create_connection", fake_create_connection)

    with pytest.raises(FetchError):
        safe_fetch.fetch_document("http://rebind.example/")

    # The socket went to the address that was validated, never to the second
    # (private) answer a rebinding resolver would hand out.
    assert attempted == [("93.184.216.34", 80)]


def test_tls_uses_the_default_verification_context(monkeypatch):
    created: list = []
    hostnames: list = []
    handshakes: list = []
    deferred: list = []
    real_context = safe_fetch.ssl.create_default_context

    class _PlainTLS:
        """Minimal SSLSocket double: a plain transport plus a no-op handshake."""

        def __init__(self, sock):
            self._sock = sock

        def do_handshake(self):
            handshakes.append("handshake")

        def settimeout(self, value):
            self._sock.settimeout(value)

        def sendall(self, data):
            self._sock.sendall(data)

        def makefile(self, *args, **kwargs):
            return self._sock.makefile(*args, **kwargs)

        def shutdown(self, *args):
            self._sock.shutdown(*args)

        def close(self):
            self._sock.close()

        def fileno(self):
            return self._sock.fileno()

    class _RecordingContext:
        def __init__(self, context):
            self.context = context

        def wrap_socket(self, sock, server_hostname=None, do_handshake_on_connect=True, **kwargs):
            hostnames.append(server_hostname)
            # The handshake is deferred so the abort watch covers it too.
            deferred.append(do_handshake_on_connect is False)
            return _PlainTLS(sock)

    def fake_create_default_context(*args, **kwargs):
        context = real_context(*args, **kwargs)
        created.append(context)
        return _RecordingContext(context)

    with _Server() as server:
        server.responses["/"] = lambda handler: _send(handler, b"<html>secure</html>")
        _route_connections(monkeypatch, server.port)
        monkeypatch.setattr(safe_fetch.ssl, "create_default_context", fake_create_default_context)

        document = safe_fetch.fetch_document(f"https://{PUBLIC_IP}:{server.port}/")

        assert document.status_code == 200

    assert created and created[0].verify_mode == ssl.CERT_REQUIRED
    assert created[0].check_hostname is True
    assert hostnames == [PUBLIC_IP]
    assert deferred == [True]
    assert handshakes == ["handshake"]


def test_public_addresses_are_recognised():
    assert safe_fetch.is_public_address("8.8.8.8")
    assert safe_fetch.is_public_address("93.184.216.34")
    assert safe_fetch.is_public_address("2606:4700::1111")
    assert not safe_fetch.is_public_address("127.0.0.1")
    assert not safe_fetch.is_public_address("169.254.169.254")
    assert not safe_fetch.is_public_address("::ffff:127.0.0.1")
    assert not safe_fetch.is_public_address("example.com")


# --------------------------------------------------------------------------- #
# F2 - bounded download, memory and parse work
# --------------------------------------------------------------------------- #
def test_oversized_declared_body_is_rejected_without_reading_it(monkeypatch):
    def huge_body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", "100000000")
        handler.end_headers()
        handler.wfile.write(b"<html>")
        handler.wfile.flush()

    def forbidden(*args, **kwargs):
        pytest.fail("the body must not be read once Content-Length exceeds the cap")

    monkeypatch.setattr(safe_fetch, "_raw_chunks", forbidden)

    with _Server() as server:
        server.responses["/huge"] = huge_body
        _route_connections(monkeypatch, server.port)

        with pytest.raises(ResponseTooLargeError) as excinfo:
            safe_fetch.fetch_document(f"http://{PUBLIC_IP}:{server.port}/huge")

    assert "100000000" in str(excinfo.value)


def test_streamed_body_is_capped_without_buffering_it_all():
    pulled: list[int] = []

    def chunks():
        for index in range(100):
            pulled.append(index)
            yield b"A" * (1024 * 1024)

    with pytest.raises(ResponseTooLargeError):
        safe_fetch.collect_bounded(chunks(), 8192)

    # One chunk is already over the cap: the remaining 99 MiB are never pulled.
    assert pulled == [0]


def test_chunked_response_is_capped():
    def chunked_body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        block = b"B" * (256 * 1024)
        try:
            for _ in range(40):  # 10 MiB with no Content-Length to pre-check
                handler.wfile.write(b"%X\r\n" % len(block) + block + b"\r\n")
            handler.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass

    with _Server() as server:
        server.responses["/chunked"] = chunked_body
        # A small cap keeps the test quick while proving the cumulative bound.
        with pytest.raises(ResponseTooLargeError):
            _fetch(server, "/chunked", max_bytes=512 * 1024)


def test_compressed_body_is_capped_after_inflation():
    bomb = gzip.compress(b"A" * (8 * 1024 * 1024))
    assert len(bomb) < safe_fetch.MAX_RESPONSE_BYTES  # the wire form passes the byte cap

    with _Server() as server:
        server.responses["/bomb"] = lambda handler: _send(
            handler, bomb, headers=[("Content-Encoding", "gzip")]
        )
        with pytest.raises(ResponseTooLargeError) as excinfo:
            _fetch(server, "/bomb")

    assert "decompressed" in str(excinfo.value)


def test_gzip_inflation_stops_before_the_whole_stream_is_read():
    blob = gzip.compress(b"A" * (8 * 1024 * 1024))
    blocks = [blob[index : index + 4096] for index in range(0, len(blob), 4096)]
    pulled: list[bytes] = []

    def source():
        for block in blocks:
            pulled.append(block)
            yield block

    decoder = safe_fetch._BodyDecoder("gzip", 8192)
    with pytest.raises(ResponseTooLargeError):
        safe_fetch.collect_bounded(decoder.decode(source()), 8192)

    assert 0 < len(pulled) < len(blocks)


def test_encoded_body_is_capped_cumulatively():
    counter = safe_fetch._ByteCounter(1024)

    def source():
        for _ in range(100):
            yield b"A" * 512

    with pytest.raises(ResponseTooLargeError):
        list(counter.count(source()))


def test_trailing_bytes_after_the_compressed_stream_are_refused():
    # The reviewer's probe: a tiny valid gzip stream followed by far more
    # bytes than the cap.  The old decoder fed the second chunk to the EOF'd
    # zlib object and returned "OK" while ``unused_data`` grew to 8 MiB.
    stream = gzip.compress(b"OK")
    trailing = b"X" * (8 * 1024 * 1024)
    decoder = safe_fetch._BodyDecoder("gzip", 2 * 1024 * 1024)

    with pytest.raises(TrailingDataError):
        safe_fetch.collect_bounded(decoder.decode(iter([stream, trailing])), 2 * 1024 * 1024)

    assert not decoder._inflater.unused_data


def test_trailing_bytes_inside_the_final_chunk_are_refused():
    decoder = safe_fetch._BodyDecoder("gzip", 2 * 1024 * 1024)
    combined = gzip.compress(b"OK") + b"X" * (2 * 1024 * 1024)

    with pytest.raises(TrailingDataError):
        safe_fetch.collect_bounded(decoder.decode(iter([combined])), 2 * 1024 * 1024)


def test_decoder_stops_reading_at_the_first_trailing_chunk():
    pulled = 0

    def source():
        nonlocal pulled
        yield gzip.compress(b"OK")
        for _ in range(1000):
            pulled += 1
            yield b"X" * 8192

    decoder = safe_fetch._BodyDecoder("gzip", 2 * 1024 * 1024)
    with pytest.raises(TrailingDataError):
        safe_fetch.collect_bounded(decoder.decode(source()), 2 * 1024 * 1024)

    # Only the first trailing chunk was pulled; the other 999 are never read.
    assert pulled == 1


def test_incomplete_compressed_stream_is_refused():
    truncated = gzip.compress(b"<html>ok</html>")[:-8]  # no gzip trailer
    decoder = safe_fetch._BodyDecoder("gzip", 2 * 1024 * 1024)

    with pytest.raises(IncompleteCompressedStreamError):
        safe_fetch.collect_bounded(decoder.decode(iter([truncated])), 2 * 1024 * 1024)


def test_trailing_compressed_data_fails_the_fetch():
    def trailing_body(handler):
        payload = gzip.compress(b"<html><head><title>OK</title></head></html>")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Encoding", "gzip")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        try:
            for piece in (payload, b"X" * (4 * 1024 * 1024)):
                handler.wfile.write(b"%X\r\n" % len(piece) + piece + b"\r\n")
            handler.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass

    with _Server() as server:
        server.responses["/trailing"] = trailing_body
        with pytest.raises(FetchError) as excinfo:
            _fetch(server, "/trailing")

    # A body that did not stop at its compressed stream's end never becomes a
    # document; it fails as a size/format error instead.
    assert isinstance(
        excinfo.value, (TrailingDataError, ResponseTooLargeError)
    )


def test_incomplete_compressed_body_fails_the_fetch():
    truncated = gzip.compress(b"<html><head><title>OK</title></head></html>")[:-8]

    def body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Encoding", "gzip")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        try:
            handler.wfile.write(b"%X\r\n" % len(truncated) + truncated + b"\r\n")
            handler.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass

    with _Server() as server:
        server.responses["/truncated"] = body
        with pytest.raises(IncompleteCompressedStreamError):
            _fetch(server, "/truncated")


def test_corrupt_compressed_body_fails_the_fetch():
    corrupted = bytearray(gzip.compress(b"<html><head><title>OK</title></head></html>"))
    corrupted[-5] ^= 0xFF  # break the gzip CRC32; only an end-of-stream check sees it

    def body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Encoding", "gzip")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        payload = bytes(corrupted)
        try:
            handler.wfile.write(b"%X\r\n" % len(payload) + payload + b"\r\n")
            handler.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass

    with _Server() as server:
        server.responses["/corrupt"] = body
        with pytest.raises(FetchError) as excinfo:
            _fetch(server, "/corrupt")

    assert not isinstance(excinfo.value, (TrailingDataError, IncompleteCompressedStreamError))


def test_parse_input_is_capped(monkeypatch):
    body = ("<html><head><title>Big</title></head><body>" + "word " * 200000 + "</body></html>").encode()

    monkeypatch.setattr(safe_fetch, "MAX_PARSE_CHARS", 4096)
    real_soup = site_model.BeautifulSoup
    parsed_sizes: list[int] = []

    def spy(markup, *args, **kwargs):
        parsed_sizes.append(len(markup))
        return real_soup(markup, *args, **kwargs)

    with _Server() as server:
        server.responses["/big"] = lambda handler: _send(handler, body)
        _route_connections(monkeypatch, server.port)
        url = f"http://{PUBLIC_IP}:{server.port}/big"

        document = safe_fetch.fetch_document(url)
        assert len(document.text) > 4096  # the page really is larger than the cap

        monkeypatch.setattr(site_model, "BeautifulSoup", spy)
        status_code, raw_html = site_model.SiteAdapterBase.get_html(url)
        site_model.SiteAdapterBase.extra_plain(raw_html)
        site_model.SiteAdapterBase.extra_title_element(raw_html)

    assert status_code == 200
    assert len(raw_html) == 4096
    assert parsed_sizes and max(parsed_sizes) <= 4096


def test_brief_len_is_clamped():
    assert site_model.clamp_brief_len(-10) == 1
    assert site_model.clamp_brief_len(0) == 1
    assert site_model.clamp_brief_len(1024) == 1024
    assert site_model.clamp_brief_len(10**9) == site_model.MAX_BRIEF_CHARS
    assert site_model.clamp_brief_len("nonsense") == site_model.DEFAULT_BRIEF_LEN
    assert site_model.clamp_brief_len(None) == site_model.DEFAULT_BRIEF_LEN


def test_fetch_deadline_stops_a_slow_peer():
    finished = threading.Event()

    def slow_body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", "1000000")
        handler.end_headers()
        try:
            for _ in range(100):
                handler.wfile.write(b"x" * 1024)
                handler.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass

    errors: list[Exception] = []
    returned: list[object] = []

    with _Server() as server:
        server.responses["/slow"] = slow_body
        with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):
            def run():
                try:
                    returned.append(
                        safe_fetch.fetch_document(
                            f"http://{PUBLIC_IP}:{server.port}/slow", timeout=1.0
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - recorded for the assertion
                    errors.append(exc)
                finally:
                    finished.set()

            thread = threading.Thread(target=run, daemon=True)
            start = time.monotonic()
            thread.start()
            assert finished.wait(10), "the fetch did not honour its deadline"
            elapsed = time.monotonic() - start

    assert returned == [], "a timed-out fetch must not be returned as a document"
    assert errors and isinstance(errors[0], FetchAbortedError)
    assert elapsed < 5


def test_an_abort_that_reads_as_a_clean_eof_never_returns_a_body(monkeypatch):
    """The Linux symptom: a shut-down socket reads as EOF mid-body.

    The abort lands while the reader is blocked in the socket read, and that
    read comes back as a plain EOF.  The fetch must abort instead of handing
    the partial body back as a complete response.
    """
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: 1000000\r\n"
        b"\r\n"
        b"<html>partial"
    )
    stop_event = threading.Event()
    real_read1 = http.client.HTTPResponse.read1
    reads: list[int] = []

    def read1(self, n=-1):
        chunk = real_read1(self, n)
        reads.append(len(chunk))
        if not chunk:
            # The cancel/deadline fires while this read is parked in the socket.
            stop_event.set()
        return chunk

    _scripted_peer(monkeypatch, raw)
    monkeypatch.setattr(http.client.HTTPResponse, "read1", read1)

    with pytest.raises(FetchAbortedError):
        safe_fetch.fetch_document(
            f"http://{PUBLIC_IP}/partial", timeout=30, stop_event=stop_event
        )

    assert reads and reads[0] > 0, "the body must really have started before the EOF"


def test_a_body_shorter_than_content_length_is_never_returned(monkeypatch):
    """A peer that stops early must fail loudly, not look like a page."""
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: 1000000\r\n"
        b"\r\n"
        b"<html>partial"
    )
    _scripted_peer(monkeypatch, raw)

    with pytest.raises(TruncatedResponseError) as excinfo:
        safe_fetch.fetch_document(f"http://{PUBLIC_IP}/partial")

    assert "truncated" in str(excinfo.value)
    assert "13 of 1000000" in str(excinfo.value)


def test_stop_event_aborts_an_in_flight_download():
    """A cancelled in-flight fetch ends promptly and never returns a document.

    The outcome must not depend on how the platform reports the shut-down
    socket (exception vs clean EOF): either way the caller sees an abort, never
    a partial document.
    """
    started = threading.Event()
    finished = threading.Event()
    errors: list[Exception] = []
    returned: list[object] = []
    stop_event = threading.Event()

    def slow_body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", "1000000")
        handler.end_headers()
        try:
            for _ in range(400):
                handler.wfile.write(b"x" * 1024)
                handler.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    with _Server() as server:
        server.responses["/slow"] = slow_body
        with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):
            def run():
                started.set()
                try:
                    returned.append(
                        safe_fetch.fetch_document(
                            f"http://{PUBLIC_IP}:{server.port}/slow",
                            timeout=30,
                            stop_event=stop_event,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)
                finally:
                    finished.set()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            assert started.wait(5)
            time.sleep(0.4)
            stop_event.set()

    assert finished.wait(10), "the stop flag did not interrupt the in-flight download"
    assert returned == [], "an aborted fetch must not be returned as a document"
    assert errors and isinstance(errors[0], FetchAbortedError)


def test_cancelling_the_tool_sets_the_worker_stop_flag():
    observed: list[bool] = []
    done = threading.Event()

    def fake_process(url, brief_len, **kwargs):
        stop = kwargs["stop_event"]
        while not stop.is_set():
            time.sleep(0.01)
        observed.append(stop.is_set())
        done.set()
        return "aborted"

    async def scenario():
        with mock.patch.object(visit_web_module, "process", fake_process):
            task = asyncio.create_task(_tool().call({"url": "https://slow.example/"}))
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
    assert asyncio.run(asyncio.to_thread(done.wait, 5)), "worker never observed the cancellation"
    assert observed == [True]


def test_concurrent_fetches_are_bounded(monkeypatch):
    monkeypatch.setattr(visit_web_module, "FETCH_SLOT_WAIT_SECONDS", 0.25)
    gate = threading.Event()
    slots = visit_web_module.MAX_CONCURRENT_FETCHES

    def fake_process(url, brief_len, **kwargs):
        gate.wait(10)
        return f"done:{url}"

    async def scenario():
        with mock.patch.object(visit_web_module, "process", fake_process):
            tasks = [
                asyncio.create_task(_tool().call({"url": f"https://example.com/{index}"}))
                for index in range(slots + 1)
            ]
            await asyncio.sleep(0.3)  # let the first `slots` calls take the pool
            busy = await tasks[-1]
            gate.set()
            return busy, await asyncio.gather(*tasks[:-1])

    busy, finished = asyncio.run(scenario())

    assert busy == "error visit web: too many concurrent page fetches, please retry later"
    assert finished == [f"done:https://example.com/{index}" for index in range(slots)]


# --------------------------------------------------------------------------- #
# F2 (third round) - the shared fetch slot has exactly one owner
# --------------------------------------------------------------------------- #
def test_tool_cancelled_while_queued_releases_its_slot_exactly_once(monkeypatch):
    """A call cancelled before its worker starts must not leak the slot."""
    gate = threading.Event()
    worker_ran = threading.Event()

    def fake_worker(url, brief_len, stop_event, lease, *_rest):
        worker_ran.set()
        try:
            return f"done:{url}"
        finally:
            lease.release()

    def occupy(*_args):
        gate.wait(10)
        return "blocker"

    async def scenario():
        with mock.patch.object(visit_web_module, "_worker", fake_worker):
            loop = asyncio.get_running_loop()
            loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1))
            slots = visit_web_module._slots()
            free = slots._value
            tool = _tool()

            # Occupy the single worker thread so the call below stays queued.
            blocker = loop.run_in_executor(None, occupy, "u", 1, None, slots, loop)
            await asyncio.sleep(0.1)

            task = asyncio.create_task(tool.call({"url": "https://example.com/queued"}))
            await asyncio.sleep(0.3)
            assert not worker_ran.is_set(), "the worker must still be queued"
            assert slots._value == free - 1, "the queued call holds its slot"

            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert slots._value == free - 1, "the slot was released while still queued/running"

            gate.set()
            assert await blocker == "blocker"
            for _ in range(250):
                if worker_ran.is_set() and slots._value == free:
                    break
                await asyncio.sleep(0.02)
            assert worker_ran.is_set(), "the queued worker never ran"
            # Exactly one release: a second one would push the pool above its cap.
            assert slots._value == free

            assert (
                await tool.call({"url": "https://example.com/next"})
                == "done:https://example.com/next"
            )

    asyncio.run(scenario())


def test_cancelled_running_tool_keeps_its_slot_until_the_worker_ends(monkeypatch):
    """A worker that is still running must never lose its slot early."""
    started = threading.Event()
    still_running = threading.Event()

    def fake_worker(url, brief_len, stop_event, lease, *_rest):
        started.set()
        stop_event.wait(10)  # the caller's cancellation sets this
        still_running.set()
        time.sleep(0.3)  # the thread is undeniably still alive here
        try:
            return f"done:{url}"
        finally:
            lease.release()

    async def scenario():
        with mock.patch.object(visit_web_module, "_worker", fake_worker):
            slots = visit_web_module._slots()
            free = slots._value
            tool = _tool()

            task = asyncio.create_task(tool.call({"url": "https://slow.example/"}))
            await asyncio.sleep(0.3)
            assert started.is_set()
            assert slots._value == free - 1

            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0.1)
            assert still_running.is_set()
            assert slots._value == free - 1, "the slot was released while the worker was running"

            for _ in range(250):
                if slots._value == free:
                    break
                await asyncio.sleep(0.02)
            assert slots._value == free

    asyncio.run(scenario())


def test_cancel_during_the_body_frees_the_slot_and_stays_usable(monkeypatch):
    """An aborted in-flight fetch ends, frees exactly one slot and stays usable."""
    started = threading.Event()

    def slow_body(handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", "1000000")
        handler.end_headers()
        try:
            for _ in range(400):  # far longer than the test: only the abort ends it
                handler.wfile.write(b"x" * 1024)
                handler.wfile.flush()
                started.set()
                time.sleep(0.05)
        except OSError:
            pass

    async def scenario(port: int):
        slots = visit_web_module._slots()
        free = slots._value
        tool = _tool()

        task = asyncio.create_task(
            tool.call({"url": f"http://{PUBLIC_IP}:{port}/slow"})
        )
        await asyncio.to_thread(started.wait, 5)
        assert slots._value == free - 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(300):
            if slots._value == free:
                break
            await asyncio.sleep(0.02)
        assert slots._value == free, "the aborted fetch did not release exactly one slot"

        return await tool.call({"url": f"http://{PUBLIC_IP}:{port}/ok"})

    with _Server() as server:
        server.responses["/slow"] = slow_body
        server.responses["/ok"] = lambda handler: _send(
            handler, b"<html><head><title>Ok</title></head><body>after abort</body></html>"
        )
        with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):
            result = asyncio.run(scenario(server.port))

    assert "Ok" in result and "after abort" in result


def test_slot_lease_releases_at_most_once():
    """The two owners of a slot can never give it back twice."""

    async def scenario():
        slots = visit_web_module._slots()
        free = slots._value
        await slots.acquire()
        assert slots._value == free - 1

        lease = visit_web_module._SlotLease(slots, asyncio.get_running_loop())
        lease.release()
        lease.release()  # a second owner must be a no-op
        assert slots._value == free

    asyncio.run(scenario())


def test_tool_submit_failure_leaks_no_slot(monkeypatch):
    """A failed executor submission must give the already-acquired slot back."""

    async def scenario():
        slots = visit_web_module._slots()
        free = slots._value
        loop = asyncio.get_running_loop()

        def refuse_submit(*args, **kwargs):
            raise RuntimeError("cannot schedule new futures after shutdown")

        monkeypatch.setattr(loop, "run_in_executor", refuse_submit)
        result = await _tool().call({"url": "https://example.com/"})
        assert isinstance(result, str) and result.startswith("error visit web:")
        assert slots._value == free

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# F1 (third round) - deadline/cancellation cover the status and header phase
# --------------------------------------------------------------------------- #
def test_deadline_ends_a_response_whose_headers_never_arrive():
    """A peer that drips bytes must not outlive the absolute deadline."""
    finished = threading.Event()
    errors: list[Exception] = []

    def drip_headers(handler):
        # One byte at a time, always inside the socket idle timeout, never a
        # complete status line: ``getresponse()`` would block here forever.
        try:
            for _ in range(120):
                handler.wfile.write(b"x")
                handler.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    with _Server() as server:
        server.responses["/drip"] = drip_headers
        with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):

            def run():
                try:
                    safe_fetch.fetch_document(
                        f"http://{PUBLIC_IP}:{server.port}/drip", timeout=1.0
                    )
                except Exception as exc:  # noqa: BLE001 - recorded for the assertion
                    errors.append(exc)
                finally:
                    finished.set()

            thread = threading.Thread(target=run, daemon=True)
            start = time.monotonic()
            thread.start()
            assert finished.wait(8), "the header read outlived the absolute deadline"
            elapsed = time.monotonic() - start

    assert isinstance(errors[0], FetchAbortedError)
    assert elapsed < 5


def test_stop_event_ends_a_response_whose_headers_never_arrive():
    """Cancellation must end the status/header phase too, not only the body."""
    started = threading.Event()
    finished = threading.Event()
    errors: list[Exception] = []
    stop_event = threading.Event()

    def drip_headers(handler):
        try:
            for _ in range(120):
                handler.wfile.write(b"x")
                handler.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    with _Server() as server:
        server.responses["/drip"] = drip_headers
        with mock.patch.object(safe_fetch.socket, "create_connection", _connect_to(server.port)):

            def run():
                started.set()
                try:
                    safe_fetch.fetch_document(
                        f"http://{PUBLIC_IP}:{server.port}/drip",
                        timeout=30,
                        stop_event=stop_event,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)
                finally:
                    finished.set()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            assert started.wait(5)
            time.sleep(0.4)
            stop_event.set()

    assert finished.wait(8), "the stop flag did not end the header read"
    assert isinstance(errors[0], FetchAbortedError)


def test_deadline_abandons_a_resolver_that_never_answers(monkeypatch):
    """A stalled DNS lookup must not hold the fetch past the deadline."""
    unblock = threading.Event()

    def stalled_getaddrinfo(*args, **kwargs):
        unblock.wait(8)
        return []

    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", stalled_getaddrinfo)
    start = time.monotonic()
    try:
        with pytest.raises(FetchAbortedError):
            safe_fetch.fetch_document("http://stalled.example/", timeout=1.0)
        elapsed = time.monotonic() - start
    finally:
        unblock.set()
    assert elapsed < 5


def test_tool_error_and_log_never_repeat_url_credentials_or_query(monkeypatch, caplog):
    raw = f"http://alice:s3cret-pw@{PUBLIC_IP}:1/page?token=s3cret-token#frag"

    def fail_connect(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(safe_fetch.socket, "create_connection", fail_connect)

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(_tool().call({"url": raw}))

    assert result.startswith("error visit web:")
    for text in (result, caplog.text):
        assert "s3cret-pw" not in text, text
        assert "s3cret-token" not in text, text
        assert "alice" not in text, text
    assert PUBLIC_IP in result  # the useful, non-secret part survives


# --------------------------------------------------------------------------- #
# F1 (fourth round) - an abandoned lookup keeps its own bounded budget
# --------------------------------------------------------------------------- #
def _gated_resolver(gate, calls):
    """``getaddrinfo`` stand-in that blocks until ``gate`` is set."""

    def getaddrinfo(host, port, **kwargs):
        calls.append(host)
        gate.wait(10)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))]

    return getaddrinfo


def _dns_threads():
    return [t for t in threading.enumerate() if t.name == "safe-fetch-dns"]


def _drain_resolver_pool(timeout=5.0):
    deadline = time.monotonic() + timeout
    while safe_fetch.resolver_stats()["in_flight"] and time.monotonic() < deadline:
        time.sleep(0.02)
    return safe_fetch.resolver_stats()


def test_abandoned_waiter_does_not_free_the_resolver_budget(monkeypatch):
    """A timed-out waiter must not return budget the resolver still uses."""
    assert _drain_resolver_pool()["in_flight"] == 0
    gate = threading.Event()
    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", _gated_resolver(gate, []))
    try:
        for index in range(safe_fetch.MAX_DNS_OUTSTANDING):
            started = time.monotonic()
            with pytest.raises(FetchAbortedError):
                safe_fetch.fetch_document(f"http://slow{index}.example/", timeout=0.3)
            # The waiter returned on time even though the lookup never ended.
            assert time.monotonic() - started < 5

        stats = safe_fetch.resolver_stats()
        # Every waiter gave up, yet every resolution is still with the resolver:
        # the budget must not have been handed back early.
        assert stats["in_flight"] == safe_fetch.MAX_DNS_OUTSTANDING
        assert stats["running"] + stats["queued"] == safe_fetch.MAX_DNS_OUTSTANDING

        # While the budget is exhausted a further request is refused, not
        # queued behind the abandoned work.
        started = time.monotonic()
        with pytest.raises(safe_fetch.ResolverBusyError):
            safe_fetch.fetch_document("http://one-too-many.example/", timeout=2.0)
        assert time.monotonic() - started < 2, "the refusal was not immediate"
    finally:
        gate.set()


def test_resolver_budget_returns_only_when_the_lookup_really_ends(monkeypatch):
    """The budget comes back when the abandoned lookup really finishes."""
    assert _drain_resolver_pool()["in_flight"] == 0
    gate = threading.Event()
    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", _gated_resolver(gate, []))
    try:
        with pytest.raises(FetchAbortedError):
            safe_fetch.fetch_document("http://slow.example/", timeout=0.3)
        # The abandoned resolution still holds its budget slot.
        assert safe_fetch.resolver_stats()["in_flight"] == 1
    finally:
        gate.set()

    assert _drain_resolver_pool()["in_flight"] == 0
    # The budget is back: the next resolution runs to completion.
    addresses = safe_fetch.resolve_public_addresses(
        "next.example", 443, time.monotonic() + 5
    )
    assert addresses == [PUBLIC_IP]


def test_resolver_pool_is_bounded_under_repeated_timeouts(monkeypatch):
    """Repeated timeouts cannot grow the pool or its queue without limit."""
    assert _drain_resolver_pool()["in_flight"] == 0
    gate = threading.Event()
    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", _gated_resolver(gate, []))
    try:
        for index in range(safe_fetch.MAX_DNS_OUTSTANDING):
            with pytest.raises(FetchAbortedError):
                safe_fetch.fetch_document(f"http://flood{index}.example/", timeout=0.2)

        stats = safe_fetch.resolver_stats()
        assert stats["workers"] <= safe_fetch.MAX_DNS_WORKERS
        assert stats["in_flight"] == safe_fetch.MAX_DNS_OUTSTANDING
        assert len(_dns_threads()) <= safe_fetch.MAX_DNS_WORKERS

        threads_before = len(_dns_threads())
        for _ in range(25):
            with pytest.raises(safe_fetch.ResolverBusyError):
                safe_fetch.resolve_public_addresses(
                    "flood.example", 80, time.monotonic() + 0.5
                )

        stats = safe_fetch.resolver_stats()
        assert len(_dns_threads()) == threads_before, "a refusal created a thread"
        assert stats["workers"] <= safe_fetch.MAX_DNS_WORKERS
        assert stats["queued"] <= safe_fetch.MAX_DNS_OUTSTANDING
        assert stats["in_flight"] == safe_fetch.MAX_DNS_OUTSTANDING
    finally:
        gate.set()
