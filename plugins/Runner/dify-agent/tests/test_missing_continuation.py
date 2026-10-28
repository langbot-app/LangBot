import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from components.runner.default import DefaultRunner, _interaction_storage_key
from langbot_plugin.entities.io.errors import ActionCallError
from pkg.dify_client import DifyAPIError


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["", "ActionCallError: ", "ActionCallError: ActionCallError: "])
async def test_missing_rpc_key(prefix):
    key = _interaction_storage_key("missing")
    api = SimpleNamespace(
        get_plugin_storage=AsyncMock(side_effect=ActionCallError(prefix + f"Storage with key {key} not found"))
    )
    runner = SimpleNamespace(get_run_api=lambda ctx: api)
    with pytest.raises(DifyAPIError) as exc:
        await DefaultRunner._load_interaction_continuation(runner, None, "missing")
    assert exc.value.code == "dify.interaction_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ActionCallError("permission denied"),
        ActionCallError("Storage with key other not found"),
        TimeoutError("timeout"),
    ],
)
async def test_other_errors_propagate(error):
    runner = SimpleNamespace(get_run_api=lambda ctx: SimpleNamespace(get_plugin_storage=AsyncMock(side_effect=error)))
    with pytest.raises(type(error)) as exc:
        await DefaultRunner._load_interaction_continuation(runner, None, "missing")
    assert exc.value is error


@pytest.mark.asyncio
async def test_corrupt_json_propagates():
    runner = SimpleNamespace(
        get_run_api=lambda ctx: SimpleNamespace(get_plugin_storage=AsyncMock(return_value=b"broken"))
    )
    with pytest.raises(json.JSONDecodeError):
        await DefaultRunner._load_interaction_continuation(runner, None, "missing")
