from __future__ import annotations

import posixpath
from typing import Any

from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine


def discover_plugin_components(
    plugin_manifest: ComponentManifest,
    discovery_engine: ComponentDiscoveryEngine,
) -> list[ComponentManifest]:
    component_manifests: list[ComponentManifest] = []

    for comp_group in plugin_manifest.spec["components"].values():
        manifests = discovery_engine.load_blueprint_comp_group(
            comp_group, owner="builtin", no_save=True
        )
        component_manifests.extend(manifests)

    return component_manifests


def populate_plugin_pages(
    plugin_manifest: ComponentManifest,
    component_manifests: list[ComponentManifest],
) -> None:
    pages: list[dict[str, Any]] = []
    seen_page_ids: set[str] = set()

    for page in plugin_manifest.manifest.get("spec", {}).get("pages", []):
        if isinstance(page, dict) and page.get("id") not in seen_page_ids:
            pages.append(page)
            seen_page_ids.add(page.get("id", ""))

    for component_manifest in component_manifests:
        if component_manifest.kind != "Page":
            continue

        page_id = component_manifest.metadata.name
        if page_id in seen_page_ids:
            continue

        yaml_dir = posixpath.dirname(component_manifest.rel_path.replace("\\", "/"))
        html_rel_path = component_manifest.spec.get("path", "index.html")
        page_entry = {
            "id": page_id,
            "label": component_manifest.manifest["metadata"].get("label", {}),
            "path": posixpath.normpath(
                posixpath.join(yaml_dir, str(html_rel_path).replace("\\", "/"))
            ),
        }

        pages.append(page_entry)
        seen_page_ids.add(page_id)

    plugin_manifest.manifest["spec"]["pages"] = pages
