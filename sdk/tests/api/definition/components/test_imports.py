"""Regression test for components module imports.

This test verifies that all exported components can be imported successfully.
"""

from __future__ import annotations


def test_components_import_success():
    """Test that all exported components can be imported without ImportError.

    This is a regression test to ensure we don't accidentally export
    symbols that don't exist in the codebase.
    """
    # Should succeed without ImportError
    from langbot_plugin.api.definition.components import (
        BaseComponent,
        Command,
        Tool,
        EventListener,
        Runner,
    )

    # Verify they are the expected classes
    assert BaseComponent.__name__ == "BaseComponent"
    assert Command.__kind__ == "Command"
    assert Tool.__kind__ == "Tool"
    assert EventListener.__kind__ == "EventListener"
    assert Runner.__kind__ == "Runner"


def test_components_all_exports_exist():
    """Test that __all__ only contains symbols that can be imported."""
    import langbot_plugin.api.definition.components as components

    for name in components.__all__:
        # Each exported name must be accessible
        assert hasattr(components, name), f"{name} in __all__ but not importable"


def test_no_polymorphic_component_export():
    """Verify PolymorphicComponent is NOT exported (does not exist in codebase).

    This prevents accidental reintroduction of non-existent symbols.
    """
    import langbot_plugin.api.definition.components as components

    # PolymorphicComponent should NOT be in __all__ or importable
    assert "PolymorphicComponent" not in components.__all__
    assert not hasattr(components, "PolymorphicComponent")


def test_no_knowledge_retriever_export():
    """Verify KnowledgeRetriever is NOT exported (does not exist in codebase).

    KnowledgeEngine exists instead. KnowledgeRetriever is historical.
    """
    import langbot_plugin.api.definition.components as components

    # KnowledgeRetriever should NOT be in __all__ or importable
    assert "KnowledgeRetriever" not in components.__all__
    assert not hasattr(components, "KnowledgeRetriever")
