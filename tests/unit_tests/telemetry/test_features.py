"""Unit tests for telemetry feature counters (pkg/telemetry/features.py)."""

from __future__ import annotations

from importlib import import_module


def get_features_module():
    return import_module('langbot.pkg.telemetry.features')


class FakeQuery:
    def __init__(self):
        self.variables = {}


class TestIncrement:
    def test_increment_nested_counter(self):
        features = get_features_module()
        q = FakeQuery()
        features.increment(q, 'tool_calls', 'native')
        features.increment(q, 'tool_calls', 'native')
        features.increment(q, 'tool_calls', 'mcp')
        assert q.variables[features.FEATURES_KEY]['tool_calls'] == {'native': 2, 'mcp': 1}

    def test_increment_flat_counter(self):
        features = get_features_module()
        q = FakeQuery()
        features.increment(q, 'something')
        features.increment(q, 'something', amount=2)
        assert q.variables[features.FEATURES_KEY]['something'] == 3

    def test_increment_never_raises_on_broken_query(self):
        features = get_features_module()

        class Broken:
            @property
            def variables(self):
                raise RuntimeError('boom')

        # Must not raise
        features.increment(Broken(), 'tool_calls', 'native')

    def test_set_value(self):
        features = get_features_module()
        q = FakeQuery()
        features.set_value(q, 'tool_call_rounds', 5)
        assert q.variables[features.FEATURES_KEY]['tool_call_rounds'] == 5


class TestCollectFeatures:
    def test_collect_empty(self):
        features = get_features_module()
        q = FakeQuery()
        assert features.collect_features(q) == {}

    def test_collect_combines_counters_and_snapshots(self):
        features = get_features_module()
        q = FakeQuery()
        features.increment(q, 'sandbox', 'execs')
        features.set_value(q, 'kb', {'kb_count': 2, 'engine_plugins': ['builtin'], 'retrieved_entries': 7})
        q.variables['_activated_skills'] = {'pdf-tools': {}, 'a-skill': {}}
        q.variables['_pipeline_bound_mcp_servers'] = ['srv1', 'srv2']

        result = features.collect_features(q)
        assert result['sandbox'] == {'execs': 1}
        assert result['kb']['kb_count'] == 2
        assert result['activated_skills'] == ['a-skill', 'pdf-tools']  # sorted
        assert result['mcp_servers'] == ['srv1', 'srv2']

    def test_collect_omits_mcp_when_all_enabled(self):
        """None means 'all enabled' and is not reported."""
        features = get_features_module()
        q = FakeQuery()
        q.variables['_pipeline_bound_mcp_servers'] = None
        assert 'mcp_servers' not in features.collect_features(q)

    def test_collect_drops_non_json_serializable(self):
        features = get_features_module()
        q = FakeQuery()
        features.set_value(q, 'good', 1)
        features.set_value(q, 'bad', object())
        result = features.collect_features(q)
        assert result == {'good': 1}

    def test_collect_is_json_serializable(self):
        import json

        features = get_features_module()
        q = FakeQuery()
        features.increment(q, 'tool_calls', 'skill')
        json.dumps(features.collect_features(q))
