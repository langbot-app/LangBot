# 长消息处理相关
import os
import time
import base64

import config
from mirai.models.message import MessageComponent, MessageChain, Image
from mirai.models.message import ForwardMessageNode
from mirai.models.base import MiraiBaseModel
from typing import List
import pkg.utils.context as context
import pkg.utils.text2img as text2img


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


def text_to_image(text: str) -> MessageComponent:
    """将文本转换成图片"""
    # 检查temp文件夹是否存在
    if not os.path.exists('temp'):
        os.mkdir('temp')
    img_path = text2img.text_to_image(text_str=text, save_as='temp/{}.png'.format(int(time.time())))
    
    compressed_path, size = text2img.compress_image(img_path, outfile="temp/{}_compressed.png".format(int(time.time())))
    # 读取图片，转换成base64
    with open(compressed_path, 'rb') as f:
        img = f.read()

    b64 = base64.b64encode(img)

    # 删除图片
    os.remove(img_path)

    # 判断compressed_path是否存在
    if os.path.exists(compressed_path):
        os.remove(compressed_path)
    # 返回图片
    return Image(base64=b64.decode('utf-8'))


def check_text(text: str) -> list:
    """检查文本是否为长消息，并转换成该使用的消息链组件"""
    if len(text) > config.blob_message_threshold:

        # logging.info("长消息: {}".format(text))
        if config.blob_message_strategy == 'image':
            # 转换成图片
            return [text_to_image(text)]
        elif config.blob_message_strategy == 'forward':

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
    else:
        return [text]