"""Application wiring that makes the Harness WebSocket endpoint reachable.

The route in ``api/http/controller/main.py`` deliberately refuses to start when
its dependencies are absent, so without this module a real instance serves
``/api/v1/harness/ws`` but closes every connection with 1013. Everything the
route needs is injected here rather than imported by the controller, which keeps
the HTTP layer free of persistence and crypto construction.
"""

from .binding import HarnessBindings
from .crypto.transport import HarnessTransportFactory, ReplayGuard
from .oauth import HarnessOAuthService


async def _client_key_lookup(ap, harness_id: str, device_kid: str):
    """Return the pinned static keys of an enrolled device, or None."""
    return await HarnessOAuthService(ap).lookup_device(harness_id, device_kid)


async def install(ap) -> None:
    """Attach the transport for a configured Harness instance."""
    try:
        service = HarnessBindings(ap)
    except ValueError:
        return
    try:
        await service.ensure_instance_key()
    except Exception as exc:
        # Registration can still provision the key once persistence recovers.
        ap.logger.warning('Harness instance identity was not initialized: %s', exc)

    async def lookup(harness_id: str, device_kid: str):
        return await _client_key_lookup(ap, harness_id, device_kid)

    ap.harness_transport_factory = HarnessTransportFactory(ap, lookup, ReplayGuard())
