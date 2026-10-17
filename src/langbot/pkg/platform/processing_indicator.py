"""Optional platform processing status around actual processor execution."""

import contextlib


@contextlib.asynccontextmanager
async def processing_indicator(adapter, target_type, target_id):
    factory = getattr(type(adapter), 'processing_indicator', None)
    if callable(factory) and target_type and target_id is not None:
        async with factory(adapter, target_type, str(target_id)):
            yield
    else:
        yield
