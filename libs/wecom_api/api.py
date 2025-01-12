from quart import request
from .WXBizMsgCrypt3 import WXBizMsgCrypt

import httpx
from quart import Quart
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Any
from .wecomevent import WecomEvent


class WecomClient():
    def __init__(self,corpid:str,secret:str,token:str,EncodingAESKey:str,contacts_secret:str):
        self.corpid = corpid
        self.secret = secret
        self.access_token_for_contacts =''
        self.token = token
        self.aes = EncodingAESKey
        self.base_url = 'https://qyapi.weixin.qq.com/cgi-bin'
        self.access_token = ''
        self.secret_for_contacts = contacts_secret
        self.app = Quart(__name__)
        self.wxcpt = WXBizMsgCrypt(self.token, self.aes, self.corpid)
        self.app.add_url_rule('/callback/command', 'handle_callback', self.handle_callback_request, methods=['GET', 'POST'])
        self._message_handlers = {
            "example":[],
        }

    #access——token操作
    async def check_access_token(self):
        return bool(self.access_token and self.access_token.strip())

    async def check_access_token_for_contacts(self):
        return bool(self.access_token_for_contacts and self.access_token_for_contacts.strip())

    async def get_access_token(self,secret):
        url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corpid}&corpsecret={secret}'
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            if 'access_token' in data:
                return data['access_token']
            else:
                raise Exception(f"未获取access token: {data}")


    async def get_users(self):
        if not self.check_access_token_for_contacts():
            self.access_token_for_contacts = await self.get_access_token(self.secret_for_contacts)

        url = self.base_url+'/user/list_id?access_token='+self.access_token_for_contacts
        async with httpx.AsyncClient() as client:
            params = {
                "cursor":"",
                "limit":10000,
            }
            response = await client.post(url,json=params)
            data = response.json()
            if data['errcode'] == 0:
                dept_users = data['dept_user']
                userid = []
                for user in dept_users:
                    userid.append(user["userid"])
                return userid
            else:
                raise Exception("未获取用户")
            
    async def send_to_all(self,content:str):
        if not self.check_access_token_for_contacts():
            self.access_token_for_contacts = await self.get_access_token(self.secret_for_contacts)

            url = self.base_url+'/message/send?access_token='+self.access_token_for_contacts
            user_ids = await self.get_users()
            user_ids_string = "|".join(user_ids)
            async with httpx.AsyncClient() as client:
                params = {
                "touser" : user_ids_string,
                "msgtype" : "text",
                "agentid" : 1000002,
                "text" : {
                    "content" : content,
                },
                "safe":0,
                "enable_id_trans": 0,
                "enable_duplicate_check": 0,
                "duplicate_check_interval": 1800
                }
                response = await client.post(url,json=params)
                data = response.json()
                if data['errcode'] != 0:
                    raise Exception("Failed to send message: "+str(data))
            
    async def send_private_msg(self,user_id:str, agent_id:int,content:str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url+'/message/send?access_token='+self.access_token

        async with httpx.AsyncClient() as client:
            params={
                "touser" : user_id,
                "msgtype" : "text",
                "agentid" : agent_id,
                "text" : {
                    "content" : content,
                },
                "safe":0,
                "enable_id_trans": 0,
                "enable_duplicate_check": 0,
                "duplicate_check_interval": 1800
            }
            response = await client.post(url,json=params)
            data = response.json()
            
            if data['errcode'] != 0:
                raise Exception("Failed to send message: "+str(data))

    async def handle_callback_request(self):
        """
        处理回调请求，包括 GET 验证和 POST 消息接收。
        """
        try:

            msg_signature = request.args.get("msg_signature")
            timestamp = request.args.get("timestamp")
            nonce = request.args.get("nonce")

            if request.method == "GET":
                echostr = request.args.get("echostr")
                ret, reply_echo_str = self.wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                if ret != 0:
                    raise Exception(f"验证失败，错误码: {ret}")
                return reply_echo_str

            elif request.method == "POST":
                encrypt_msg = await request.data
                ret, xml_msg = self.wxcpt.DecryptMsg(encrypt_msg, msg_signature, timestamp, nonce)
                if ret != 0:
                    raise Exception(f"消息解密失败，错误码: {ret}")

                # 解析消息并处理
                message_data = await self.get_message(xml_msg)
                if message_data:
                    event = WecomEvent.from_payload(message_data)  # 转换为 WecomEvent 对象
                    if event:
                        await self._handle_message(event)

                return "success"
        except Exception as e:
            return f"Error processing request: {str(e)}", 400

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)

    def on_message(self, msg_type: str):
        """
        注册消息类型处理器。
        """
        def decorator(func: Callable[[WecomEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func
        return decorator

    async def _handle_message(self, event: WecomEvent):
        """
        处理消息事件。
        """
        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def get_message(self, xml_msg: str) -> Dict[str, Any]:
        """
        解析微信返回的 XML 消息并转换为字典。
        """
        root = ET.fromstring(xml_msg)
        message_data = {
            "ToUserName": root.find("ToUserName").text,
            "FromUserName": root.find("FromUserName").text,
            "CreateTime": int(root.find("CreateTime").text),
            "MsgType": root.find("MsgType").text,
            "Content": root.find("Content").text if root.find("Content") is not None else None,
            "MsgId": int(root.find("MsgId").text) if root.find("MsgId") is not None else None,
            "AgentID": int(root.find("AgentID").text) if root.find("AgentID") is not None else None,
        }
        return message_data




            


    
    