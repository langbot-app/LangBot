from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.telemetry.telemetry import TelemetryManager


@pytest.mark.asyncio
async def test_send_tasks_are_scoped_to_manager_instance(monkeypatch):
    async def fake_send(self, payload):
        return payload

    monkeypatch.setattr(TelemetryManager, 'send', fake_send)

    first = TelemetryManager(SimpleNamespace())
    second = TelemetryManager(SimpleNamespace())

    assert first.send_tasks is not second.send_tasks

    await first.start_send_task({'event': 'first'})
    await first.send_tasks[0]

    assert len(first.send_tasks) == 1
    assert second.send_tasks == []
