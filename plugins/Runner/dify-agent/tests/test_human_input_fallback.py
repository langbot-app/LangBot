"""Dify human-input forms on platforms that cannot render the whole form at once."""

import pytest
from components.runner import default as runner_module
from components.runner.default import DefaultRunner
from langbot_plugin.api.entities.builtin.runner import (
    InteractionNotSupportedError,
    InteractionResult,
    InteractionSubmission,
)

# Payload shape emitted by Dify 1.18.0 for a paragraph input with approve / reject actions.
EVENT = {
    "event": "human_input_required",
    "workflow_run_id": "run-1",
    "data": {
        "form_id": "form-1",
        "node_id": "hi",
        "node_title": "Approval",
        "form_content": "Comment: {{#$output.comment#}}",
        "inputs": [
            {
                "output_variable_name": "comment",
                "type": "paragraph",
                "default": {"type": "constant", "selector": [], "value": ""},
            }
        ],
        "actions": [
            {"id": "approve", "title": "Approve", "button_style": "primary"},
            {"id": "reject", "title": "Reject", "button_style": "default"},
        ],
        "form_token": "token-1",
        "approval_channels": ["console"],
        "resolved_default_values": {},
    },
}


class Ctx:
    def __init__(self, answers, whole_form_supported=False):
        self.answers = list(answers)
        self.whole_form_supported = whole_form_supported
        self.requests = []
        self.run_id = "run"

    async def request_interaction(self, request, timeout, on_unsupported):
        self.requests.append(request)
        if len(request.fields) > 1 and not self.whole_form_supported:
            raise InteractionNotSupportedError([{"path": "fields", "reason": "too_many_fields"}])
        values, action_id = self.answers.pop(0)
        submission = InteractionSubmission(interaction_id=request.interaction_id, values=values, action_id=action_id)
        return InteractionResult(status="submitted", submission=submission)


class Client:
    def __init__(self):
        self.submitted = None

    async def workflow_submit(self, **kwargs):
        self.submitted = kwargs
        yield {"event": "workflow_finished", "data": {"outputs": {"action": kwargs["action"]}}}


async def _run(ctx):
    client = Client()
    runner = DefaultRunner.__new__(DefaultRunner)
    results = [item async for item in runner._wait_and_resume_workflow(ctx, client, EVENT, "user", False)]
    return client, results


@pytest.mark.asyncio
async def test_field_and_actions_are_asked_one_by_one_when_the_form_is_unsupported():
    ctx = Ctx(answers=[({"field_1": "looks good"}, None), ({}, "action_2")])

    client, results = await _run(ctx)

    whole, field_step, action_step = ctx.requests
    assert [field.type for field in whole.fields] == ["textarea", "select"]
    assert [field.id for field in field_step.fields] == ["field_1"]
    assert field_step.actions == []
    assert action_step.fields == []
    assert [(action.id, action.label) for action in action_step.actions] == [
        ("action_1", "Approve"),
        ("action_2", "Reject"),
    ]
    assert len({request.interaction_id for request in ctx.requests}) == 3
    assert client.submitted["inputs"] == {"comment": "looks good"}
    assert client.submitted["action"] == "reject"
    assert client.submitted["form_token"] == "token-1"
    assert results[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_native_whole_form_is_used_when_supported():
    ctx = Ctx(
        answers=[({"field_1": "ok", "_dify_action": "action_1"}, None)],
        whole_form_supported=True,
    )

    client, _ = await _run(ctx)

    assert len(ctx.requests) == 1
    assert client.submitted["inputs"] == {"comment": "ok"}
    assert client.submitted["action"] == "approve"


@pytest.mark.asyncio
async def test_single_unsupported_field_still_fails():
    event = {
        **EVENT,
        "data": {**EVENT["data"], "actions": [], "inputs": [{"output_variable_name": "doc", "type": "file"}]},
    }
    ctx = Ctx(answers=[])

    async def unsupported(request, timeout, on_unsupported):
        raise InteractionNotSupportedError([{"path": "fields[0].type", "reason": "unsupported_field_type"}])

    ctx.request_interaction = unsupported
    runner = DefaultRunner.__new__(DefaultRunner)
    with pytest.raises(InteractionNotSupportedError):
        [item async for item in runner._wait_and_resume_workflow(ctx, Client(), event, "user", False)]


def test_module_exports_dify_reason_parser():
    assert runner_module._human_input_reason(EVENT)["form_token"] == "token-1"
