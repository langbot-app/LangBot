"""Agent runner errors."""
from __future__ import annotations


class AgentRunnerError(Exception):
    """Base error for agent runner operations."""
    pass


class RunnerNotFoundError(AgentRunnerError):
    """Runner not found in registry."""
    def __init__(self, runner_id: str):
        self.runner_id = runner_id
        super().__init__(f'Agent runner not found: {runner_id}')


class RunnerNotAuthorizedError(AgentRunnerError):
    """Runner not authorized for this pipeline."""
    def __init__(self, runner_id: str, bound_plugins: list[str] | None):
        self.runner_id = runner_id
        self.bound_plugins = bound_plugins
        super().__init__(f'Agent runner {runner_id} not authorized for bound_plugins={bound_plugins}')


class RunnerProtocolError(AgentRunnerError):
    """Runner protocol version mismatch or invalid manifest."""
    def __init__(self, runner_id: str, message: str):
        self.runner_id = runner_id
        super().__init__(f'Agent runner protocol error for {runner_id}: {message}')


class RunnerExecutionError(AgentRunnerError):
    """Runner execution failed."""
    def __init__(self, runner_id: str, message: str, retryable: bool = False):
        self.runner_id = runner_id
        self.retryable = retryable
        super().__init__(f'Agent runner {runner_id} execution failed: {message}')