from __future__ import annotations

from typing import Any


async def is_box_backend_available(ap: Any) -> bool:
    """Return whether the configured Box backend is ready for tool execution."""
    box_service = getattr(ap, 'box_service', None)
    if box_service is None:
        return False
    if not getattr(box_service, 'available', False):
        return False
    try:
        status = await box_service.get_backend_status()
        backend_info = status.get('backend', {})
        return bool(backend_info.get('available', False))
    except Exception:
        return False
