#!/usr/bin/env python3
"""Measure populated Workspace runtime replacement cost and retention.

Unlike ``runtime_resource_probe.py``, which stresses historical request keys
and empty tenants, this probe keeps one representative Provider, LLM,
Embedding model, Rerank model, Pipeline, Bot, and Knowledge Base per Workspace.
It then advances every Workspace to a new placement generation and verifies
that old runtime objects are closed and collectible while active registry
cardinality remains constant.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import time
import tracemalloc
import weakref
from dataclasses import asdict, dataclass
from types import SimpleNamespace

import psutil

from langbot.pkg.api.http.context import ExecutionContext

# Match the production import order; importing a leaf manager first exposes a
# historical annotation cycle that the application graph resolves.
from langbot.pkg.core import app as _core_app  # noqa: F401
from langbot.pkg.entity.persistence import bot as persistence_bot
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.entity.persistence import pipeline as persistence_pipeline
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.pipeline.pipelinemgr import PipelineManager
from langbot.pkg.platform.botmgr import PlatformManager
from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.tools.loaders.mcp import MCPLoader
from langbot.pkg.rag.knowledge.kbmgr import RAGManager
from langbot.pkg.workspace.entities import WorkspaceExecutionBinding


@dataclass(frozen=True, slots=True)
class ProbeScale:
    workspaces: int


SCALES = {
    'quick': ProbeScale(workspaces=250),
    'audit': ProbeScale(workspaces=5_000),
}


@dataclass(frozen=True, slots=True)
class ProcessSample:
    rss_bytes: int
    traced_current_bytes: int
    traced_peak_bytes: int
    asyncio_tasks: int
    threads: int
    open_fds: int | None


class _ProbeLogger:
    def debug(self, *_args, **_kwargs) -> None:
        return None

    def info(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None

    def error(self, *_args, **_kwargs) -> None:
        return None


class _ProbeWorkspaceService:
    instance_uuid = 'runtime-capacity-probe'

    def __init__(self) -> None:
        self.generations: dict[str, int] = {}
        self.binding_lookups = 0

    async def get_execution_binding(
        self,
        workspace_uuid: str,
        *,
        expected_generation: int | None = None,
    ) -> WorkspaceExecutionBinding:
        self.binding_lookups += 1
        generation = self.generations[workspace_uuid]
        if expected_generation is not None and expected_generation != generation:
            raise AssertionError(f'stale probe generation {expected_generation} != {generation}')
        return WorkspaceExecutionBinding(
            instance_uuid=self.instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            write_fenced=False,
            state='active',
        )


class _ProbeRequester(requester.ProviderAPIRequester):
    name = 'capacity-probe'
    closed = 0

    async def invoke_llm(
        self,
        query,
        model,
        messages,
        funcs=None,
        extra_args=None,
        remove_think=False,
    ):
        return None

    async def aclose(self) -> None:
        type(self).closed += 1


class _ProbeAdapter:
    killed = 0

    def __init__(self, _config, _logger) -> None:
        self.listeners = []

    def register_listener(self, event_type, listener) -> None:
        self.listeners.append((event_type, listener))

    async def kill(self) -> None:
        type(self).killed += 1


class _ProbeMCPSession:
    closed = 0

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name

    async def shutdown(self) -> None:
        type(self).closed += 1


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


class PopulatedWorkspaceProbe:
    def __init__(self) -> None:
        _ProbeRequester.closed = 0
        _ProbeAdapter.killed = 0
        _ProbeMCPSession.closed = 0
        self.workspace_service = _ProbeWorkspaceService()
        self.logger = _ProbeLogger()
        self.app = SimpleNamespace(
            logger=self.logger,
            workspace_service=self.workspace_service,
            persistence_mgr=SimpleNamespace(
                mode=SimpleNamespace(value='cloud_runtime'),
            ),
            pipeline_config_meta_trigger={'name': 'trigger', 'stages': []},
            pipeline_config_meta_safety={'name': 'safety', 'stages': []},
            pipeline_config_meta_ai={'name': 'ai', 'stages': []},
            pipeline_config_meta_output={'name': 'output', 'stages': []},
            task_mgr=SimpleNamespace(
                cancel_by_scope=lambda *_args, **_kwargs: None,
                cancel_task=lambda *_args, **_kwargs: None,
            ),
        )
        self.model_manager = ModelManager(self.app)
        self.model_manager.requester_dict = {
            _ProbeRequester.name: _ProbeRequester,
        }
        self.pipeline_manager = PipelineManager(self.app)
        self.pipeline_manager.stage_dict = {}
        self.rag_manager = RAGManager(self.app)
        self.mcp_loader = MCPLoader(self.app)
        self.platform_manager = PlatformManager(self.app)
        self.platform_manager.adapter_dict = {
            'capacity-probe': _ProbeAdapter,
        }
        self.generation_refs: dict[
            int,
            list[weakref.ReferenceType],
        ] = {}

    def _context(
        self,
        workspace_uuid: str,
        generation: int,
        *,
        bot_uuid: str | None = None,
        pipeline_uuid: str | None = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            instance_uuid=self.workspace_service.instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
        )

    async def load_generation(self, workspaces: int, generation: int) -> None:
        for index in range(workspaces):
            workspace_uuid = f'workspace-{index}'
            provider_uuid = f'provider-{index}'
            llm_uuid = f'llm-{index}'
            embedding_uuid = f'embedding-{index}'
            rerank_uuid = f'rerank-{index}'
            pipeline_uuid = f'pipeline-{index}'
            bot_uuid = f'bot-{index}'
            kb_uuid = f'knowledge-{index}'
            mcp_server_name = f'mcp-{index}'
            self.workspace_service.generations[workspace_uuid] = generation
            context = self._context(workspace_uuid, generation)

            runtime_provider = await self.model_manager.load_provider(
                context,
                persistence_model.ModelProvider(
                    uuid=provider_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Provider',
                    requester=_ProbeRequester.name,
                    base_url='https://capacity.invalid',
                    api_keys=['probe'],
                ),
            )
            await self.model_manager.cache_provider(context, runtime_provider)

            runtime_llm = await self.model_manager.load_llm_model_with_provider(
                context,
                persistence_model.LLMModel(
                    uuid=llm_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity LLM',
                    provider_uuid=provider_uuid,
                    abilities=['func_call'],
                    extra_args={'temperature': 0.1},
                ),
                runtime_provider,
            )
            await self.model_manager.cache_llm_model(context, runtime_llm)
            runtime_embedding = await self.model_manager.load_embedding_model_with_provider(
                context,
                persistence_model.EmbeddingModel(
                    uuid=embedding_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Embedding',
                    provider_uuid=provider_uuid,
                    extra_args={'dimensions': 1_024},
                ),
                runtime_provider,
            )
            await self.model_manager.cache_embedding_model(
                context,
                runtime_embedding,
            )
            runtime_rerank = await self.model_manager.load_rerank_model_with_provider(
                context,
                persistence_model.RerankModel(
                    uuid=rerank_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Rerank',
                    provider_uuid=provider_uuid,
                    extra_args={},
                ),
                runtime_provider,
            )
            await self.model_manager.cache_rerank_model(
                context,
                runtime_rerank,
            )

            pipeline_context = self._context(
                workspace_uuid,
                generation,
                pipeline_uuid=pipeline_uuid,
            )
            await self.pipeline_manager.load_pipeline(
                pipeline_context,
                persistence_pipeline.LegacyPipeline(
                    uuid=pipeline_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Pipeline',
                    description='',
                    for_version='probe',
                    is_default=True,
                    stages=[],
                    config={},
                    extensions_preferences={},
                ),
                _binding_validated=True,
            )
            runtime_pipeline = self.pipeline_manager._pipelines_by_key[
                (
                    self.workspace_service.instance_uuid,
                    workspace_uuid,
                    pipeline_uuid,
                )
            ]

            runtime_kb = await self.rag_manager.load_knowledge_base(
                context,
                persistence_rag.KnowledgeBase(
                    uuid=kb_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Knowledge',
                    description='',
                    knowledge_engine_plugin_id=None,
                    collection_id=kb_uuid,
                    creation_settings={},
                    retrieval_settings={},
                ),
                _binding_validated=True,
            )

            await self.mcp_loader._assert_execution_active(context)
            runtime_mcp = _ProbeMCPSession(mcp_server_name)
            self.mcp_loader._register_session(
                context,
                mcp_server_name,
                runtime_mcp,
            )

            bot_context = self._context(
                workspace_uuid,
                generation,
                bot_uuid=bot_uuid,
            )
            runtime_bot = await self.platform_manager.load_bot(
                bot_context,
                persistence_bot.Bot(
                    uuid=bot_uuid,
                    workspace_uuid=workspace_uuid,
                    name='Capacity Bot',
                    description='',
                    adapter='capacity-probe',
                    adapter_config={},
                    enable=True,
                    use_pipeline_uuid=pipeline_uuid,
                    pipeline_routing_rules=[],
                ),
                _binding_validated=True,
            )

            self.generation_refs.setdefault(generation, []).extend(
                (
                    weakref.ref(runtime_provider),
                    weakref.ref(runtime_llm),
                    weakref.ref(runtime_embedding),
                    weakref.ref(runtime_rerank),
                    weakref.ref(runtime_pipeline),
                    weakref.ref(runtime_kb),
                    weakref.ref(runtime_mcp),
                    weakref.ref(runtime_bot),
                )
            )

        await asyncio.sleep(0)

    def retained_state(self) -> dict[str, int]:
        return {
            'model_providers': len(self.model_manager.provider_dict),
            'llm_models': len(self.model_manager.llm_model_dict),
            'embedding_models': len(self.model_manager.embedding_model_dict),
            'rerank_models': len(self.model_manager.rerank_model_dict),
            'model_scopes': len(self.model_manager._scope_generations),
            'pipelines': len(self.pipeline_manager._pipelines_by_key),
            'pipeline_scopes': len(self.pipeline_manager._scope_generations),
            'knowledge_bases': len(self.rag_manager.knowledge_bases),
            'knowledge_scopes': len(self.rag_manager._scope_generations),
            'mcp_sessions': len(self.mcp_loader.sessions),
            'mcp_scopes': len(self.mcp_loader._scope_generations),
            'bots': len(self.platform_manager._bots_by_key),
            'bot_scopes': len(self.platform_manager._scope_generations),
            'requesters_closed': _ProbeRequester.closed,
            'adapters_killed': _ProbeAdapter.killed,
            'mcp_sessions_closed': _ProbeMCPSession.closed,
            'binding_lookups': self.workspace_service.binding_lookups,
        }

    def assert_generation_state(
        self,
        workspaces: int,
        generation: int,
    ) -> None:
        state = self.retained_state()
        cardinality_keys = (
            'model_providers',
            'llm_models',
            'embedding_models',
            'rerank_models',
            'model_scopes',
            'pipelines',
            'pipeline_scopes',
            'knowledge_bases',
            'knowledge_scopes',
            'mcp_sessions',
            'mcp_scopes',
            'bots',
            'bot_scopes',
        )
        invalid = {key: value for key in cardinality_keys if (value := state[key]) != workspaces}
        if invalid:
            raise AssertionError(f'populated Workspace cardinality mismatch: {invalid}')
        expected_retired = (generation - 1) * workspaces
        if state['requesters_closed'] != expected_retired:
            raise AssertionError(f'retired requester count {state["requesters_closed"]} != {expected_retired}')
        if state['adapters_killed'] != expected_retired:
            raise AssertionError(f'retired adapter count {state["adapters_killed"]} != {expected_retired}')
        if state['mcp_sessions_closed'] != expected_retired:
            raise AssertionError(f'retired MCP session count {state["mcp_sessions_closed"]} != {expected_retired}')

    def assert_generation_collected(self, generation: int) -> None:
        gc.collect()
        references = self.generation_refs.pop(generation)
        retained = sum(reference() is not None for reference in references)
        if retained:
            raise AssertionError(f'{retained} generation-{generation} runtime objects remain reachable')


async def _run(args: argparse.Namespace) -> dict:
    scale = SCALES[args.scale]
    tracemalloc.start()
    probe = PopulatedWorkspaceProbe()
    baseline = _sample_process()

    phase_one_started = time.monotonic()
    await probe.load_generation(scale.workspaces, 1)
    phase_one_seconds = time.monotonic() - phase_one_started
    probe.assert_generation_state(scale.workspaces, 1)
    phase_one = _sample_process()
    phase_one_state = probe.retained_state()

    phase_two_started = time.monotonic()
    await probe.load_generation(scale.workspaces, 2)
    phase_two_seconds = time.monotonic() - phase_two_started
    probe.assert_generation_state(scale.workspaces, 2)
    probe.assert_generation_collected(1)
    phase_two = _sample_process()
    phase_two_state = probe.retained_state()

    phase_three_started = time.monotonic()
    await probe.load_generation(scale.workspaces, 3)
    phase_three_seconds = time.monotonic() - phase_three_started
    probe.assert_generation_state(scale.workspaces, 3)
    probe.assert_generation_collected(2)
    phase_three = _sample_process()
    phase_three_state = probe.retained_state()

    cardinality_keys = (
        'model_providers',
        'llm_models',
        'embedding_models',
        'rerank_models',
        'model_scopes',
        'pipelines',
        'pipeline_scopes',
        'knowledge_bases',
        'knowledge_scopes',
        'mcp_sessions',
        'mcp_scopes',
        'bots',
        'bot_scopes',
    )
    if any(
        phase_two_state[key] != phase_one_state[key] or phase_three_state[key] != phase_one_state[key]
        for key in cardinality_keys
    ):
        raise AssertionError(
            'populated Workspace registries did not plateau: '
            f'phase_one={phase_one_state}, phase_two={phase_two_state}, '
            f'phase_three={phase_three_state}'
        )

    traced_growth = phase_three.traced_current_bytes - phase_two.traced_current_bytes
    rss_growth = phase_three.rss_bytes - phase_two.rss_bytes
    max_traced_growth = int(args.max_traced_growth_mib * 1024 * 1024)
    max_rss_growth = int(args.max_rss_growth_mib * 1024 * 1024)
    if traced_growth > max_traced_growth:
        raise AssertionError(f'replacement traced memory grew by {traced_growth} bytes (limit {max_traced_growth})')
    if rss_growth > max_rss_growth:
        raise AssertionError(f'replacement RSS grew by {rss_growth} bytes (limit {max_rss_growth})')
    phase_ratio = max(
        phase_two_seconds,
        phase_three_seconds,
    ) / max(phase_one_seconds, 0.000_001)
    if phase_ratio > args.max_replacement_time_ratio:
        raise AssertionError(f'replacement phase ratio {phase_ratio:.3f} exceeds {args.max_replacement_time_ratio:.3f}')

    return {
        'component': 'langbot-populated-workspaces',
        'scale': args.scale,
        'workspaces': scale.workspaces,
        'passed': True,
        'phase_seconds': {
            'initial': round(phase_one_seconds, 3),
            'replacement_one': round(phase_two_seconds, 3),
            'replacement_two': round(phase_three_seconds, 3),
            'maximum_replacement_ratio': round(phase_ratio, 3),
        },
        'samples': {
            'baseline': asdict(baseline),
            'phase_one': asdict(phase_one),
            'phase_two': asdict(phase_two),
            'phase_three': asdict(phase_three),
        },
        'replacement_growth': {
            'rss_bytes': rss_growth,
            'traced_current_bytes': traced_growth,
        },
        'retained_state': {
            'phase_one': phase_one_state,
            'phase_two': phase_two_state,
            'phase_three': phase_three_state,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scale', choices=tuple(SCALES), default='quick')
    parser.add_argument('--max-traced-growth-mib', type=float, default=16.0)
    parser.add_argument('--max-rss-growth-mib', type=float, default=64.0)
    parser.add_argument(
        '--max-replacement-time-ratio',
        type=float,
        default=3.0,
    )
    parser.add_argument('--json', action='store_true')
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
