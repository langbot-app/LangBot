from __future__ import annotations

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
from .msgtrun import msgtrun


# 请求处理阶段顺序
stage_order = [
    "GroupRespondRuleCheckStage",  # 群响应规则检查
    "BanSessionCheckStage",  # 封禁会话检查
    "PreContentFilterStage",  # 内容过滤前置阶段
    "PreProcessor",  # 预处理器
    "ConversationMessageTruncator",  # 会话消息截断器
    "RequireRateLimitOccupancy",  # 请求速率限制占用
    "MessageProcessor",  # 处理器
    "ReleaseRateLimitOccupancy",  # 释放速率限制占用
    "PostContentFilterStage",  # 内容过滤后置阶段
    "ResponseWrapper",  # 响应包装器
    "LongTextProcessStage",  # 长文本处理
    "SendResponseBackStage",  # 发送响应
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
