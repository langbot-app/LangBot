from __future__ import annotations

import pydantic

from ..core import app
from . import stage
from .resprule import resprule
from .bansess import bansess
from .cntfilter import cntfilter
from .longtext import longtext


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
