from __future__ import annotations

import typing
import importlib
import os
import pydantic
import sys


class InvalidRunnerManifest(ValueError):
    """A Runner must explicitly declare its supported product usages."""


class RunnerUsageSpec(pydantic.BaseModel):
    usages: list[typing.Literal["agent", "event"]] = pydantic.Field(min_length=1)
    events: list[str] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_events(self) -> RunnerUsageSpec:
        if "event" in self.usages and not self.events:
            raise ValueError("Event usage requires an explicit spec.events declaration")
        return self


class I18nString(pydantic.BaseModel):
    """Internationalized string"""

    en_US: str
    """English"""

    zh_Hans: typing.Optional[str] = None
    """Simplified Chinese"""

    zh_Hant: typing.Optional[str] = None
    """Traditional Chinese"""

    ja_JP: typing.Optional[str] = None
    """Japanese"""

    th_TH: typing.Optional[str] = None
    """Thai"""

    vi_VN: typing.Optional[str] = None
    """Vietnamese"""

    es_ES: typing.Optional[str] = None
    """Spanish"""

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        dic = {}
        if self.en_US is not None:
            dic["en_US"] = self.en_US
        if self.zh_Hans is not None:
            dic["zh_Hans"] = self.zh_Hans
        if self.zh_Hant is not None:
            dic["zh_Hant"] = self.zh_Hant
        if self.ja_JP is not None:
            dic["ja_JP"] = self.ja_JP
        if self.th_TH is not None:
            dic["th_TH"] = self.th_TH
        if self.vi_VN is not None:
            dic["vi_VN"] = self.vi_VN
        if self.es_ES is not None:
            dic["es_ES"] = self.es_ES
        return dic


class Metadata(pydantic.BaseModel):
    """元数据"""

    name: str
    """名称"""

    label: I18nString
    """标签"""

    description: typing.Optional[I18nString] = None
    """描述"""

    version: typing.Optional[str] = None
    """版本"""

    icon: typing.Optional[str] = None
    """图标"""

    author: typing.Optional[str] = None
    """作者"""

    repository: typing.Optional[str] = None
    """仓库"""

    license: typing.Optional[str] = None
    """开源协议（SPDX 标识符，如 MIT / Apache-2.0）"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.description is None:
            self.description = I18nString(en_US="")

        if self.icon is None:
            self.icon = ""


class PythonExecution(pydantic.BaseModel):
    """Python执行"""

    path: str
    """路径"""

    attr: str
    """属性"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.path.startswith("./"):
            self.path = self.path[2:]


class Execution(pydantic.BaseModel):
    """执行"""

    python: PythonExecution
    """Python执行"""

    shared_runtime: typing.Literal["shared-runtime-v1"] | None = pydantic.Field(
        default=None,
        alias="sharedRuntime",
    )
    """Certified shared runtime profile; absent manifests use a dedicated runtime."""

    component_model: typing.Literal["stateless-v1"] | None = pydantic.Field(
        default=None,
        alias="componentModel",
    )
    """Singleton, task-local component contract required for certification."""

    @pydantic.model_validator(mode="before")
    @classmethod
    def _require_supported_shared_runtime_when_present(cls, values: typing.Any):
        if (
            isinstance(values, dict)
            and "sharedRuntime" in values
            and values["sharedRuntime"] != "shared-runtime-v1"
        ):
            raise ValueError("sharedRuntime must be shared-runtime-v1 when present")
        return values


