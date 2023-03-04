# 长消息处理相关
import config
from mirai.models.message import MessageComponent, MessageChain
from mirai.models.message import ForwardMessageNode
from mirai.models.base import MiraiBaseModel
from typing import List, Optional
import pkg.utils.context as context


class ForwardMessageDiaplay(MiraiBaseModel):
    title: str = "群聊的聊天记录"
    brief: str = "[聊天记录]"
    source: str = "聊天记录"
    preview: List[str] = []
    summary: str = "查看x条转发消息"


class Forward(MessageComponent):
    """合并转发。"""
    type: str = "Forward"
    """消息组件类型。"""
    display: ForwardMessageDiaplay
    """显示信息"""
    node_list: List[ForwardMessageNode]
    """转发消息节点列表。"""
    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            self.node_list = args[0]
            super().__init__(**kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return '[聊天记录]'



def check_text(text: str) -> list:
    """检查文本是否为长消息，并转换成该使用的消息链组件"""
    if not hasattr(config, 'blob_message_threshold'):
        return [text]
    
    if len(text) > config.blob_message_threshold:
        if not hasattr(config, 'blob_message_strategy'):
            raise AttributeError('未定义长消息处理策略')
        
        if config.blob_message_strategy == 'image':
            # 转换成图片
            pass
        elif config.blob_message_strategy == 'forward':
            # 敏感词屏蔽
            text = context.get_qqbot_manager().reply_filter.process(text)

            # 包装转发消息
            display = ForwardMessageDiaplay(
                title='群聊的聊天记录',
                brief='[聊天记录]',
                source='聊天记录',
                preview=["bot: "+text],
                summary="查看1条转发消息"
            )

            node = ForwardMessageNode(
                sender_id=config.mirai_http_api_config['qq'],
                sender_name='bot',
                message_chain=MessageChain([text])
            )

            forward = Forward(
                display=display,
                node_list=[node]
            )

            return [forward]