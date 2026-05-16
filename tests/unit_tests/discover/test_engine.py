"""
Unit tests for discover engine utilities.

Tests I18nString, Metadata, and Component utilities.
"""

from __future__ import annotations


from langbot.pkg.discover.engine import I18nString, Metadata, Component


class TestI18nString:
    """Tests for I18nString Pydantic model."""

    def test_create_with_english_only(self):
        """Create I18nString with only English."""
        i18n = I18nString(en_US="Hello")

        assert i18n.en_US == "Hello"
        assert i18n.zh_Hans is None

    def test_create_with_multiple_languages(self):
        """Create I18nString with multiple languages."""
        i18n = I18nString(
            en_US="Hello",
            zh_Hans="你好",
            zh_Hant="你好",
            ja_JP="こんにちは",
        )

        assert i18n.en_US == "Hello"
        assert i18n.zh_Hans == "你好"
        assert i18n.zh_Hant == "你好"
        assert i18n.ja_JP == "こんにちは"

    def test_to_dict_with_english_only(self):
        """to_dict returns only non-None fields."""
        i18n = I18nString(en_US="Hello")

        result = i18n.to_dict()

        assert result == {"en_US": "Hello"}

    def test_to_dict_with_multiple_languages(self):
        """to_dict returns all non-None fields."""
        i18n = I18nString(
            en_US="Hello",
            zh_Hans="你好",
        )

        result = i18n.to_dict()

        assert result == {"en_US": "Hello", "zh_Hans": "你好"}

    def test_to_dict_excludes_none(self):
        """to_dict excludes None values."""
        i18n = I18nString(
            en_US="Hello",
            zh_Hans=None,
            ja_JP="こんにちは",
        )

        result = i18n.to_dict()

        assert "zh_Hans" not in result
        assert "en_US" in result
        assert "ja_JP" in result

    def test_to_dict_all_languages(self):
        """to_dict with all supported languages."""
        i18n = I18nString(
            en_US="Hello",
            zh_Hans="你好",
            zh_Hant="你好",
            ja_JP="こんにちは",
            th_TH="สวัสดี",
            vi_VN="Xin chào",
            es_ES="Hola",
        )

        result = i18n.to_dict()

        assert len(result) == 7


class TestMetadata:
    """Tests for Metadata Pydantic model."""

    def test_create_minimal(self):
        """Create Metadata with required fields only."""
        from langbot.pkg.discover.engine import I18nString

        metadata = Metadata(
            name="test-component",
            label=I18nString(en_US="Test Component"),
        )

        assert metadata.name == "test-component"
        assert metadata.label.en_US == "Test Component"

    def test_create_with_all_fields(self):
        """Create Metadata with all optional fields."""
        from langbot.pkg.discover.engine import I18nString

        metadata = Metadata(
            name="test-component",
            label=I18nString(en_US="Test"),
            description=I18nString(en_US="A test component"),
            version="1.0.0",
            icon="test-icon",
            author="Test Author",
            repository="https://github.com/test/repo",
        )

        assert metadata.version == "1.0.0"
        assert metadata.icon == "test-icon"
        assert metadata.author == "Test Author"


class TestComponentManifest:
    """Tests for Component manifest detection."""

    def test_is_component_manifest_valid(self):
        """is_component_manifest returns True for valid manifest."""
        manifest = {
            'apiVersion': 'v1',
            'kind': 'Component',
            'metadata': {'name': 'test'},
            'spec': {},
        }

        assert Component.is_component_manifest(manifest) is True

    def test_is_component_manifest_missing_apiversion(self):
        """is_component_manifest returns False without apiVersion."""
        manifest = {
            'kind': 'Component',
            'metadata': {'name': 'test'},
            'spec': {},
        }

        assert Component.is_component_manifest(manifest) is False

    def test_is_component_manifest_missing_kind(self):
        """is_component_manifest returns False without kind."""
        manifest = {
            'apiVersion': 'v1',
            'metadata': {'name': 'test'},
            'spec': {},
        }

        assert Component.is_component_manifest(manifest) is False

    def test_is_component_manifest_missing_metadata(self):
        """is_component_manifest returns False without metadata."""
        manifest = {
            'apiVersion': 'v1',
            'kind': 'Component',
            'spec': {},
        }

        assert Component.is_component_manifest(manifest) is False

    def test_is_component_manifest_missing_spec(self):
        """is_component_manifest returns False without spec."""
        manifest = {
            'apiVersion': 'v1',
            'kind': 'Component',
            'metadata': {'name': 'test'},
        }

        assert Component.is_component_manifest(manifest) is False

    def test_is_component_manifest_empty(self):
        """is_component_manifest returns False for empty dict."""
        manifest = {}

        assert Component.is_component_manifest(manifest) is False

    def test_is_component_manifest_extra_fields_ok(self):
        """is_component_manifest accepts extra fields."""
        manifest = {
            'apiVersion': 'v1',
            'kind': 'Component',
            'metadata': {'name': 'test'},
            'spec': {},
            'extraField': 'ignored',
        }

        assert Component.is_component_manifest(manifest) is True
