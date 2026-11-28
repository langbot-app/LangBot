"""Unit tests for mixed Artifact soak wave/stage timing diagnostics and profile budgets."""

from __future__ import annotations

import json
import math
from pathlib import Path

from tests.e2e import test_artifact_lifecycle_soak as soak


def test_summarize_wave_timing_attributes_dominant_stage_to_http_or_sampling():
    http_dominated = soak._summarize_wave_timing(
        70,
        'accelerated-steady',
        wave_seconds=4.140,
        wave_exec_seconds=4.069,
        sample_seconds=0.071,
        turn_timings=[
            {
                'turn': 280,
                'kind': 'text',
                'session': 'qa-person-short-280',
                'total_seconds': 2.11,
                'http_seconds': 2.01,
                'verify_seconds': 0.05,
                'release_seconds': 0.04,
                'ttl_update_seconds': 0.01,
            },
            {
                'turn': 281,
                'kind': 'png',
                'session': 'qa-group-1-short-281',
                'total_seconds': 4.069,
                'http_seconds': 3.886,
                'verify_seconds': 0.094,
                'release_seconds': 0.074,
                'ttl_update_seconds': 0.015,
            },
        ],
    )
    assert http_dominated['wave'] == 70
    assert http_dominated['dominant_stage'] == 'http'
    assert http_dominated['slowest_turn']['turn'] == 281
    assert http_dominated['wave_exec_seconds'] == 4.069
    assert http_dominated['sample_seconds'] == 0.071

    sample_dominated = soak._summarize_wave_timing(
        71,
        'accelerated-steady',
        wave_seconds=5.42,
        wave_exec_seconds=1.12,
        sample_seconds=4.30,
        turn_timings=[
            {
                'turn': 284,
                'kind': 'jpeg',
                'session': 'qa-person-short-284',
                'total_seconds': 1.12,
                'http_seconds': 0.90,
                'verify_seconds': 0.12,
                'release_seconds': 0.08,
                'ttl_update_seconds': 0.02,
            }
        ],
    )
    assert sample_dominated['dominant_stage'] == 'sample'


def test_aggregate_timing_summary_computes_wave_and_stage_distributions():
    turns = [
        {
            'turn': 0,
            'kind': 'png',
            'session': 's0',
            'total_seconds': 2.0,
            'http_seconds': 1.7,
            'verify_seconds': 0.15,
            'release_seconds': 0.1,
            'ttl_update_seconds': 0.05,
        },
        {
            'turn': 1,
            'kind': 'mixed',
            'session': 's1',
            'total_seconds': 3.5,
            'http_seconds': 3.1,
            'verify_seconds': 0.2,
            'release_seconds': 0.15,
            'ttl_update_seconds': 0.05,
        },
    ]
    waves = [
        soak._summarize_wave_timing(
            0,
            'accelerated-steady',
            wave_seconds=2.08,
            wave_exec_seconds=2.0,
            sample_seconds=0.08,
            turn_timings=[turns[0]],
        ),
        soak._summarize_wave_timing(
            1,
            'accelerated-steady',
            wave_seconds=3.62,
            wave_exec_seconds=3.5,
            sample_seconds=0.12,
            turn_timings=[turns[1]],
        ),
    ]
    summary = soak._aggregate_timing_summary(waves, turns)
    assert summary['wave_latency_seconds']['total']['max'] == 3.62
    assert summary['wave_latency_seconds']['wave_exec']['max'] == 3.5
    assert summary['wave_latency_seconds']['sample']['max'] == 0.12
    assert summary['stage_latency_seconds']['http']['max'] == 3.1
    assert summary['stage_latency_seconds']['verify']['max'] == 0.2
    assert summary['stage_latency_seconds']['release']['max'] == 0.15
    assert summary['stage_latency_seconds']['ttl_update']['max'] == 0.05
    assert summary['slowest_wave']['wave'] == 1
    assert summary['slowest_wave']['dominant_stage'] == 'http'


def test_artifact_soak_profile_respects_accelerated_gc_and_probe_budgets():
    root = Path(__file__).resolve().parents[3]
    profile = json.loads((root / 'tools/profiles/artifact-soak.json').read_text(encoding='utf-8'))
    assert set(profile['weights']) == set(soak._MIXED_KINDS)
    fast = profile['accelerated']
    parallel = profile['staircase'][-1]['parallel']
    rows_per_wave = parallel * 5
    assert 0 < fast['gc_interval_seconds'] <= fast['ttl_seconds'] < fast['load_seconds']
    assert fast['drain_seconds'] >= fast['ttl_seconds'] + 2 * fast['gc_interval_seconds']
    assert math.ceil(fast['gc_interval_seconds'] / fast['period_seconds']) * rows_per_wave <= 80
    assert (
        math.ceil((fast['ttl_seconds'] + 2 * fast['gc_interval_seconds']) / fast['period_seconds']) * rows_per_wave + 2
        <= profile['budgets']['artifact_rows']
    )
