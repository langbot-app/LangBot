"""Continuation feature parity with owner-bound, expiring new-format records."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from langbot_plugin.api.entities.builtin.runner import InteractionSubmission

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_traditional_runner_protocol_fixes import (
    _collect_async,
    _ctx,
    _FakePluginStorage,
    _load_runner_module,
    _type,
)

if os.environ.get("HTTP_RUNNER_SOURCE_ROOT"):
    _load_runner_module.__globals__["ROOT"] = Path(os.environ["HTTP_RUNNER_SOURCE_ROOT"])


def test_dify_interaction_resume_submits_mapped_values_and_clears_continuation() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-test"
    storage_key = module._interaction_storage_key(interaction_id)
    storage.values[storage_key] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-private",
            "workflow_run_id": "workflow-private",
            "user": "user_1",
            "field_map": {"field_1": "priority"},
            "action_map": {"action_1": "approve-private"},
            "default_inputs": {"comment": "default"},
        }
    ).encode()
    captured: dict[str, Any] = {}

    class FakeClient:
        async def workflow_submit(self, **kwargs):
            captured.update(kwargs)
            yield {
                "event": "workflow_finished",
                "data": {"error": None, "outputs": {"summary": "Approved"}},
            }

    submission = InteractionSubmission(
        interaction_id=interaction_id,
        action_id="action_1",
        values={"field_1": "high"},
    )
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), FakeClient(), submission, False)))

    assert captured == {
        "form_token": "form-private",
        "workflow_run_id": "workflow-private",
        "inputs": {"comment": "default", "priority": "high"},
        "user": "user_1",
        "action": "approve-private",
    }
    assert [_type(result) for result in results] == ["message.delta", "run.completed"]
    assert storage_key in storage.deleted
    assert storage_key not in storage.values


def test_dify_field_submission_advances_to_action_without_calling_provider() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-field"
    storage.values[module._interaction_storage_key(interaction_id)] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-private",
            "workflow_run_id": "workflow-private",
            "user": "user_1",
            "field_map": {"field_1": "priority"},
            "action_map": {"action_1": "approve-private"},
            "default_inputs": {},
            "title": "Manual review",
            "description": "Review it",
            "fallback_text": "Review it",
            "phase": "field",
            "current_fields": [
                {
                    "id": "field_1",
                    "label": "Priority",
                    "type": "select",
                    "required": True,
                    "options": [{"value": "high", "label": "High"}],
                }
            ],
            "remaining_fields": [],
            "interaction_actions": [{"id": "action_1", "label": "Approve", "style": "primary"}],
        }
    ).encode()

    class ProviderMustNotRun:
        def workflow_submit(self, **kwargs):
            raise AssertionError("provider must not resume before the action step")

    submission = InteractionSubmission(interaction_id=interaction_id, values={"field_1": "high"})
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), ProviderMustNotRun(), submission, False)))

    assert [_type(result) for result in results] == ["action.requested"]
    request = results[0].data["payload"]
    assert request["fields"] == []
    assert request["actions"][0]["label"] == "Approve"
    continuation = json.loads(storage.values[module._interaction_storage_key(request["interaction_id"])])
    assert continuation["default_inputs"] == {"priority": "high"}


def test_dify_interaction_resume_can_pause_again() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-first"
    old_key = module._interaction_storage_key(interaction_id)
    storage.values[old_key] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-1",
            "workflow_run_id": "workflow-1",
            "user": "user_1",
            "field_map": {},
            "action_map": {"continue": ""},
            "default_inputs": {},
        }
    ).encode()

    class FakeClient:
        async def workflow_submit(self, **kwargs):
            yield {
                "event": "workflow_paused",
                "data": {
                    "workflow_run_id": "workflow-2",
                    "reasons": [
                        {
                            "TYPE": "human_input_required",
                            "form_token": "form-2",
                            "node_title": "Second review",
                            "inputs": [],
                            "actions": [{"id": "done", "title": "Done"}],
                        }
                    ],
                },
            }

    submission = InteractionSubmission(interaction_id=interaction_id, action_id="continue")
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), FakeClient(), submission, False)))

    assert [_type(result) for result in results] == ["action.requested"]
    new_interaction_id = results[0].data["payload"]["interaction_id"]
    assert new_interaction_id != interaction_id
    assert old_key in storage.deleted
    assert module._interaction_storage_key(new_interaction_id) in storage.values
