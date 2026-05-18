"""Unit tests for RAG i18n name conversion.

Tests cover:
- _to_i18n_name() static method
"""
from __future__ import annotations

from importlib import import_module


def get_kbmgr_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.rag.knowledge.kbmgr')


class TestToI18nName:
    """Tests for _to_i18n_name static method."""

    def test_string_input_wrapped(self):
        """Test that string input is wrapped into i18n dict."""
        kbmgr = get_kbmgr_module()
        result = kbmgr.RAGManager._to_i18n_name('Test Engine')
        assert result == {'en_US': 'Test Engine', 'zh_Hans': 'Test Engine'}

    def test_dict_input_preserved(self):
        """Test that dict input is returned as-is."""
        kbmgr = get_kbmgr_module()
        input_dict = {'en_US': 'English Name', 'zh_Hans': '中文名', 'ja_JP': '日本語名'}
        result = kbmgr.RAGManager._to_i18n_name(input_dict)
        assert result == input_dict
        assert result is input_dict  # Should return the same object

    def test_empty_string_handling(self):
        """Test that empty string is handled correctly."""
        kbmgr = get_kbmgr_module()
        result = kbmgr.RAGManager._to_i18n_name('')
        assert result == {'en_US': '', 'zh_Hans': ''}

    def test_none_input_handling(self):
        """Test that None is converted to string 'None'."""
        kbmgr = get_kbmgr_module()
        result = kbmgr.RAGManager._to_i18n_name(None)
        assert result == {'en_US': 'None', 'zh_Hans': 'None'}

    def test_number_input_converted_to_string(self):
        """Test that numbers are converted to strings."""
        kbmgr = get_kbmgr_module()
        result = kbmgr.RAGManager._to_i18n_name(123)
        assert result == {'en_US': '123', 'zh_Hans': '123'}

    def test_dict_with_partial_keys_preserved(self):
        """Test that dict with only some i18n keys is preserved."""
        kbmgr = get_kbmgr_module()
        input_dict = {'en_US': 'Only English'}
        result = kbmgr.RAGManager._to_i18n_name(input_dict)
        assert result == {'en_US': 'Only English'}

    def test_dict_with_extra_keys_preserved(self):
        """Test that dict with extra non-i18n keys is preserved."""
        kbmgr = get_kbmgr_module()
        input_dict = {'en_US': 'English', 'extra_key': 'extra_value'}
        result = kbmgr.RAGManager._to_i18n_name(input_dict)
        assert result == {'en_US': 'English', 'extra_key': 'extra_value'}