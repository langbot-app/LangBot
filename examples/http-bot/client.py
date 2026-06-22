#!/usr/bin/env python3
"""LangBot HTTP Bot adapter — reference client (Python).

Two things in one file:

1. ``push()`` / ``push_sync()`` — send a message into a LangBot ``http_bot`` bot.
2. A tiny Flask callback receiver that verifies signatures and prints replies,
   so you can watch N->1 aggregation and 1->M multi-reply working live.

Usage
-----
    pip install flask requests

    # Terminal 1 — start the callback receiver (this is your callback_url):
    python client.py serve --port 8900 --secret SHARED_SECRET

    # Terminal 2 — push a message (async; reply lands on the receiver):
    python client.py push \
        --url   https://your-langbot/bots/<BOT_UUID> \
        --secret SHARED_SECRET \
        --session ticket-10293 \
        --text "Export keeps failing on the dashboard."

    # Or push and block for the collapsed reply (sync convenience mode):
    python client.py sync --url https://your-langbot/bots/<BOT_UUID> \
        --secret SHARED_SECRET --session ticket-10293 --text "hi"

The signing scheme is HMAC-SHA256 over ``"{timestamp}." + raw_body``; see
``sign()`` below — it is intentionally tiny and easy to port.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import uuid

HEADER_TIMESTAMP = 'X-LB-Timestamp'
HEADER_SIGNATURE = 'X-LB-Signature'
HEADER_IDEMPOTENCY = 'X-LB-Idempotency-Key'
REPLAY_WINDOW = 300


def sign(secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, str]:
    """Return (timestamp, signature) for *body*."""
    ts = str(timestamp if timestamp is not None else int(time.time()))
    mac = hmac.new(secret.encode(), f'{ts}.'.encode() + body, hashlib.sha256)
    return ts, 'sha256=' + mac.hexdigest()


def verify(secret: str, body: bytes, timestamp: str | None, signature: str | None) -> bool:
    """Verify an inbound signature (used by the callback receiver)."""
    if not timestamp or not signature:
        return False
    try:
        if abs(int(time.time()) - int(float(timestamp))) > REPLAY_WINDOW:
            return False
    except ValueError:
        return False
    _, expected = sign(secret, body, int(float(timestamp)))
    return hmac.compare_digest(expected, signature)


def _post(url: str, secret: str, payload: dict, idempotency: bool = True):
    import requests

    body = json.dumps(payload, ensure_ascii=False).encode()
    ts, sig = sign(secret, body)
    headers = {
        'Content-Type': 'application/json',
        HEADER_TIMESTAMP: ts,
        HEADER_SIGNATURE: sig,
    }
    if idempotency:
        headers[HEADER_IDEMPOTENCY] = uuid.uuid4().hex
    resp = requests.post(url, data=body, headers=headers, timeout=30)
    print(f'-> {resp.status_code} {resp.text}')
    return resp


def push(url: str, secret: str, session: str, text: str, session_type: str = 'person'):
    """Fire-and-collect: returns 202 immediately; reply arrives on your callback."""
    payload = {
        'session_id': session,
        'session_type': session_type,
        'message': [{'type': 'Plain', 'text': text}],
    }
    return _post(url.rstrip('/'), secret, payload)


def push_sync(url: str, secret: str, session: str, text: str, session_type: str = 'person'):
    """Blocking convenience: POST to /sync and get the collapsed reply back."""
    payload = {
        'session_id': session,
        'session_type': session_type,
        'message': [{'type': 'Plain', 'text': text}],
    }
    resp = _post(url.rstrip('/') + '/sync', secret, payload, idempotency=False)
    return resp


def reset(url: str, secret: str, session: str, session_type: str = 'person'):
    """Reset a session's conversation (next message starts fresh)."""
    payload = {'session_id': session, 'session_type': session_type}
    return _post(url.rstrip('/') + '/reset', secret, payload, idempotency=False)


def serve(port: int, secret: str):
    """Run a callback receiver that verifies signatures and prints replies."""
    from flask import Flask, request

    app = Flask(__name__)

    @app.route('/', methods=['POST'])
    def recv():
        raw = request.get_data()
        ok = verify(secret, raw, request.headers.get(HEADER_TIMESTAMP), request.headers.get(HEADER_SIGNATURE))
        if not ok:
            print('!! signature verification FAILED — rejecting')
            return {'error': 'bad signature'}, 401
        data = json.loads(raw)
        text_parts = [c.get('text', '') for c in data.get('message', []) if c.get('type') == 'Plain']
        marker = 'FINAL' if data.get('is_final') else 'part '
        print(
            f'[{marker}] session={data["session_id"]} seq={data["sequence"]} '
            f'reply_to={data.get("reply_to")}: {" ".join(text_parts)}'
        )
        return {'ok': True}

    print(f'callback receiver listening on http://0.0.0.0:{port}/  (Ctrl-C to stop)')
    app.run(host='0.0.0.0', port=port)


def main(argv=None):
    p = argparse.ArgumentParser(description='LangBot HTTP Bot reference client')
    sub = p.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('serve', help='run the callback receiver')
    sp.add_argument('--port', type=int, default=8900)
    sp.add_argument('--secret', required=True)

    for name in ('push', 'sync', 'reset'):
        c = sub.add_parser(name)
        c.add_argument('--url', required=True, help='https://host/bots/<BOT_UUID>')
        c.add_argument('--secret', required=True)
        c.add_argument('--session', required=True)
        c.add_argument('--session-type', default='person', choices=['person', 'group'])
        if name != 'reset':
            c.add_argument('--text', required=True)

    args = p.parse_args(argv)
    if args.cmd == 'serve':
        serve(args.port, args.secret)
    elif args.cmd == 'push':
        push(args.url, args.secret, args.session, args.text, args.session_type)
    elif args.cmd == 'sync':
        push_sync(args.url, args.secret, args.session, args.text, args.session_type)
    elif args.cmd == 'reset':
        reset(args.url, args.secret, args.session, args.session_type)


if __name__ == '__main__':
    sys.exit(main())
