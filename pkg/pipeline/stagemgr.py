from __future__ import annotations

import pydantic

from ..core import app
from . import stage
from .resprule import resprule
from .bansess import bansess
from .cntfilter import cntfilter
from .process import process
from .longtext import longtext
from .respback import respback
from .wrapper import wrapper
from .preproc import preproc
from .ratelimit import ratelimit


# 请求处理阶段顺序
stage_order = [
    "GroupRespondRuleCheckStage",
    "BanSessionCheckStage",
    "PreContentFilterStage",
    "PreProcessor",
    "RequireRateLimitOccupancy",
    "MessageProcessor",
    "ReleaseRateLimitOccupancy",
    "PostContentFilterStage",
    "ResponseWrapper",
    "LongTextProcessStage",
    "SendResponseBackStage",
]


class StageInstContainer():
    """阶段实例容器
    """

    inst_name: str

    inst: stage.PipelineStage

    def __init__(self, inst_name: str, inst: stage.PipelineStage):
        self.inst_name = inst_name
        self.inst = inst


class StageManager:
    ap: app.Application

    stage_containers: list[StageInstContainer]

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.stage_containers = []

    async def initialize(self):
        """初始化
        """
        
        for name, cls in stage._stage_classes.items():
            self.stage_containers.append(StageInstContainer(
                inst_name=name,
                inst=cls(self.ap)
            ))
            
        for stage_containers in self.stage_containers:
            await stage_containers.inst.initialize()

        # 按照 stage_order 排序
        self.stage_containers.sort(key=lambda x: stage_order.index(x.inst_name))
