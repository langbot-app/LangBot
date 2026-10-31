"""Agent runner subsystem for LangBot."""

from __future__ import annotations

from .runner.descriptor import RunnerDescriptor
from .runner.id import parse_runner_id, format_runner_id, RunnerIdParts, is_plugin_runner_id
from .runner.errors import (
    RunnerError,
    RunnerNotFoundError,
    RunnerNotAuthorizedError,
    RunnerProtocolError,
    RunnerExecutionError,
)
from .runner.registry import RunnerRegistry
from .runner.context_builder import RunnerContextBuilder
from .runner.resource_builder import AgentResourceBuilder
from .runner.result_normalizer import AgentResultNormalizer
from .runner.orchestrator import AgentRunOrchestrator
from .runner.config_resolver import RunnerConfigResolver

__all__ = [
    'RunnerDescriptor',
    'parse_runner_id',
    'format_runner_id',
    'is_plugin_runner_id',
    'RunnerIdParts',
    'RunnerError',
    'RunnerNotFoundError',
    'RunnerNotAuthorizedError',
    'RunnerProtocolError',
    'RunnerExecutionError',
    'RunnerRegistry',
    'RunnerContextBuilder',
    'AgentResourceBuilder',
    'AgentResultNormalizer',
    'AgentRunOrchestrator',
    'RunnerConfigResolver',
]
