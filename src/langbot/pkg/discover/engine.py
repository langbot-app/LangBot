from __future__ import annotations

import typing
import importlib
import os
import yaml
import pydantic

from langbot.pkg.core import app
from langbot.pkg.utils import importutil


class I18nString(pydantic.BaseModel):
    """国际化字符串"""

    en_US: str
    """英文"""

    zh_Hans: typing.Optional[str] = None
    """中文"""

    ja_JP: typing.Optional[str] = None
    """日文"""

    def to_dict(self) -> dict:
        """转换为字典"""
        dic = {}
        if self.en_US is not None:
            dic['en_US'] = self.en_US
        if self.zh_Hans is not None:
            dic['zh_Hans'] = self.zh_Hans
        if self.ja_JP is not None:
            dic['ja_JP'] = self.ja_JP
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.description is None:
            self.description = I18nString(en_US='')

        if self.icon is None:
            self.icon = ''


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

    rel_dir: str
    """组件清单相对main.py的目录"""

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
            rel_path=rel_path,
            rel_dir=os.path.dirname(rel_path),
        )
        self._metadata = Metadata(**manifest['metadata'])
        self._spec = manifest['spec']
        self._execution = Execution(**manifest['execution']) if 'execution' in manifest else None

    @classmethod
    def is_component_manifest(cls, manifest: typing.Dict[str, typing.Any]) -> bool:
        """判断是否为组件清单"""
        return 'apiVersion' in manifest and 'kind' in manifest and 'metadata' in manifest and 'spec' in manifest

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
        """组件可执行文件信息"""
        return self._execution

    @property
    def icon_rel_path(self) -> str:
        """图标相对路径"""
        return (
            os.path.join(self.rel_dir, self.metadata.icon)
            if self.metadata.icon is not None and self.metadata.icon.strip() != ''
            else None
        )

    def get_python_component_class(self) -> typing.Type[typing.Any]:
        """获取Python组件类"""
        module_path = os.path.join(self.rel_dir, self.execution.python.path)
        if module_path.endswith('.py'):
            module_path = module_path[:-3]
        module_path = module_path.replace('/', '.').replace('\\', '.')
        module = importlib.import_module(f'langbot.{module_path}')
        return getattr(module, self.execution.python.attr)

    def to_plain_dict(self) -> dict:
        """转换为平铺字典"""
        return {
            'name': self.metadata.name,
            'label': self.metadata.label.to_dict(),
            'description': self.metadata.description.to_dict(),
            'icon': self.metadata.icon,
            'spec': self.spec,
        }


class ComponentDiscoveryEngine:
    """组件发现引擎"""

    ap: app.Application
    """应用实例"""

    components: typing.Dict[str, typing.List[Component]] = {}
    """组件列表"""

    def __init__(self, ap: app.Application):
        self.ap = ap

    def load_component_manifest(self, path: str, owner: str = 'builtin', no_save: bool = False) -> Component | None:
        """加载组件清单"""
        # with open(path, 'r', encoding='utf-8') as f:
        #     manifest = yaml.safe_load(f)
        manifest = yaml.safe_load(importutil.read_resource_file(path))
        if not Component.is_component_manifest(manifest):
            return None
        comp = Component(owner=owner, manifest=manifest, rel_path=path)
        if not no_save:
            if comp.kind not in self.components:
                self.components[comp.kind] = []
            self.components[comp.kind].append(comp)
        return comp

    def load_component_manifests_in_dir(
        self,
        path: str,
        owner: str = 'builtin',
        no_save: bool = False,
        max_depth: int = 1,
    ) -> typing.List[Component]:
        """加载目录中的组件清单"""
        components: typing.List[Component] = []

        def recursive_load_component_manifests_in_dir(path: str, depth: int = 1):
            if depth > max_depth:
                return

            for file in importutil.list_resource_files(path):
                if (not os.path.isdir(os.path.join(path, file))) and (file.endswith('.yaml') or file.endswith('.yml')):
                    comp = self.load_component_manifest(os.path.join(path, file), owner, no_save)
                    if comp is not None:
                        components.append(comp)
                elif os.path.isdir(os.path.join(path, file)):
                    recursive_load_component_manifests_in_dir(os.path.join(path, file), depth + 1)

        recursive_load_component_manifests_in_dir(path)
        return components

    def load_blueprint_comp_group(
        self, group: dict, owner: str = 'builtin', no_save: bool = False
    ) -> typing.List[Component]:
        """加载蓝图组件组"""
        components: typing.List[Component] = []
        if 'fromFiles' in group:
            for file in group['fromFiles']:
                comp = self.load_component_manifest(file, owner, no_save)
                if comp is not None:
                    components.append(comp)
        if 'fromDirs' in group:
            for dir in group['fromDirs']:
                path = dir['path']
                max_depth = dir['maxDepth'] if 'maxDepth' in dir else 1
                components.extend(self.load_component_manifests_in_dir(path, owner, no_save, max_depth))
        return components

    def discover_blueprint(self, blueprint_manifest_path: str, owner: str = 'builtin'):
        """发现蓝图"""
        blueprint_manifest = self.load_component_manifest(blueprint_manifest_path, owner, no_save=True)
        if blueprint_manifest is None:
            raise ValueError(f'Invalid blueprint manifest: {blueprint_manifest_path}')
        assert blueprint_manifest.kind == 'Blueprint', '`Kind` must be `Blueprint`'
        components: typing.Dict[str, typing.List[Component]] = {}

        # load ComponentTemplate first
        if 'ComponentTemplate' in blueprint_manifest.spec['components']:
            components['ComponentTemplate'] = self.load_blueprint_comp_group(
                blueprint_manifest.spec['components']['ComponentTemplate'], owner
            )

        for name, component in blueprint_manifest.spec['components'].items():
            if name == 'ComponentTemplate':
                continue
            components[name] = self.load_blueprint_comp_group(component, owner)

        self.ap.logger.debug(f'Components: {components}')

        return blueprint_manifest, components

    def get_components_by_kind(self, kind: str) -> typing.List[Component]:
        """获取指定类型的组件"""
        if kind not in self.components:
            return []
        return self.components[kind]

    def find_components(self, kind: str, component_list: typing.List[Component]) -> typing.List[Component]:
        """查找组件"""
        result: typing.List[Component] = []
        for component in component_list:
            if component.kind == kind:
                result.append(component)
        return result
