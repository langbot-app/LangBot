"""Validate explicit endpoints. Network reachability remains a Host egress policy.

Private HTTP(S) service endpoints are intentional for self-hosted vendors; this
syntax check is NOT an SSRF sandbox or permission to access other workspaces.
"""

from urllib.parse import urlsplit


def endpoint(value, *, query=False):
    try:
        if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or (parsed.query and not query)
        ):
            raise ValueError
        _ = parsed.port
    except (ValueError, TypeError):
        raise ValueError("Endpoint must be an HTTP(S) URL without credentials or fragment") from None
    return value
