"""Language boundaries for adapter-owned replies outside the Pipeline."""

import functools

from . import DEFAULT_LANGUAGE, language_scope, t
from .workspace import _cache, get_workspace_language


def _owner(adapter):
    logger = getattr(adapter, 'logger', None)
    context = getattr(logger, 'execution_context', None)
    workspace_uuid = getattr(context, 'workspace_uuid', None)
    return getattr(logger, 'ap', None), workspace_uuid if isinstance(workspace_uuid, str) else None


def adapter_t(adapter, message: str, **params) -> str:
    """Synchronous SDK callbacks use the bot's own cached language, never a peer's."""
    ap, workspace_uuid = _owner(adapter)
    cached = _cache(ap).get(workspace_uuid) if ap is not None and workspace_uuid else None
    return t(message, locale=cached[0] if cached else DEFAULT_LANGUAGE, **params)


def localized_adapter(method):
    @functools.wraps(method)
    async def wrapped(self, *args, **kwargs):
        ap, workspace_uuid = _owner(self)
        locale = await get_workspace_language(ap, workspace_uuid) if ap is not None else DEFAULT_LANGUAGE
        with language_scope(locale):
            return await method(self, *args, **kwargs)

    return wrapped
