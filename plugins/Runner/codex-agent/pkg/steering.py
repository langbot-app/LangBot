"""Run-scoped steering (follow-up input) turn loop for native CLI runners.

Steering lets a runner absorb follow-up user messages that arrive while a run is
still active. When the runner declares ``capabilities.steering: true`` in its
manifest, the Host queues those messages against the active run (keyed by
``run_id``) instead of starting a new run. The runner drains them at turn
boundaries via ``RunnerAPIProxy.steering_pull``.

``run_with_steering`` wraps a single-turn executor and re-invokes it once per
pulled follow-up input, reusing the runner's own session-resume mechanism so
each follow-up continues the same agent session. It forwards every per-turn
result except the intermediate ``run.completed`` events, emitting exactly one
terminal ``run.completed`` after all follow-ups are drained.

The helper is intentionally defensive: if the Host did not authorize steering
for this run (e.g. no conversation scope), or ``steering_pull`` fails, it falls
back to single-turn behavior and never breaks an otherwise-successful run.
"""

from __future__ import annotations

import collections
import typing

from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)
from langbot_plugin.api.entities.builtin.runner.result import RunnerResultType
from langbot_plugin.api.proxies.runner import (
    PermissionDeniedError,
    RunnerAPIProxy,
)

# run_turn(prompt, resume_session_id) -> async generator of RunnerResult for one turn.
RunTurn = typing.Callable[[str, str], typing.AsyncGenerator[RunnerResult, None]]
GetRunApi = typing.Callable[[], RunnerAPIProxy]

# Upper bound on follow-up turns per run. Far above any realistic interactive
# session; the Host steering queue is itself capped (100 items), so this only
# guards against pathological loops.
DEFAULT_MAX_FOLLOWUPS = 256


def steering_enabled(ctx: RunnerContext) -> bool:
    """Return whether the Host authorized ``steering_pull`` for this run."""
    try:
        return bool(ctx.context.available_apis.steering_pull)
    except AttributeError:
        return False


async def _pull_followup_prompts(api: RunnerAPIProxy, mode: str) -> list[str]:
    result = await api.steering_pull(mode=mode)
    prompts: list[str] = []
    for item in result.items:
        try:
            text = item.input.to_text().strip()
        except Exception:
            text = ""
        if text:
            prompts.append(text)
    return prompts


async def run_with_steering(
    ctx: RunnerContext,
    get_run_api: GetRunApi,
    run_turn: RunTurn,
    *,
    initial_prompt: str,
    initial_resume_session_id: str,
    session_state_key: str,
    steering_mode: str = "all",
    max_followups: int = DEFAULT_MAX_FOLLOWUPS,
) -> typing.AsyncGenerator[RunnerResult, None]:
    """Drive ``run_turn`` once per turn, injecting steering follow-ups between turns.

    Args:
        ctx: The current run context.
        get_run_api: Lazily returns the run-scoped API proxy. Only called when
            steering is authorized, so runners that disable Host assets in tests
            are unaffected.
        run_turn: Executes one agent turn for ``(prompt, resume_session_id)`` and
            yields its ``RunnerResult`` stream, terminated by ``run.completed``
            or ``run.failed``.
        initial_prompt: Prompt text for the first turn.
        initial_resume_session_id: Session id to resume for the first turn (may be
            empty to start a fresh session).
        session_state_key: ``state.updated`` key under which the executor reports
            the session id; captured so follow-up turns resume the same session.
        steering_mode: ``"all"`` to drain everything queued each round, or
            ``"one"`` to pull a single item per round.
        max_followups: Safety cap on the number of follow-up turns.
    """
    enabled = steering_enabled(ctx)
    pending: collections.deque[str] = collections.deque()
    prompt = initial_prompt
    resume_session_id = initial_resume_session_id
    terminal: RunnerResult | None = None
    followups = 0

    while True:
        async for result in run_turn(prompt, resume_session_id):
            result_type = result.type.value if isinstance(result.type, RunnerResultType) else str(result.type)
            if result_type == RunnerResultType.STATE_UPDATED.value:
                if result.data.get("key") == session_state_key:
                    new_session_id = str(result.data.get("value") or "").strip()
                    if new_session_id:
                        resume_session_id = new_session_id
                yield result
                continue
            if result_type == RunnerResultType.RUN_FAILED.value:
                # A failed turn ends the run immediately; do not drain steering.
                yield result
                return
            if result_type == RunnerResultType.ACTION_REQUESTED.value:
                # An interaction logically pauses the run. The callback creates
                # a new run, so do not pull steering or synthesize completion.
                yield result
                return
            if result_type == RunnerResultType.RUN_COMPLETED.value:
                # Hold back: only the final turn's completion terminates the run.
                terminal = result
                continue
            yield result

        # The turn completed successfully. Drain any pending follow-ups; only
        # pull more from the Host once the local buffer is empty.
        if not pending:
            if not enabled or followups >= max_followups:
                break
            try:
                pending.extend(await _pull_followup_prompts(get_run_api(), steering_mode))
            except PermissionDeniedError:
                enabled = False
            except Exception:
                # Steering is best-effort and must never break a good run.
                enabled = False
        if not pending:
            break
        prompt = pending.popleft()
        followups += 1

    if terminal is not None:
        yield terminal
    else:
        yield RunnerResult.run_completed(ctx.run_id, finish_reason="stop")
