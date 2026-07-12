"""HMAC signing utilities for the HTTP Bot adapter.

A dependency-free, symmetric HMAC-SHA256 scheme used in *both* directions:

    signing_string = "{timestamp}." + raw_body_bytes
    signature      = "sha256=" + hex(HMAC_SHA256(secret, signing_string))

Inbound requests are signed by the caller and verified here; outbound
callbacks are signed here and verified by the caller. The scheme is trivial to
reproduce in any language (see docs/platforms/http-bot.md for JS/curl).
"""

from __future__ import annotations

import hashlib
import hmac
import time

# Header names (kept here so adapter + clients agree on a single source).
HEADER_TIMESTAMP = 'X-LB-Timestamp'
HEADER_SIGNATURE = 'X-LB-Signature'
HEADER_IDEMPOTENCY = 'X-LB-Idempotency-Key'

# Maximum allowed clock skew between signer and verifier (seconds).
DEFAULT_REPLAY_WINDOW = 300


def compute_signature(secret: str, body: bytes, timestamp: str | int) -> str:
    """Compute the ``sha256=<hex>`` signature for *body* at *timestamp*.

    Args:
        secret: Shared HMAC secret.
        body: Raw request body bytes (exactly as sent on the wire).
        timestamp: Unix timestamp (seconds) as str or int.

    Returns:
        The signature string, e.g. ``sha256=ab12...``.
    """
    signing_string = f'{timestamp}.'.encode() + body
    digest = hmac.new(secret.encode(), signing_string, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def sign(secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, str]:
    """Produce ``(timestamp, signature)`` for an outbound request.

    Args:
        secret: Shared HMAC secret.
        body: Raw request body bytes.
        timestamp: Optional fixed timestamp; defaults to ``int(time.time())``.

    Returns:
        ``(timestamp_str, signature_str)``.
    """
    ts = str(timestamp if timestamp is not None else int(time.time()))
    return ts, compute_signature(secret, body, ts)


def verify(
    secret: str,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    replay_window: int = DEFAULT_REPLAY_WINDOW,
) -> tuple[bool, str]:
    """Verify an inbound signature.

    Args:
        secret: Shared HMAC secret.
        body: Raw request body bytes.
        timestamp: Value of the timestamp header.
        signature: Value of the signature header.
        replay_window: Max allowed skew in seconds.

    Returns:
        ``(ok, reason)``. ``reason`` is empty when ``ok`` is True, otherwise a
        short machine-friendly cause (``missing_headers`` / ``bad_timestamp`` /
        ``expired`` / ``signature_mismatch``).
    """
    if not timestamp or not signature:
        return False, 'missing_headers'

    try:
        ts_int = int(float(timestamp))
    except (ValueError, TypeError):
        return False, 'bad_timestamp'

    if abs(int(time.time()) - ts_int) > replay_window:
        return False, 'expired'

    expected = compute_signature(secret, body, timestamp)
    if not hmac.compare_digest(expected, signature):
        return False, 'signature_mismatch'

    return True, ''
