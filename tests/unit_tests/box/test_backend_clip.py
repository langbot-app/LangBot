from __future__ import annotations

import pytest

from langbot.pkg.box.backend import CLISandboxBackend, _MAX_RAW_OUTPUT_BYTES


class TestClipBytes:
    def test_within_limit_unchanged(self):
        data = b'hello world'
        result = CLISandboxBackend._clip_bytes(data, limit=1024)
        assert result == 'hello world'

    def test_exceeding_limit_clips_and_appends_notice(self):
        data = b'A' * 200
        result = CLISandboxBackend._clip_bytes(data, limit=100)
        assert result.startswith('A' * 100)
        assert 'raw output clipped at 100 bytes' in result
        assert '100 bytes discarded' in result

    def test_exact_limit_not_clipped(self):
        data = b'B' * 100
        result = CLISandboxBackend._clip_bytes(data, limit=100)
        assert result == 'B' * 100
        assert 'clipped' not in result

    def test_default_limit_is_module_constant(self):
        data = b'x' * 10
        result = CLISandboxBackend._clip_bytes(data)
        assert result == 'x' * 10
        assert _MAX_RAW_OUTPUT_BYTES == 1_048_576

    def test_invalid_utf8_replaced(self):
        data = b'ok\xff\xfetail'
        result = CLISandboxBackend._clip_bytes(data, limit=1024)
        assert 'ok' in result
        assert 'tail' in result
