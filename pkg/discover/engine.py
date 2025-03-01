from __future__ import annotations

import typing
import importlib
import os
import inspect

import yaml
import pydantic

from ..core import app


class I18nString(pydantic.BaseModel):
    """国际化字符串"""

    en_US: str
    """英文"""

    zh_CN: typing.Optional[str] = None
    """中文"""

    ja_JP: typing.Optional[str] = None
    """日文"""


class Metadata(pydantic.BaseModel):
    """元数据"""

    name: str
    """名称"""

    label: I18nString
    """标签"""

    description: typing.Optional[I18nString] = None
    """描述"""

    icon: typing.Optional[str] = None
    """图标"""


class PythonExecution(pydantic.BaseModel):
    """Python执行"""

    path: str
    """路径"""

    attr: str
    """属性"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.path.startswith('./'):
            self.path = self.path[2:]


class Execution(pydantic.BaseModel):
    """执行"""

    python: PythonExecution
    """Python执行"""


class Component(pydantic.BaseModel):
    """组件清单"""

    owner: str
    """组件所属"""

    manifest: typing.Dict[str, typing.Any]
    """组件清单内容"""

    rel_path: str
    """组件清单相对main.py的路径"""

    _metadata: Metadata
    """组件元数据"""

    _spec: typing.Dict[str, typing.Any]
    """组件规格"""

    _execution: Execution
    """组件执行"""

    def __init__(self, owner: str, manifest: typing.Dict[str, typing.Any], rel_path: str):
        super().__init__(
            owner=owner,
            manifest=manifest,
            rel_path=rel_path
        )
        self._metadata = Metadata(**manifest['metadata'])
        self._spec = manifest['spec']
        self._execution = Execution(**manifest['execution']) if 'execution' in manifest else None

    @property
    def kind(self) -> str:
        """组件类型"""
        return self.manifest['kind']
    
    @property
    def metadata(self) -> Metadata:
        """组件元数据"""
        return self._metadata
    
    @property
    def spec(self) -> typing.Dict[str, typing.Any]:
        """组件规格"""
        return self._spec
    
    @property
    def execution(self) -> Execution:
        """组件执行"""
        return self._execution
    
    def get_python_component_class(self) -> typing.Type[typing.Any]:
        """获取Python组件类"""
        parent_path = os.path.dirname(self.rel_path)
        module_path = os.path.join(parent_path, self.execution.python.path)
        if module_path.endswith('.py'):
            module_path = module_path[:-3]
        module_path = module_path.replace('/', '.').replace('\\', '.')
        module = importlib.import_module(module_path)
        return getattr(module, self.execution.python.attr)


class ComponentDiscoveryEngine:
    """组件发现引擎"""

    ap: app.Application
    """应用实例"""

    components: typing.Dict[str, typing.List[Component]] = {}
    """组件列表"""

    def __init__(self, ap: app.Application):
        self.ap = ap

    def load_component_manifest(self, path: str, owner: str = 'builtin', no_save: bool = False) -> Component:
        """加载组件清单"""
        with open(path, 'r', encoding='utf-8') as f:
            manifest = yaml.safe_load(f)
            comp = Component(
                owner=owner,
                manifest=manifest,
                rel_path=path
            )
            if not no_save:
                if comp.kind not in self.components:
                    self.components[comp.kind] = []
                self.components[comp.kind].append(comp)
            return comp
        
    def load_component_manifests_in_dir(self, path: str, owner: str = 'builtin', no_save: bool = False) -> typing.List[Component]:
        """加载目录中的组件清单"""
        components: typing.List[Component] = []
        for file in os.listdir(path):
            if file.endswith('.yaml') or file.endswith('.yml'):
                components.append(self.load_component_manifest(os.path.join(path, file), owner, no_save))
        return components
    
    def load_blueprint_comp_group(self, group: dict, owner: str = 'builtin', no_save: bool = False) -> typing.List[Component]:
        """加载蓝图组件组"""
        components: typing.List[Component] = []
        if 'fromFiles' in group:
            for file in group['fromFiles']:
                components.append(self.load_component_manifest(file, owner, no_save))
        if 'fromDirs' in group:
            for dir in group['fromDirs']:
                path = dir['path']
                # depth = dir['depth']
                components.extend(self.load_component_manifests_in_dir(path, owner, no_save))
        return components

    def discover_blueprint(self, blueprint_manifest_path: str, owner: str = 'builtin'):
        """发现蓝图"""
        blueprint_manifest = self.load_component_manifest(blueprint_manifest_path, owner, no_save=True)
        assert blueprint_manifest.kind == 'Blueprint', '`Kind` must be `Blueprint`'
        components: typing.Dict[str, typing.List[Component]] = {}

        # load ComponentTemplate first
        if 'ComponentTemplate' in blueprint_manifest.spec['components']:
            components['ComponentTemplate'] = self.load_blueprint_comp_group(blueprint_manifest.spec['components']['ComponentTemplate'], owner)

        for name, component in blueprint_manifest.spec['components'].items():
            if name == 'ComponentTemplate':
                continue
            components[name] = self.load_blueprint_comp_group(component, owner)
        
        self.ap.logger.debug(f'Components: {components}')

        return blueprint_manifest, components


    def get_components_by_kind(self, kind: str) -> typing.List[Component]:
        """获取指定类型的组件"""
        if kind not in self.components:
            raise ValueError(f'No components found for kind: {kind}')
        return self.components[kind]
