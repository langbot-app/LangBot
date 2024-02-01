import re

import botpy
from botpy.message import Message, DirectMessage

import openai
import datetime

openai_client = openai.Client()


intents = botpy.Intents(
    public_guild_messages=True,
    direct_message=True,
)
client = botpy.Client(intents=intents)

def wrapper(func):
    async def fn(*args, **kwargs):
        return await func(client, *args, **kwargs)
    
    return fn

print(int('11374654729765438030'))

@wrapper
async def on_at_message_create(self, message: Message):
    # await self.api.post_message(channel_id=message.channel_id, content=openai_client.chat.completions.create(
    #     model="gpt-3.5-turbo",
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": message.content
    #         }
    #     ]
    # ).choices[0].message.content)
    print(self)

    print(message.content)

    # 删除消息中：<@!12345678> 这样的内容
    message.content = re.sub(r"<@!\d+>", "", message.content)

    print(message.content)
    # image_url = openai_client.images.generate(
    #     model="dall-e-3",
    #     prompt=message.content,
    #     size="1024x1024",
    #     quality="standard",
    #     n=1,
    # ).data[0].url
    # print(image_url)
    print(message.member.roles)
    # 2022-06-04T22:56:51+08:00
    time_str = message.member.joined_at
    date_obj = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")
    print(date_obj.timestamp())

    print(f"message.channel_id: {message.channel_id}, message.id: {message.id}, message.content: {message.content}, message.author: {message.author}, message.attachments: {message.attachments}")
    print(message.mentions)

    await self.api.post_message(
        channel_id=message.channel_id,
        msg_id=message.id,
        image="https://gchat.qpic.cn/download?appid=1407&fileid=CgoxMDEwNTUzODkyEhS7rtLyruPu6lyTBvTjQwZul5vuERjx-wEg_woo6oKkscHDggNQgL2jAQ&rkey=CAMSMEpZEUuWzKJ8k5PQaayVPrGr_qQ1zF89b65iW_h_w-HlQvPmNfEeCLBaR3Mhtt1FTA&spec=0",
        # content=message.content
    )

    print(message.channel_id, message.id)
    print(type(message.channel_id), type(message.id))

    await self.api.post_message(
        channel_id=message.channel_id,
        msg_id=message.id,
        image="https://gchat.qpic.cn/download?appid=1407&fileid=CgoxMDEwNTUzODkyEhS7rtLyruPu6lyTBvTjQwZul5vuERjx-wEg_woo6oKkscHDggNQgL2jAQ&rkey=CAMSMEpZEUuWzKJ8k5PQaayVPrGr_qQ1zF89b65iW_h_w-HlQvPmNfEeCLBaR3Mhtt1FTA&spec=0",
        # content=message.content
    )

@wrapper
async def on_direct_message_create(self, message: DirectMessage):
    print(f"message.channel_id: {message.channel_id}, message.id: {message.id}, message.content: {message.content}, message.author: {message.author}, message.attachments: {message.attachments}")
    await self.api.post_dms(guild_id=message.guild_id, content="hi")


setattr(client, "on_at_message_create", on_at_message_create)
setattr(client, "on_direct_message_create", on_direct_message_create)
client.run(appid="102076866", token="jwn1C2V1S9q3PBHoSLKfA7pKzKVyWzkm")
