"""Unit tests for config_coercion module"""

from __future__ import annotations

import pytest

from langbot.pkg.pipeline.config_coercion import _coerce_value, coerce_pipeline_config


class TestCoerceValue:
    """Tests for _coerce_value function"""

    def test_none_passthrough(self):
        assert _coerce_value(None, 'integer') is None
        assert _coerce_value(None, 'boolean') is None

    def test_string_to_integer(self):
        assert _coerce_value('120', 'integer') == 120
        assert _coerce_value('0', 'integer') == 0
        assert _coerce_value('-5', 'integer') == -5

    def test_integer_passthrough(self):
        assert _coerce_value(42, 'integer') == 42

    def test_string_to_float(self):
        assert _coerce_value('3.14', 'number') == 3.14
        assert _coerce_value('3.14', 'float') == 3.14

    def test_int_to_float(self):
        assert _coerce_value(3, 'number') == 3.0
        assert isinstance(_coerce_value(3, 'number'), float)

    def test_float_passthrough(self):
        assert _coerce_value(3.14, 'float') == 3.14

    def test_string_to_bool(self):
        assert _coerce_value('true', 'boolean') is True
        assert _coerce_value('True', 'boolean') is True
        assert _coerce_value('false', 'boolean') is False
        assert _coerce_value('False', 'boolean') is False

    def test_bool_passthrough(self):
        assert _coerce_value(True, 'boolean') is True
        assert _coerce_value(False, 'boolean') is False

    def test_invalid_bool_string_raises(self):
        with pytest.raises(ValueError):
            _coerce_value('notabool', 'boolean')

    def test_unknown_type_passthrough(self):
        assert _coerce_value('hello', 'string') == 'hello'
        assert _coerce_value('hello', 'unknown') == 'hello'

    def test_invalid_integer_raises(self):
        with pytest.raises(ValueError):
            _coerce_value('abc', 'integer')


class TestCoercePipelineConfig:
    """Tests for coerce_pipeline_config function"""

    def _make_meta(self, section_name: str, stage_name: str, fields: list[dict]) -> dict:
        return {
            'name': section_name,
            'stages': [{'name': stage_name, 'config': fields}],
        }

    def test_coerce_integer_in_config(self):
        config = {'trigger': {'misc': {'timeout': '120'}}}
        meta = self._make_meta('trigger', 'misc', [{'name': 'timeout', 'type': 'integer'}])
        coerce_pipeline_config(config, meta)
        assert config['trigger']['misc']['timeout'] == 120

    def test_coerce_boolean_in_config(self):
        config = {'output': {'misc': {'at-sender': 'true'}}}
        meta = self._make_meta('output', 'misc', [{'name': 'at-sender', 'type': 'boolean'}])
        coerce_pipeline_config(config, meta)
        assert config['output']['misc']['at-sender'] is True

    def test_missing_section_skipped(self):
        config = {'ai': {}}
        meta = self._make_meta('trigger', 'misc', [{'name': 'x', 'type': 'integer'}])
        coerce_pipeline_config(config, meta)  # should not raise

    def test_missing_field_skipped(self):
        config = {'trigger': {'misc': {}}}
        meta = self._make_meta('trigger', 'misc', [{'name': 'nonexistent', 'type': 'integer'}])
        coerce_pipeline_config(config, meta)  # should not raise

    def test_invalid_value_logs_warning(self, caplog):
        config = {'trigger': {'misc': {'timeout': 'abc'}}}
        meta = self._make_meta('trigger', 'misc', [{'name': 'timeout', 'type': 'integer'}])
        import logging
        with caplog.at_level(logging.WARNING):
            coerce_pipeline_config(config, meta)
        assert config['trigger']['misc']['timeout'] == 'abc'  # unchanged
        assert 'Failed to coerce' in caplog.text

    def test_empty_metadata(self):
        config = {'trigger': {'misc': {'timeout': '120'}}}
        coerce_pipeline_config(config)  # no metadata args, should not raise

    def test_multiple_metadata(self):
        config = {
            'trigger': {'misc': {'timeout': '120'}},
            'output': {'misc': {'at-sender': 'false'}},
        }
        meta_trigger = self._make_meta('trigger', 'misc', [{'name': 'timeout', 'type': 'integer'}])
        meta_output = self._make_meta('output', 'misc', [{'name': 'at-sender', 'type': 'boolean'}])
        coerce_pipeline_config(config, meta_trigger, meta_output)
        assert config['trigger']['misc']['timeout'] == 120
        assert config['output']['misc']['at-sender'] is False
