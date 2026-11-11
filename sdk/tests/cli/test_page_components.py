from __future__ import annotations

from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.cli.utils.page_components import populate_plugin_pages


def _manifest(kind: str, name: str, rel_path: str, spec=None) -> ComponentManifest:
    return ComponentManifest(
        owner="tester",
        manifest={
            "apiVersion": "v1",
            "kind": kind,
            "metadata": {
                "name": name,
                "label": {"en_US": name.title()},
            },
            "spec": spec or {},
        },
        rel_path=rel_path,
    )


def test_populate_plugin_pages_merges_existing_and_component_pages():
    plugin = _manifest(
        "Plugin",
        "demo",
        "manifest.yaml",
        spec={
            "components": {},
            "pages": [{"id": "existing", "label": {"en_US": "Existing"}, "path": "x"}],
        },
    )
    component = _manifest(
        "Page",
        "settings",
        "components/pages/settings.yaml",
        spec={"path": "settings.html"},
    )

    populate_plugin_pages(plugin, [component])

    assert plugin.manifest["spec"]["pages"] == [
        {"id": "existing", "label": {"en_US": "Existing"}, "path": "x"},
        {
            "id": "settings",
            "label": {"en_US": "Settings"},
            "path": "components/pages/settings.html",
        },
    ]


def test_populate_plugin_pages_deduplicates_page_ids():
    plugin = _manifest(
        "Plugin",
        "demo",
        "manifest.yaml",
        spec={"components": {}, "pages": [{"id": "settings", "path": "existing"}]},
    )
    component = _manifest("Page", "settings", "components/pages/settings.yaml")

    populate_plugin_pages(plugin, [component])

    assert plugin.manifest["spec"]["pages"] == [{"id": "settings", "path": "existing"}]
