"""Outbound URL safety checks for server-side fetches (SSRF guard).

The platform adapters fetch URLs that come from inbound platform messages
(attachment URLs, session webhooks, media links). Those values are attacker
influenced, so the server must not be tricked into requesting internal
infrastructure: cloud metadata (169.254.169.254), the cluster network, or
loopback services.

Call :func:`assert_safe_outbound_url` before every such request. It checks the
scheme, rejects literal private/loopback/link-local addresses, and resolves the
hostname so a public-looking name that points at an internal address is
rejected too.
"""

from __future__ import annotations

import ipaddress
import socket
import tempfile
import urllib.parse
from pathlib import Path

_ALLOWED_SCHEMES = ('http', 'https')


class UnsafeOutboundUrlError(ValueError):
    """Raised when an outbound URL would reach a non-public destination."""


def _reject_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Return why this address is not a safe outbound destination, if it is not."""
    mapped = getattr(ip, 'ipv4_mapped', None)
    if mapped is not None:
        ip = mapped

    if ip.is_private:
        return 'private address'
    if ip.is_loopback:
        return 'loopback address'
    if ip.is_link_local:
        return 'link-local address'
    if ip.is_multicast:
        return 'multicast address'
    if ip.is_reserved:
        return 'reserved address'
    if ip.is_unspecified:
        return 'unspecified address'
    return None


def _parse_and_check_scheme(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeOutboundUrlError(f'unsupported URL scheme: {parsed.scheme or "<none>"}')
    if not parsed.hostname:
        raise UnsafeOutboundUrlError('URL has no host')
    return parsed


def _host_allowed(host: str, allowed_domains: tuple[str, ...] | None) -> bool:
    if allowed_domains is None:
        return True
    host = host.lower().rstrip('.')
    for domain in allowed_domains:
        domain = domain.lower().lstrip('.')
        if host == domain or host.endswith('.' + domain):
            return True
    return False


def assert_safe_outbound_url(
    url: str,
    *,
    allowed_domains: tuple[str, ...] | None = None,
) -> str:
    """Validate an outbound URL, returning it unchanged when it is safe.

    ``allowed_domains`` restricts the destination to those domain suffixes (used
    where the legitimate destination is a fixed platform domain). When omitted,
    any public destination is allowed but internal addresses are still refused.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeOutboundUrlError('URL is empty')

    parsed = _parse_and_check_scheme(url)
    host = parsed.hostname or ''

    if not _host_allowed(host, allowed_domains):
        raise UnsafeOutboundUrlError(f'host is not an allowed destination: {host}')

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        reason = _reject_reason(literal)
        if reason is not None:
            raise UnsafeOutboundUrlError(f'refusing to fetch {host}: {reason}')
        return url

    # Resolve so a public-looking name pointing at an internal address is caught.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80))
    except socket.gaierror as exc:
        raise UnsafeOutboundUrlError(f'cannot resolve host {host}: {exc}') from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeOutboundUrlError(f'host {host} did not resolve to an address')

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        reason = _reject_reason(ip)
        if reason is not None:
            raise UnsafeOutboundUrlError(f'refusing to fetch {host} ({address}): {reason}')

    return url


def assert_safe_local_media_path(file_path: str, *, allowed_roots: tuple[str, ...] | None = None) -> str:
    """Validate a local file path used as outbound media, returning it resolved.

    Message components can carry a ``path``/``file_path`` field. A platform
    adapter that opens it blindly lets a crafted component read any file the
    process can see (``/etc/passwd``, credentials, another tenant's data) and
    upload it to the chat platform.

    The path must stay inside one of ``allowed_roots`` — by default the LangBot
    data directory and the system temporary directory, which is where plugins and
    the pipeline legitimately write generated media. Symlinks are resolved first,
    so a link pointing outside the root is rejected too.
    """
    from langbot.pkg.utils.paths import get_data_root

    if not isinstance(file_path, str) or not file_path.strip():
        raise UnsafeOutboundUrlError('file path is empty')

    roots = allowed_roots or (get_data_root(), tempfile.gettempdir())
    resolved_roots = []
    for root in roots:
        try:
            resolved_roots.append(Path(root).resolve())
        except OSError:  # pragma: no cover - defensive
            continue

    candidate = Path(file_path)
    if not candidate.is_absolute():
        # Relative paths resolve against an unpredictable cwd; refuse them.
        raise UnsafeOutboundUrlError(f'refusing to read a relative media path: {file_path}')

    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafeOutboundUrlError(f'cannot resolve media path: {file_path}') from exc

    for root in resolved_roots:
        if resolved == root or root in resolved.parents:
            if not resolved.is_file():
                raise UnsafeOutboundUrlError(f'media path is not a regular file: {file_path}')
            return str(resolved)

    raise UnsafeOutboundUrlError(f'refusing to read media path outside the allowed roots: {file_path}')