class ComponentManifest(pydantic.BaseModel):
    """组件清单"""

    owner: str
    """组件所属"""

    manifest: typing.Dict[str, typing.Any]
    """组件清单内容"""

    rel_path: str
    """组件清单相对main.py的路径"""

    _rel_dir: str
    """组件清单相对main.py的目录"""

    _metadata: Metadata
    """组件元数据"""

    _spec: typing.Dict[str, typing.Any]
    """组件规格"""

    _execution: Execution | None
    """组件执行"""

    def __init__(
        self, owner: str, manifest: typing.Dict[str, typing.Any], rel_path: str
    ):
        super().__init__(
            owner=owner,
            manifest=manifest,
            rel_path=rel_path,
        )
        self._metadata = Metadata(**manifest["metadata"])
        self._spec = manifest["spec"]
        if manifest.get("kind") == "Plugin" and "permissions" in self._spec:
            from langbot_plugin.api.entities.permissions import PluginPermissions

            PluginPermissions.model_validate(self._spec["permissions"])
        if manifest.get("kind") == "Runner":
            try:
                RunnerUsageSpec.model_validate(self._spec)
            except pydantic.ValidationError as exc:
                raise InvalidRunnerManifest(
                    f"Invalid Runner manifest {rel_path}: {exc}"
                ) from exc
        self._rel_dir = os.path.dirname(rel_path)
        self._execution = (
            Execution(**manifest["execution"]) if "execution" in manifest else None
        )

    @classmethod
    def is_component_manifest(cls, manifest: typing.Dict[str, typing.Any]) -> bool:
        """判断是否为组件清单"""
        return (
            "apiVersion" in manifest
            and "kind" in manifest
            and "metadata" in manifest
            and "spec" in manifest
        )

    @property
    def kind(self) -> str:
        """组件类型"""
        return self.manifest["kind"]

    @property
    def metadata(self) -> Metadata:
        """组件元数据"""
        return self._metadata

    @property
    def spec(self) -> typing.Dict[str, typing.Any]:
        """组件规格"""
        return self._spec

    @property
    def execution(self) -> Execution | None:
        """组件可执行文件信息"""
        return self._execution

    @property
    def icon_rel_path(self) -> str | None:
        """图标相对路径"""
        return (
            os.path.join(self._rel_dir, self.metadata.icon)
            if self.metadata.icon is not None and self.metadata.icon.strip() != ""
            else None
        )

    def _resolve_component_module(self) -> tuple[str, str]:
        """Return the plugin directory to import from and the module path.

        ``execution.python.path`` comes from the plugin's own manifest, so it is
        untrusted input. Only a module inside the plugin directory may be
        imported: absolute paths, drive letters and ``..`` components are
        rejected outright rather than relied on to fail later during import.
        """
        if self.execution is None:
            raise ValueError("Execution is not set")
        python = self.execution.python
        declared = python.path or ""
        if not declared or "\x00" in declared:
            raise ValueError("execution.python.path is empty")

        portable = declared.replace("\\", "/")
        if portable.startswith("/") or os.path.isabs(declared):
            raise ValueError(
                f"execution.python.path must be relative to the plugin: {declared}"
            )
        if any(part == ".." for part in portable.split("/")):
            raise ValueError(
                f"execution.python.path escapes the plugin directory: {declared}"
            )
        if len(portable.split("/", 1)[0]) >= 2 and portable.split("/", 1)[0][1] == ":":
            raise ValueError(f"execution.python.path uses a drive letter: {declared}")

        # Workers run at the plugin root; _rel_dir is the manifest's directory.
        # Keep that directory in the module name so relative imports still work.
        plugin_dir = os.path.abspath(".")
        target = os.path.abspath(os.path.join(plugin_dir, self._rel_dir, portable))
        if os.path.commonpath([plugin_dir, target]) != plugin_dir:
            raise ValueError(
                f"execution.python.path escapes the plugin directory: {declared}"
            )

        if target.endswith(".py"):
            target = target[: -len(".py")]
        relative = os.path.relpath(target, plugin_dir)
        return plugin_dir, relative.replace(os.sep, ".").replace("/", ".")

    def get_python_component_class(self) -> typing.Type[typing.Any]:
        """获取Python组件类"""
        if self.execution is None:
            raise ValueError("Execution is not set")
        plugin_dir, module_path = self._resolve_component_module()
        # Insert for the duration of the import only: a permanent append would
        # let one plugin shadow modules for every plugin loaded after it.
        sys.path.insert(0, plugin_dir)
        try:
            module = importlib.import_module(module_path)
        finally:
            try:
                sys.path.remove(plugin_dir)
            except ValueError:  # pragma: no cover - defensive
                pass
        return getattr(module, self.execution.python.attr)

    def to_plain_dict(self) -> dict:
        """转换为平铺字典"""
        return {
            "name": self.metadata.name,
            "label": self.metadata.label.to_dict(),
            "description": self.metadata.description.to_dict()
            if self.metadata.description is not None
            else None,
            "icon": self.metadata.icon,
            "spec": self.spec,
        }
