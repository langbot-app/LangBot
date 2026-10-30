"""Scoped upstream identity follows the current trusted invocation binding."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.runner.default import DefaultRunner, DifyAPIError  # noqa: E402
from pkg.scoped_identity import scoped_identity  # noqa: E402


def _binding(installation: str, *, workspace: str = "workspace-1", instance: str = "instance-1", revision: int = 1):
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def _ctx(workspace_id: str | None = None):
    return SimpleNamespace(conversation=SimpleNamespace(workspace_id=workspace_id))


def _runner(handler):
    return SimpleNamespace(_plugin_runtime_handler=handler)


def _expected(binding: InstallationBinding, local_id: str) -> str:
    scope = [binding.instance_uuid, binding.workspace_uuid, binding.installation_uuid]
    encoded = json.dumps([scope, local_id], ensure_ascii=False, separators=(",", ":")).encode()
    return "lb_" + hashlib.sha256(encoded).hexdigest()


def test_identity_does_not_collide_across_installations():
    first_handler, second_handler = SimpleNamespace(), SimpleNamespace()
    with bind_invocation(first_handler, binding=_binding("installation-a")):
        first = scoped_identity(_runner(first_handler), _ctx(), "local-1")
    with bind_invocation(second_handler, binding=_binding("installation-b")):
        second = scoped_identity(_runner(second_handler), _ctx(), "local-1")
    assert first == _expected(_binding("installation-a"), "local-1")
    assert second == _expected(_binding("installation-b"), "local-1")
    assert first != second


def test_identity_is_stable_for_the_same_binding():
    def compute(revision: int) -> str:
        handler = SimpleNamespace()
        with bind_invocation(handler, binding=_binding("installation-a", revision=revision)):
            return scoped_identity(_runner(handler), _ctx(), "local-1")

    assert compute(1) == compute(1)
    # Only the installation scope matters: a worker upgrade must not rename upstream state.
    assert compute(1) == compute(7)


def test_invocation_binding_wins_over_connection_binding():
    handler = SimpleNamespace(bound_action_context=_binding("installation-legacy"))
    with bind_invocation(handler, binding=_binding("installation-current")):
        identity = scoped_identity(_runner(handler), _ctx(), "local-1")
    assert identity == _expected(_binding("installation-current"), "local-1")


def test_connection_binding_is_used_without_an_invocation_binding(monkeypatch):
    monkeypatch.delenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", raising=False)
    handler = SimpleNamespace(bound_action_context=_binding("installation-dedicated"))
    assert scoped_identity(_runner(handler), _ctx(), "local-1") == _expected(
        _binding("installation-dedicated"), "local-1"
    )


def test_shared_profile_without_binding_refuses(monkeypatch):
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", "shared")
    handler = SimpleNamespace()
    with pytest.raises(RuntimeError):
        scoped_identity(_runner(handler), _ctx(workspace_id="workspace-1"), "local-1")


def test_dedicated_falls_back_to_workspace_then_legacy_local_id(monkeypatch):
    monkeypatch.delenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", raising=False)
    handler = SimpleNamespace()
    scoped = scoped_identity(_runner(handler), _ctx(workspace_id="workspace-1"), "local-1")
    assert scoped.startswith("lb_")
    assert scoped != scoped_identity(_runner(handler), _ctx(workspace_id="workspace-2"), "local-1")
    assert scoped_identity(_runner(handler), _ctx(), "local-1") == "local-1"


# --- Dify continuation owner -------------------------------------------------


def _dify_context():
    return SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            launcher_type="group",
            launcher_id="launcher-1",
            workspace_id=None,
        ),
        actor=SimpleNamespace(actor_id="actor-1"),
        config={"base-url": "https://dify.invalid"},
    )


def _dify_runner(handler):
    runner = object.__new__(DefaultRunner)
    runner._plugin_runtime_handler = handler
    return runner


def _legacy_owner(binding: InstallationBinding, subject: str) -> str:
    scope = [binding.instance_uuid, binding.workspace_uuid, binding.installation_uuid]
    encoded = json.dumps([scope, subject], ensure_ascii=False, separators=(",", ":")).encode()
    return "lb_" + hashlib.sha256(encoded).hexdigest()


class _StorageAPI:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def get_plugin_storage(self, key: str) -> bytes:
        return self._payload


def _continuation_payload(owner: str) -> bytes:
    return json.dumps(
        {
            "interaction_id": "interaction-1",
            "version": 1,
            "owner": owner,
            "expires_at": 4_000_000_000,
        }
    ).encode("utf-8")


@pytest.mark.asyncio
async def test_resume_concurrency_key_uses_the_same_owner_and_binding():
    ctx = _dify_context()
    handler = SimpleNamespace()
    runner = _dify_runner(handler)
    binding = _binding("installation-a")
    with bind_invocation(handler, binding=binding):
        owner = runner._continuation_owner(ctx)
        assert owner == _expected(binding, runner._continuation_subject(ctx))
        # Pre-seeding the exact key proves _resume_workflow derives it from the same
        # invocation binding and owner rather than a different scope.
        runner._active_resumes = {(binding, owner, "interaction-1")}
        stream = runner._resume_workflow(
            ctx,
            client=None,
            submission=SimpleNamespace(interaction_id="interaction-1"),
            remove_think=False,
        )
        with pytest.raises(DifyAPIError):
            await stream.__anext__()


@pytest.mark.asyncio
async def test_legacy_owner_is_accepted_and_migrated():
    ctx = _dify_context()
    legacy_binding = _binding("installation-legacy")
    handler = SimpleNamespace(bound_action_context=legacy_binding)
    runner = _dify_runner(handler)
    subject = runner._continuation_subject(ctx)
    runner.get_run_api = lambda _ctx: _StorageAPI(_continuation_payload(_legacy_owner(legacy_binding, subject)))
    binding = _binding("installation-current")
    with bind_invocation(handler, binding=binding):
        current_owner = runner._continuation_owner(ctx)
        assert current_owner != _legacy_owner(legacy_binding, subject)
        continuation = await runner._load_interaction_continuation(ctx, "interaction-1")
    assert continuation["owner"] == current_owner


@pytest.mark.asyncio
async def test_foreign_owner_is_rejected():
    ctx = _dify_context()
    runner = _dify_runner(SimpleNamespace())
    runner.get_run_api = lambda _ctx: _StorageAPI(_continuation_payload("lb_" + "0" * 64))
    with pytest.raises(DifyAPIError):
        await runner._load_interaction_continuation(ctx, "interaction-1")
