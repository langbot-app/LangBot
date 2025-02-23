from __future__ import annotations

import discord

import typing
import asyncio
import traceback
import time
import re
import base64
import uuid
import json
import os
import datetime

import aiohttp

from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ...utils import image


class DiscordMessageConverter(adapter.MessageConverter):

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain
    ) -> typing.Tuple[str, typing.List[discord.File]]:
        for ele in message_chain:
            if isinstance(ele, platform_message.At):
                message_chain.remove(ele)
                break

        text_string = ""
        image_files = []

        for ele in message_chain:
            if isinstance(ele, platform_message.Image):
                image_bytes = None

                if ele.base64:
                    image_bytes = base64.b64decode(ele.base64)
                elif ele.url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(ele.url) as response:
                            image_bytes = await response.read()
                elif ele.path:
                    with open(ele.path, "rb") as f:
                        image_bytes = f.read()

                image_files.append(discord.File(fp=image_bytes, filename=f"{uuid.uuid4()}.png"))
            elif isinstance(ele, platform_message.Plain):
                text_string += ele.text
            elif isinstance(ele, platform_message.Forward):
                for node in ele.node_list:
                    text_string, image_files = await DiscordMessageConverter.yiri2target(node.message_chain)
                    text_string += text_string
                    image_files.extend(image_files)

        return text_string, image_files

    @staticmethod
    async def target2yiri(
        message: discord.Message
    ) -> platform_message.MessageChain:
        lb_msg_list = []

        msg_create_time = datetime.datetime.fromtimestamp(
            int(message.created_at.timestamp())
        )

        lb_msg_list.append(
            platform_message.Source(id=message.id, time=msg_create_time)
        )

        element_list = []

        def text_element_recur(text_ele: str) -> list[platform_message.MessageComponent]:
            if text_ele == "":
                return []

            # <@1234567890>
            # @everyone
            # @here
            at_pattern = re.compile(r"(@everyone|@here|<@[\d]+>)")
            at_matches = at_pattern.findall(text_ele)
            
            if len(at_matches) > 0:
                mid_at = at_matches[0]

                text_split = text_ele.split(mid_at)

                mid_at_component = []

                if mid_at == "@everyone" or mid_at == "@here":
                    mid_at_component.append(platform_message.AtAll())
                else:
                    mid_at_component.append(platform_message.At(target=mid_at[2:-1]))

                return text_element_recur(text_split[0]) + \
                    mid_at_component + \
                    text_element_recur(text_split[1])
            else:
                return [platform_message.Plain(text=text_ele)]

        
        element_list.extend(text_element_recur(message.content))

        # attachments
        for attachment in message.attachments:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(attachment.url) as response:
                    image_data = await response.read()
                    image_base64 = base64.b64encode(image_data).decode("utf-8")
                    image_format = response.headers["Content-Type"]
                    element_list.append(platform_message.Image(base64=f"data:{image_format};base64,{image_base64}"))

        return platform_message.MessageChain(element_list)


class DiscordEventConverter(adapter.EventConverter):

    @staticmethod
    async def yiri2target(
        event: platform_events.Event
    ) -> discord.Message:
        pass

    @staticmethod
    async def target2yiri(
        event: discord.Message
    ) -> platform_events.Event:
        message_chain = await DiscordMessageConverter.target2yiri(event)

        if type(event.channel) == discord.DMChannel:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.author.id,
                    nickname=event.author.name,
                    remark=event.channel.id,
                ),
                message_chain=message_chain,
                time=event.created_at.timestamp(),
                source_platform_object=event,
            )
        elif type(event.channel) == discord.TextChannel:
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.author.id,
                    member_name=event.author.name,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.channel.id,
                        name=event.channel.name,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title="",
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event.created_at.timestamp(),
                source_platform_object=event,
            )


class DiscordAdapter(adapter.MessagePlatformAdapter):

    bot: discord.Client

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识

    config: dict

    ap: app.Application

    message_converter: DiscordMessageConverter = DiscordMessageConverter()
    event_converter: DiscordEventConverter = DiscordEventConverter()

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap

        self.bot_account_id = self.config["client_id"]

        adapter_self = self

        class MyClient(discord.Client):

            async def on_message(self: discord.Client, message: discord.Message):
                if message.author.id == self.user.id or message.author.bot:
                    return

                lb_event = await adapter_self.event_converter.target2yiri(message)
                await adapter_self.listeners[type(lb_event)](lb_event, adapter_self)

        intents = discord.Intents.default()
        intents.message_content = True

        args = {}

        if os.getenv("http_proxy"):
            args["proxy"] = os.getenv("http_proxy")

        self.bot = MyClient(intents=intents, **args)
        
    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
        pass

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        msg_to_send, image_files = await self.message_converter.yiri2target(message)
        assert isinstance(message_source.source_platform_object, discord.Message)

        args = {
            "content": msg_to_send,
        }

        if len(image_files) > 0:
            args["files"] = image_files

        if quote_origin:
            args["reference"] = message_source.source_platform_object

        if message.has(platform_message.At):
            args["mention_author"] = True

        await message_source.source_platform_object.channel.send(**args)

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners.pop(event_type)

    async def run_async(self):
        async with self.bot:
            await self.bot.start(self.config["token"], reconnect=True)

    async def kill(self) -> bool:
        await self.bot.close()
        return True
