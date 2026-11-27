from __future__ import annotations

import tempfile
from pathlib import Path

from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.security import WorkspaceDebugTokenStore


def test_workspace_debug_tokens_sliding_expiration():
    now = [1000.0]
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "tokens.json"
        store = WorkspaceDebugTokenStore(
            clock=lambda: now[0],
            ttl_seconds=3600,
            storage_path=storage_path,
        )
        ctx = ActionContext(
            instance_uuid="inst-1",
            workspace_uuid="ws-1",
            placement_generation=1,
        )
        cred = store.issue(ctx)
        token = cred.token

        # Advance 30 minutes (well within 60m TTL)
        now[0] += 1800
        # binding_for_token slides the expiration window by 3600 from now (now is 2800 -> expires 6400)
        assert store.binding_for_token(token) is not None

        # Advance another 45 minutes (total 75m since initial issue, which would have expired without sliding)
        now[0] += 2700  # now is 5500, which is < 6400
        assert store.binding_for_token(token) is not None


def test_workspace_debug_tokens_persistence():
    now = [1000.0]
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "tokens.json"
        store1 = WorkspaceDebugTokenStore(
            clock=lambda: now[0],
            ttl_seconds=3600,
            storage_path=storage_path,
        )
        ctx = ActionContext(
            instance_uuid="inst-1",
            workspace_uuid="ws-1",
            placement_generation=1,
        )
        cred = store1.issue(ctx)
        token = cred.token

        # Create new store instance pointing to same file
        store2 = WorkspaceDebugTokenStore(
            clock=lambda: now[0],
            ttl_seconds=3600,
            storage_path=storage_path,
        )
        binding = store2.binding_for_token(token)
        assert binding is not None
        assert binding.workspace_uuid == "ws-1"
