from typing import Dict, List, Type

import pydantic.v1.main as pdm
from pydantic.v1 import BaseModel


class PlatformMetaclass(pdm.ModelMetaclass):
    """此类是平台中使用的 pydantic 模型的元类的基类。"""


def to_camel(name: str) -> str:
    """将下划线命名风格转换为小驼峰命名。"""
    if name[:2] == '__':  # 不处理双下划线开头的特殊命名。
        return name
    name_parts = name.split('_')
    return ''.join(name_parts[:1] + [x.title() for x in name_parts[1:]])


class PlatformBaseModel(BaseModel, metaclass=PlatformMetaclass):
    """模型基类。

    启用了三项配置：
    1. 允许解析时传入额外的值，并将额外值保存在模型中。
    2. 允许通过别名访问字段。
    3. 自动生成小驼峰风格的别名。
    """

    def __init__(self, *args, **kwargs):
        """"""
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return (
            self.__class__.__name__ + '(' + ', '.join((f'{k}={repr(v)}' for k, v in self.__dict__.items() if v)) + ')'
        )

    class Config:
        extra = 'allow'
        allow_population_by_field_name = True
        alias_generator = to_camel


class PlatformIndexedMetaclass(PlatformMetaclass):
    """可以通过子类名获取子类的类的元类。"""

    __indexedbases__: List[Type['PlatformIndexedModel']] = []
    __indexedmodel__ = None

    def __new__(cls, name, bases, attrs, **kwargs):
        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        # 第一类：PlatformIndexedModel
        if name == 'PlatformIndexedModel':
            cls.__indexedmodel__ = new_cls
            new_cls.__indexes__ = {}
            return new_cls
        # 第二类：PlatformIndexedModel 的直接子类，这些是可以通过子类名获取子类的类。
        if cls.__indexedmodel__ in bases:
            cls.__indexedbases__.append(new_cls)
            new_cls.__indexes__ = {}
            return new_cls
        # 第三类：PlatformIndexedModel 的直接子类的子类，这些添加到直接子类的索引中。
        for base in cls.__indexedbases__:
            if issubclass(new_cls, base):
                base.__indexes__[name] = new_cls
                return new_cls

    def __getitem__(cls, name):
        return cls.get_subtype(name)


class PlatformIndexedModel(PlatformBaseModel, metaclass=PlatformIndexedMetaclass):
    """可以通过子类名获取子类的类。"""

    __indexes__: Dict[str, Type['PlatformIndexedModel']]

    @classmethod
    def get_subtype(cls, name: str) -> Type['PlatformIndexedModel']:
        """根据类名称，获取相应的子类类型。

        Args:
            name: 类名称。

        Returns:
            Type['PlatformIndexedModel']: 子类类型。
        """
        try:
            type_ = cls.__indexes__.get(name)
            if not (type_ and issubclass(type_, cls)):
                raise ValueError(f'`{name}` 不是 `{cls.__name__}` 的子类！')
            return type_
        except AttributeError:
            raise ValueError(f'`{name}` 不是 `{cls.__name__}` 的子类！') from None

    @classmethod
    def parse_subtype(cls, obj: dict) -> 'PlatformIndexedModel':
        """通过字典，构造对应的模型对象。

        Args:
            obj: 一个字典，包含了模型对象的属性。

        Returns:
            PlatformIndexedModel: 构造的对象。
        """
        if cls in PlatformIndexedModel.__subclasses__():
            ModelType = cls.get_subtype(obj['type'])
            return ModelType.parse_obj(obj)
        return super().parse_obj(obj)
