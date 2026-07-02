"""
Monitoring helper for recording events during workflow execution.
This module provides convenient methods to record monitoring data
without cluttering the main workflow code.

NOTE: All frontend panel logging functionality has been removed.
A new solution will be implemented separately.
"""

from __future__ import annotations

import typing
import time

if typing.TYPE_CHECKING:
    from ..core import app
    from langbot_plugin.api.entities.builtin.workflow.query import WorkflowQuery


class WorkflowMonitoringHelper:
    """Helper class for workflow monitoring operations"""

    # All frontend panel logging methods have been removed.
    # A new solution will be implemented separately.
    pass


class LLMCallMonitor:
    """Context manager for monitoring LLM calls in workflow"""

    def __init__(
        self,
        ap: app.Application,
        query: WorkflowQuery,
        bot_id: str,
        bot_name: str,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        model_name: str,
    ):
        self.ap = ap
        self.query = query
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.node_name = node_name
        self.model_name = model_name
        self.start_time = None
        self.input_tokens = 0
        self.output_tokens = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # LLM call monitoring has been removed.
        # A new solution will be implemented separately.
        return False
