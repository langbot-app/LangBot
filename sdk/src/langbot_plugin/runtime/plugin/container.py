# Plugin runtime container

from __future__ import annotations

import typing
import enum
import pydantic
from dataclasses import dataclass

from langbot_plugin.api.definition.plugin import NonePlugin
from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.definition.components.base import BaseComponent, NoneComponent
from langbot_plugin.api.definition.components.manifest import ComponentManifest


class RuntimeContainerStatus(enum.Enum):
    """插件容器状态"""

    UNMOUNTED = "unmounted"
    """未加载进内存"""

    MOUNTED = "mounted"
    """已加载进内存"""

    INITIALIZED = "initialized"
    """已初始化"""


class PluginContainer(pydantic.BaseModel):
    """The container for running plugins."""

    debug: bool = False
    """是否为调试插件"""

    install_source: str = ""
    """插件安装来源"""

    install_info: dict[str, typing.Any] = {}
    """插件安装信息"""

    manifest: ComponentManifest
    """插件清单"""

    plugin_instance: BasePlugin
    """插件实例"""

    enabled: bool
    """插件是否启用"""

    priority: int
    """插件优先级"""

    plugin_config: dict[str, typing.Any]
    """插件配置"""

    status: RuntimeContainerStatus
    """插件容器状态"""

    components: list[ComponentContainer]
    """组件容器列表"""

    _runtime_plugin_handler: typing.Any = pydantic.PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True

    def model_dump(self):
        return {
            "debug": self.debug,
            "install_source": self.install_source,
            "install_info": self.install_info,
            "manifest": self.manifest.model_dump(),
            "plugin_instance": None,  # not serializable
            "enabled": self.enabled,
            "priority": self.priority,
            "plugin_config": self.plugin_config,
            "status": self.status.value,
            "components": [component.model_dump() for component in self.components],
        }

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> PluginContainer:
        return cls(
            debug=data["debug"],
            install_source=data.get("install_source", ""),
            install_info=data.get("install_info", {}),
            manifest=ComponentManifest.model_validate(data["manifest"]),
            plugin_instance=NonePlugin(),
            enabled=data["enabled"],
            priority=data["priority"],
            plugin_config=data["plugin_config"],
            status=RuntimeContainerStatus(data["status"]),
            components=[
                ComponentContainer.from_dict(component)
                for component in data["components"]
            ],
        )


class ComponentContainer(pydantic.BaseModel):
    """The container for running components."""

    manifest: ComponentManifest
    """组件清单"""

    component_instance: BaseComponent
    """组件实例"""

    component_config: dict[str, typing.Any]
    """组件配置"""

    class Config:
        arbitrary_types_allowed = True

    def model_dump(self):
        return {
            "manifest": self.manifest.model_dump(),
            "component_instance": None,  # not serializable
            "component_config": self.component_config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> ComponentContainer:
        return cls(
            manifest=ComponentManifest.model_validate(data["manifest"]),
            component_instance=NoneComponent(),
            component_config=data["component_config"],
        )


PluginContainer.model_rebuild()


@dataclass(frozen=True, slots=True)
class PluginInstallationSlot:
    """Lightweight tenant state pointing at one process-wide object graph."""

    binding: typing.Any
    enabled: bool
    priority: int
    plugin_config: typing.Mapping[str, typing.Any]
    plugin_container: PluginContainer
