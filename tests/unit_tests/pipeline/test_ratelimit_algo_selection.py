"""
RateLimit algorithm-selection unit tests.

Verifies that RateLimit.initialize reads the algorithm name from
pipeline_config['safety']['rate-limit']['algo'], defaults to 'fixwin' when
absent (backward compatible), and raises ValueError for an unknown algorithm.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from importlib import import_module


def get_modules():
    """Lazy import to ensure proper initialization order."""
    ratelimit = import_module('langbot.pkg.pipeline.ratelimit.ratelimit')
    fixedwin = import_module('langbot.pkg.pipeline.ratelimit.algos.fixedwin')
    valkey_fixwin = import_module('langbot.pkg.pipeline.ratelimit.algos.valkey_fixwin')
    return ratelimit, fixedwin, valkey_fixwin


@pytest.mark.asyncio
async def test_default_is_fixwin(mock_app):
    """Empty config selects in-memory FixedWindowAlgo."""
    ratelimit, fixedwin, _ = get_modules()

    stage = ratelimit.RateLimit(mock_app)
    await stage.initialize({})

    assert isinstance(stage.algo, fixedwin.FixedWindowAlgo)


@pytest.mark.asyncio
async def test_default_is_fixwin_when_algo_key_absent(mock_app):
    """Config with rate-limit but no `algo` key still defaults to fixwin."""
    ratelimit, fixedwin, _ = get_modules()

    stage = ratelimit.RateLimit(mock_app)
    await stage.initialize({'safety': {'rate-limit': {'window-length': 60}}})

    assert isinstance(stage.algo, fixedwin.FixedWindowAlgo)


@pytest.mark.asyncio
async def test_selects_valkey_fixwin(mock_app):
    """Config algo=valkey_fixwin selects ValkeyFixedWindowAlgo."""
    ratelimit, _, valkey_fixwin = get_modules()

    config = {'safety': {'rate-limit': {'algo': 'valkey_fixwin'}}}

    # Patch initialize to avoid any client work during selection.
    with patch.object(valkey_fixwin.ValkeyFixedWindowAlgo, 'initialize', new=AsyncMock()):
        stage = ratelimit.RateLimit(mock_app)
        await stage.initialize(config)

    assert isinstance(stage.algo, valkey_fixwin.ValkeyFixedWindowAlgo)


@pytest.mark.asyncio
async def test_unknown_algo_raises(mock_app):
    """Unknown algorithm name raises ValueError."""
    ratelimit, _, _ = get_modules()

    config = {'safety': {'rate-limit': {'algo': 'nope'}}}

    stage = ratelimit.RateLimit(mock_app)
    with pytest.raises(ValueError):
        await stage.initialize(config)
