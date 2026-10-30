from __future__ import annotations

import pytest

from tests.test_native_parity_external import collect, ctx, kind, load_runner


def final_texts(results):
    return [
        result.data["chunk"]["content"]
        for result in results
        if kind(result) == "message.delta" and result.data["chunk"].get("is_final")
    ]


def test_legacy_agent_empty_thought_keeps_answer_until_message_end():
    with load_runner("dify-agent") as (_, runner):

        class Client:
            async def chat_messages(self, **kwargs):
                yield {"event": "agent_thought", "tool": "", "observation": ""}
                yield {"event": "agent_message", "answer": "23"}
                yield {"event": "agent_thought", "tool": "", "observation": ""}
                yield {"event": "message_end"}

        results = collect(runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], "agent", False))
        assert final_texts(results) == ["23"]


@pytest.mark.parametrize("summary", ["23", "final answer", None])
def test_workflow_terminal_summary_owns_streamed_text(summary):
    with load_runner("dify-agent") as (_, runner):

        class Client:
            async def workflow_run(self, **kwargs):
                yield {"event": "workflow_started", "data": {"workflow_run_id": "workflow"}}
                yield {"event": "text_chunk", "data": {"text": "2"}}
                yield {"event": "text_chunk", "data": {"text": "3"}}
                yield {"event": "workflow_finished", "data": {"outputs": {"summary": summary}}}

        results = collect(runner._run_workflow(ctx(), Client(), {}, "hi", "user", [], False))
        assert final_texts(results) == [summary or "23"]
        assert kind(results[-1]) == "run.completed"


def test_workflow_answer_node_owns_streamed_text():
    with load_runner("dify-agent") as (_, runner):

        class Client:
            async def workflow_run(self, **kwargs):
                yield {"event": "text_chunk", "data": {"text": "23"}}
                yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "23"}}}
                yield {"event": "workflow_finished", "data": {"outputs": {}}}

        results = collect(runner._run_workflow(ctx(), Client(), {}, "hi", "user", [], False))
        assert final_texts(results) == ["23"]


@pytest.mark.parametrize("app_type", ["chat", "chatflow"])
def test_chatflow_answer_snapshot_and_message_end_complete_once(app_type):
    with load_runner("dify-agent") as (_, runner):

        class Client:
            async def chat_messages(self, **kwargs):
                yield {"event": "workflow_started", "data": {"workflow_run_id": "workflow"}}
                yield {"event": "message", "answer": "2"}
                yield {"event": "message", "answer": "3"}
                yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "23"}}}
                yield {"event": "message_end"}
                yield {"event": "workflow_finished", "data": {"outputs": {"answer": "23"}}}

        results = collect(runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], app_type, False))
        assert final_texts(results) == ["23"]
