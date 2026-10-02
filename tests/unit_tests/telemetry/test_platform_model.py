from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from langbot.pkg.telemetry.platform import observe_adapter


class ModelAdapter(BaseModel):
    def get_supported_apis(self):
        return ['send_message']

    async def send_message(self):
        return {'message_id': 'ok'}


@pytest.mark.asyncio
async def test_model_adapter_instrumentation_is_instance_local():
    first, second = ModelAdapter(), ModelAdapter()
    ap = SimpleNamespace(telemetry=None)
    observe_adapter(ap, None, first)
    wrapped = first.send_message
    observe_adapter(ap, None, first)
    assert first.send_message is wrapped
    assert not getattr(second, '_execution_observed', False)
    assert await first.send_message() == {'message_id': 'ok'}
    assert await second.send_message() == {'message_id': 'ok'}
