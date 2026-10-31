#!/usr/bin/env python3
"""Exercise long-lived Core registries and verify that they reach a plateau.

This probe is intentionally separate from the default test suite because the
audit profile creates tens of thousands of historical identities. It uses the
real admission, eviction, and cleanup code while replacing external platform
objects that are irrelevant to registry retention.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import time
import tracemalloc
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from unittest.mock import patch

import psutil

from langbot.pkg.api.http.context import ExecutionContext

# Import the Application graph before taskmgr. The production boot path has
# this same ordering; importing taskmgr first exposes its historical cycle
# through HTTP route annotations.
from langbot.pkg.core import app as _core_app  # noqa: F401
from langbot.pkg.core.taskmgr import AsyncTaskManager
from langbot.pkg.pipeline.pool import QueryPool
from langbot.pkg.pipeline.ratelimit.algos.fixedwin import FixedWindowAlgo
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from langbot.pkg.platform.sources.websocket_adapter import (
    WebSocketMessage,
    WebSocketSession,
)
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.session.sessionmgr import SessionManager
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes


@dataclass(frozen=True, slots=True)
class ProbeScale:
    query_churn_per_phase: int
    session_churn_per_phase: int
    rate_limit_churn_per_phase: int
    task_churn_per_phase: int
    websocket_churn_per_phase: int
    empty_workspace_churn_per_phase: int


SCALES = {
    'quick': ProbeScale(
        query_churn_per_phase=2_500,
        session_churn_per_phase=500,
        rate_limit_churn_per_phase=10_000,
        task_churn_per_phase=1_000,
        websocket_churn_per_phase=500,
        empty_workspace_churn_per_phase=1_000,
    ),
    'audit': ProbeScale(
        query_churn_per_phase=25_000,
        session_churn_per_phase=2_500,
        rate_limit_churn_per_phase=10_000,
        task_churn_per_phase=5_000,
        websocket_churn_per_phase=2_500,
        empty_workspace_churn_per_phase=10_000,
    ),
}


class _ProbeQuery:
    """Small weak-referenceable stand-in for SDK Query construction."""

    def __init__(self, **values):
        self.__dict__.update(values)


class _EmptyResult:
    def all(self) -> list:
        return []


class _EmptyPluginRuntimeHandler:
    async def reconcile_plugin_installations(self, _states: tuple) -> dict:
        return {
            'applied': [],
            'removed': [],
            'missing_artifacts': [],
            'failed_installations': [],
        }

    def unregister_installation_binding(self, _binding) -> None:
        raise AssertionError('An empty Workspace exposed an installation binding')


@dataclass(frozen=True, slots=True)
class ProcessSample:
    rss_bytes: int
    traced_current_bytes: int
    traced_peak_bytes: int
    asyncio_tasks: int
    threads: int
    open_fds: int | None


def _sample_process() -> ProcessSample:
    gc.collect()
    process = psutil.Process()
    try:
        open_fds = process.num_fds()
    except (AttributeError, psutil.Error):
        open_fds = None
    traced_current, traced_peak = tracemalloc.get_traced_memory()
    return ProcessSample(
        rss_bytes=process.memory_info().rss,
        traced_current_bytes=traced_current,
        traced_peak_bytes=traced_peak,
        asyncio_tasks=len(asyncio.all_tasks()),
        threads=process.num_threads(),
        open_fds=open_fds,
    )


def _execution_context(index: int, *, query_uuid: str | None = None) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='runtime-resource-probe',
        workspace_uuid=f'workspace-{index}',
        placement_generation=1,
        bot_uuid='probe-bot',
        pipeline_uuid='probe-pipeline',
        query_uuid=query_uuid,
    )


class CoreRuntimeProbe:
    """Own the same manager instances across two equal churn phases."""

    def __init__(self) -> None:
        self.query_pool = QueryPool(max_queries=100, max_queries_per_workspace=1)
        app = SimpleNamespace(
            event_loop=asyncio.get_running_loop(),
            persistence_mgr=None,
            instance_config=SimpleNamespace(
                data={
                    'concurrency': {'session': 1},
                    'system': {
                        'session_retention': {
                            'idle_ttl_seconds': 86_400,
                            'max_entries': 200,
                            'max_entries_per_workspace': 200,
                            'max_conversations_per_session': 20,
                            'max_messages_per_conversation': 100,
                        },
                        'task_retention': {
                            'completed_limit': 200,
                            'max_log_chars': 4_096,
                            'max_active_user_tasks': 256,
                            'max_active_user_tasks_per_workspace': 8,
                        },
                    },
                }
            ),
        )
        self.session_manager = SessionManager(app)
        self.task_manager = AsyncTaskManager(app)
        self.rate_limit = FixedWindowAlgo(SimpleNamespace())
        self.websocket_session = WebSocketSession(
            'resource-probe',
            max_conversations=200,
            max_messages=100,
        )
        logger = SimpleNamespace(
            debug=lambda *_args, **_kwargs: None,
            info=lambda *_args, **_kwargs: None,
            warning=lambda *_args, **_kwargs: None,
            error=lambda *_args, **_kwargs: None,
        )
        self.empty_model_queries = 0

        async def execute_empty(_statement):
            self.empty_model_queries += 1
            return _EmptyResult()

        model_app = SimpleNamespace(
            logger=logger,
            persistence_mgr=SimpleNamespace(execute_async=execute_empty),
        )
        self.empty_model_manager = ModelManager(model_app)

        async def runtime_disconnect_callback(_connector) -> None:
            return None

        plugin_app = SimpleNamespace(
            instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
            deployment=SimpleNamespace(mode='cloud'),
            logger=logger,
        )
        self.empty_plugin_connector = PluginRuntimeConnector(
            plugin_app,
            runtime_disconnect_callback,
        )
        self.empty_plugin_connector.handler = _EmptyPluginRuntimeHandler()

        async def validate_context(context):
            return context

        async def load_desired_states(_context):
            return []

        self.empty_plugin_connector._validate_execution_context = validate_context
        self.empty_plugin_connector._load_workspace_desired_states = load_desired_states

    async def initialize(self) -> None:
        await self.rate_limit.initialize()

    async def run_phase(self, scale: ProbeScale, phase: int) -> None:
        offsets = {
            'query': (phase - 1) * scale.query_churn_per_phase,
            'session': (phase - 1) * scale.session_churn_per_phase,
            'rate': (phase - 1) * scale.rate_limit_churn_per_phase,
            'task': (phase - 1) * scale.task_churn_per_phase,
            'websocket': (phase - 1) * scale.websocket_churn_per_phase,
            'empty_workspace': ((phase - 1) * scale.empty_workspace_churn_per_phase),
        }
        await self._churn_queries(offsets['query'], scale.query_churn_per_phase)
        await self._churn_sessions(offsets['session'], scale.session_churn_per_phase)
        await self._churn_rate_limits(offsets['rate'], scale.rate_limit_churn_per_phase)
        await self._churn_tasks(offsets['task'], scale.task_churn_per_phase)
        self._churn_websocket_history(
            offsets['websocket'],
            scale.websocket_churn_per_phase,
        )
        await self._churn_empty_workspaces(
            offsets['empty_workspace'],
            scale.empty_workspace_churn_per_phase,
        )
        await asyncio.sleep(0)

    async def _churn_queries(self, start: int, count: int) -> None:
        def make_query(**values):
            return _ProbeQuery(**values)

        with patch(
            'langbot.pkg.pipeline.pool.pipeline_query.Query',
            side_effect=make_query,
        ):
            for index in range(start, start + count):
                context = _execution_context(index)
                query = await self.query_pool.add_query(
                    bot_uuid='probe-bot',
                    launcher_type=LauncherTypes.PERSON,
                    launcher_id=f'launcher-{index}',
                    sender_id=f'sender-{index}',
                    message_event=SimpleNamespace(),
                    message_chain=SimpleNamespace(),
                    adapter=None,
                    pipeline_uuid='probe-pipeline',
                    execution_context=context,
                )
                removed = await self.query_pool.remove_query(query)
                if not removed:
                    raise AssertionError('Query cleanup failed')

    async def _churn_sessions(self, start: int, count: int) -> None:
        for index in range(start, start + count):
            workspace_index = index % 100
            context = _execution_context(
                workspace_index,
                query_uuid=f'session-query-{index}',
            )
            query = SimpleNamespace(
                launcher_type=LauncherTypes.PERSON,
                launcher_id=f'launcher-{index}',
                sender_id=f'sender-{index}',
                bot_uuid='probe-bot',
                pipeline_uuid='probe-pipeline',
                query_uuid=context.query_uuid,
                _execution_context=context,
            )
            await self.session_manager.get_session(query)

    async def _churn_rate_limits(self, start: int, count: int) -> None:
        for index in range(start, start + count):
            context = _execution_context(
                index % 1_000,
                query_uuid=f'rate-query-{index}',
            )
            query = SimpleNamespace(
                bot_uuid='probe-bot',
                pipeline_uuid='probe-pipeline',
                _execution_context=context,
                pipeline_config={
                    'safety': {
                        'rate-limit': {
                            'window-length': 60,
                            'limitation': 100_000,
                            'strategy': 'drop',
                        }
                    }
                },
            )
            admitted = await self.rate_limit.require_access(
                query,
                LauncherTypes.PERSON,
                f'rate-identity-{index}',
            )
            if not admitted:
                raise AssertionError('Rate-limit registry rejected bounded churn')

    async def _churn_tasks(self, start: int, count: int) -> None:
        async def complete_immediately() -> None:
            return None

        for batch_start in range(start, start + count, 256):
            batch_size = min(256, start + count - batch_start)
            wrappers = [
                self.task_manager.create_task(
                    complete_immediately(),
                    name=f'resource-probe-{batch_start + offset}',
                )
                for offset in range(batch_size)
            ]
            await asyncio.gather(*(wrapper.task for wrapper in wrappers))
            await asyncio.sleep(0)

    def _churn_websocket_history(self, start: int, count: int) -> None:
        for index in range(start, start + count):
            conversation_key = f'conversation-{index}'
            response_id = f'response-{index}'
            indexes = self.websocket_session.get_stream_message_indexes(conversation_key)
            indexes[response_id] = 0
            self.websocket_session.append_message(
                conversation_key,
                WebSocketMessage(
                    id=self.websocket_session.next_message_id(conversation_key),
                    role='assistant',
                    content='probe',
                    message_chain=[],
                    timestamp='1970-01-01T00:00:00+00:00',
                    is_final=True,
                ),
            )

    async def _churn_empty_workspaces(self, start: int, count: int) -> None:
        for index in range(start, start + count):
            await self.empty_model_manager._load_workspace_models(_execution_context(index))
        await self.empty_plugin_connector.reconcile_projected_workspaces(
            _execution_context(index) for index in range(start, start + count)
        )

    def retained_state(self) -> dict[str, int]:
        return {
            'query_cached': len(self.query_pool.cached_queries),
            'query_queued': len(self.query_pool.queries),
            'query_active_workspaces': len(self.query_pool.active_query_count_by_workspace),
            'query_scope_counters': len(self.query_pool.query_count_by_scope),
            'sessions': len(self.session_manager.session_list),
            'session_index': len(self.session_manager._session_index),
            'rate_limit_containers': len(self.rate_limit.containers),
            'task_records': len(self.task_manager.tasks),
            'websocket_conversations': len(self.websocket_session.message_lists),
            'websocket_stream_indexes': len(self.websocket_session.stream_message_indexes),
            'empty_model_scopes': len(self.empty_model_manager._scope_generations),
            'empty_model_providers': len(self.empty_model_manager.provider_dict),
            'empty_model_llms': len(self.empty_model_manager.llm_model_dict),
            'empty_plugin_workspace_sets': len(self.empty_plugin_connector._workspace_installations),
            'empty_plugin_installations': len(self.empty_plugin_connector._known_desired_states),
        }

    def assert_bounded(self) -> None:
        state = self.retained_state()
        expected_maximums = {
            'query_cached': 0,
            'query_queued': 0,
            'query_active_workspaces': 0,
            'query_scope_counters': 100,
            'sessions': 200,
            'session_index': 200,
            'rate_limit_containers': 10_000,
            'task_records': 200,
            'websocket_conversations': 200,
            'websocket_stream_indexes': 200,
            'empty_model_scopes': 0,
            'empty_model_providers': 0,
            'empty_model_llms': 0,
            'empty_plugin_workspace_sets': 0,
            'empty_plugin_installations': 0,
        }
        violations = {key: (state[key], maximum) for key, maximum in expected_maximums.items() if state[key] > maximum}
        if violations:
            raise AssertionError(f'Core retained-state limits failed: {violations}')


async def _run(args: argparse.Namespace) -> dict:
    scale = SCALES[args.scale]
    tracemalloc.start()
    started_at = time.monotonic()
    probe = CoreRuntimeProbe()
    await probe.initialize()

    baseline = _sample_process()
    await probe.run_phase(scale, 1)
    probe.assert_bounded()
    phase_one = _sample_process()
    state_one = probe.retained_state()

    await probe.run_phase(scale, 2)
    probe.assert_bounded()
    phase_two = _sample_process()
    state_two = probe.retained_state()

    if state_two != state_one:
        raise AssertionError(f'Core retained state did not plateau: phase_one={state_one}, phase_two={state_two}')
    traced_growth = phase_two.traced_current_bytes - phase_one.traced_current_bytes
    rss_growth = phase_two.rss_bytes - phase_one.rss_bytes
    max_traced_growth = int(args.max_traced_growth_mib * 1024 * 1024)
    max_rss_growth = int(args.max_rss_growth_mib * 1024 * 1024)
    if traced_growth > max_traced_growth:
        raise AssertionError(f'Second-phase traced memory grew by {traced_growth} bytes (limit {max_traced_growth})')
    if rss_growth > max_rss_growth:
        raise AssertionError(f'Second-phase RSS grew by {rss_growth} bytes (limit {max_rss_growth})')

    return {
        'component': 'langbot-core',
        'scale': args.scale,
        'work_per_phase': asdict(scale),
        'elapsed_seconds': round(time.monotonic() - started_at, 3),
        'samples': {
            'baseline': asdict(baseline),
            'phase_one': asdict(phase_one),
            'phase_two': asdict(phase_two),
        },
        'second_phase_growth': {
            'rss_bytes': rss_growth,
            'traced_current_bytes': traced_growth,
        },
        'retained_state': {
            'phase_one': state_one,
            'phase_two': state_two,
        },
        'passed': True,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scale', choices=tuple(SCALES), default='quick')
    parser.add_argument('--max-traced-growth-mib', type=float, default=8.0)
    parser.add_argument('--max-rss-growth-mib', type=float, default=64.0)
    parser.add_argument('--json', action='store_true', help='Print compact JSON')
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
