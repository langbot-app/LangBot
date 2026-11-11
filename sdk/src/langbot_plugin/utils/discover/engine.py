from __future__ import annotations

import logging
import typing
import os
import yaml

from langbot_plugin.api.definition.components.manifest import (
    ComponentManifest,
    InvalidRunnerManifest,
)


class ComponentDiscoveryEngine:
    """组件发现引擎"""

    components: typing.Dict[str, typing.List[ComponentManifest]] = {}
    """组件列表"""

    def __init__(self):
        self.components = {}

    def load_component_manifest(
        self, path: str, owner: str = "builtin", no_save: bool = False
    ) -> ComponentManifest | None:
        """加载组件清单"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)
                if (
                    isinstance(manifest, dict)
                    and manifest.get("kind") == "Runner"
                    and "spec" not in manifest
                ):
                    raise InvalidRunnerManifest(
                        f"Invalid Runner manifest {path}: spec.usages is required"
                    )
                if not ComponentManifest.is_component_manifest(manifest):
                    return None

                comp = ComponentManifest(owner=owner, manifest=manifest, rel_path=path)
                if not no_save:
                    if comp.kind not in self.components:
                        self.components[comp.kind] = []
                    self.components[comp.kind].append(comp)
                return comp
        except InvalidRunnerManifest:
            # Build, debug and runtime discovery must fail instead of silently
            # packaging or loading a Runner with an ambiguous product usage.
            raise
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Failed to load component manifest {path}: {e}"
            )
            return None

    def load_component_manifests_in_dir(
        self,
        path: str,
        owner: str = "builtin",
        no_save: bool = False,
        max_depth: int = 1,
    ) -> typing.List[ComponentManifest]:
        """加载目录中的组件清单"""
        components: typing.List[ComponentManifest] = []

        def recursive_load_component_manifests_in_dir(path: str, depth: int = 1):
            if depth > max_depth:
                return
            for file in os.listdir(path):
                if (not os.path.isdir(os.path.join(path, file))) and (
                    file.endswith(".yaml") or file.endswith(".yml")
                ):
                    comp = self.load_component_manifest(
                        os.path.join(path, file), owner, no_save
                    )
                    if comp is not None:
                        components.append(comp)
                elif os.path.isdir(os.path.join(path, file)):
                    recursive_load_component_manifests_in_dir(
                        os.path.join(path, file), depth + 1
                    )

        recursive_load_component_manifests_in_dir(path)
        return components

    def load_blueprint_comp_group(
        self, group: dict, owner: str = "builtin", no_save: bool = False
    ) -> typing.List[ComponentManifest]:
        """加载蓝图组件组"""
        components: typing.List[ComponentManifest] = []
        if "fromFiles" in group:
            for file in group["fromFiles"]:
                comp = self.load_component_manifest(file, owner, no_save)
                if comp is not None:
                    components.append(comp)
        if "fromDirs" in group:
            for dir in group["fromDirs"]:
                path = dir["path"]
                max_depth = dir["maxDepth"] if "maxDepth" in dir else 1
                components.extend(
                    self.load_component_manifests_in_dir(
                        path, owner, no_save, max_depth
                    )
                )
        return components

    def discover_blueprint(self, blueprint_manifest_path: str, owner: str = "builtin"):
        """发现蓝图"""
        blueprint_manifest = self.load_component_manifest(
            blueprint_manifest_path, owner, no_save=True
        )
        if blueprint_manifest is None:
            raise ValueError(f"Invalid blueprint manifest: {blueprint_manifest_path}")
        assert blueprint_manifest.kind == "Blueprint", "`Kind` must be `Blueprint`"
        components: typing.Dict[str, typing.List[ComponentManifest]] = {}

        # load ComponentTemplate first
        if "ComponentTemplate" in blueprint_manifest.spec["components"]:
            components["ComponentTemplate"] = self.load_blueprint_comp_group(
                blueprint_manifest.spec["components"]["ComponentTemplate"], owner
            )

        for name, component in blueprint_manifest.spec["components"].items():
            if name == "ComponentTemplate":
                continue
            components[name] = self.load_blueprint_comp_group(component, owner)

        return blueprint_manifest, components

    def get_components_by_kind(self, kind: str) -> typing.List[ComponentManifest]:
        """获取指定类型的组件"""
        if kind not in self.components:
            return []
        return self.components[kind]

    def find_components(
        self, kind: str, component_list: typing.List[ComponentManifest]
    ) -> typing.List[ComponentManifest]:
        """查找组件"""
        result: typing.List[ComponentManifest] = []
        for component in component_list:
            if component.kind == kind:
                result.append(component)
        return result
