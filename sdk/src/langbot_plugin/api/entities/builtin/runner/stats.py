"""Statistics entities for Runner admin APIs."""

from __future__ import annotations

import pydantic
from langbot_plugin.api.entities.builtin.runner.compat import HOST_RESPONSE_MODEL_CONFIG


class RunStats(pydantic.BaseModel):
    """Statistics for runs within a time window."""

    start_time: int | None = None
    end_time: int | None = None

    total_count: int = 0
    created_count: int = 0
    queued_count: int = 0
    claimed_count: int = 0
    running_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    timeout_count: int = 0

    throughput_per_hour: float | None = None
    success_rate: float | None = None
    failure_rate: float | None = None

    avg_duration_seconds: float | None = None
    p50_duration_seconds: float | None = None
    p95_duration_seconds: float | None = None
    p99_duration_seconds: float | None = None
    avg_queue_wait_seconds: float | None = None

    model_config = HOST_RESPONSE_MODEL_CONFIG


class RuntimeStats(pydantic.BaseModel):
    """Statistics for runtimes."""

    total_count: int = 0
    online_count: int = 0
    stale_count: int = 0

    avg_heartbeat_age_seconds: float | None = None
    max_heartbeat_age_seconds: float | None = None

    active_runs: int = 0
    claimed_runs: int = 0

    model_config = HOST_RESPONSE_MODEL_CONFIG


class RunnerStats(pydantic.BaseModel):
    """Statistics aggregated by runner."""

    runner_id: str
    runner_label: str | None = None
    plugin_identity: str | None = None

    total_runs: int = 0
    active_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0

    success_rate: float | None = None
    avg_duration_seconds: float | None = None

    model_config = HOST_RESPONSE_MODEL_CONFIG


class RunnerStatsPage(pydantic.BaseModel):
    """Paged result for runner stats."""

    items: list[RunnerStats] = pydantic.Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False

    model_config = HOST_RESPONSE_MODEL_CONFIG
