"""Independent OneBot v11 wire peer; no LangBot transport/converter imports.

Contract: https://github.com/botuniverse/onebot-11 (api/public.md,
communication/{ws,ws-reverse,http}.md and event/*.md).
Only test data is served; no real QQ account or vendor service is contacted.
"""

import asyncio
import json


class OneBotMock:
    def __init__(self):
        self.ready = asyncio.Event()
        self.requests = []
        self.send = None
        self.response = None
        self.user = {'user_id': 10001, 'nickname': 'Alice', 'sex': 'unknown', 'age': 20}
        self.group = {'group_id': 20001, 'group_name': 'Mock group', 'member_count': 2, 'max_member_count': 200}
        self.member = self.user | {'group_id': 20001, 'card': 'Card', 'role': 'admin', 'title': 'Title', 'join_time': 1}

    async def run(self, send, receive):
        self.send = send
        self.ready.set()
        while True:
            request = json.loads(await receive())
            self.requests.append(request)
            if self.response is not None:
                response = dict(self.response)
            else:
                response = self.handle(request)
            await send(json.dumps(response | {'echo': request.get('echo')}))

    def handle(self, request):
        action, params = request['action'], request.get('params', {})
        for key in ('user_id', 'group_id', 'message_id', 'duration'):
            if key in params:
                assert type(params[key]) is int, (action, key, params[key])
        data = None
        if action in ('send_msg', 'send_private_msg', 'send_group_msg'):
            assert isinstance(params['message'], (list, str))
            data = {'message_id': 123}
        elif action == 'get_msg':
            data = self.message('private', 'friend')
        elif action == 'get_login_info':
            data = {'user_id': 42, 'nickname': 'Mock bot'}
        elif action == 'get_stranger_info':
            data = self.user
        elif action == 'get_friend_list':
            data = [self.user | {'remark': 'Friend'}]
        elif action == 'get_group_info':
            data = self.group
        elif action == 'get_group_list':
            data = [self.group]
        elif action == 'get_group_member_info':
            data = self.member
        elif action == 'get_group_member_list':
            data = [self.member]
        elif action == 'get_status':
            data = {'online': True, 'good': True}
        elif action == 'get_version_info':
            data = {'app_name': 'onebot-test-peer', 'app_version': '1', 'protocol_version': 'v11'}
        elif action in ('can_send_image', 'can_send_record'):
            data = {'yes': True}
        elif action in ('get_image', 'get_record'):
            data = {'file': '/mock/media'}
        elif action == 'get_forward_msg':
            data = {'message': []}
        elif action == 'get_group_honor_info':
            data = {'group_id': 20001}
        elif action not in {
            'delete_msg',
            'set_group_name',
            'set_group_ban',
            'set_group_kick',
            'set_group_leave',
            'set_friend_add_request',
            'set_group_add_request',
            'set_group_card',
            'set_group_special_title',
            'set_group_admin',
            'set_group_whole_ban',
        }:
            return {'status': 'failed', 'retcode': 1404, 'data': None}
        return {'status': 'ok', 'retcode': 0, 'data': data}

    async def emit(self, payload):
        await self.ready.wait()
        await self.send(json.dumps({'time': 1700000000, 'self_id': 42} | payload))

    def message(self, kind, subtype, message=None):
        result = {
            'post_type': 'message',
            'message_type': kind,
            'sub_type': subtype,
            'time': 1700000000,
            'self_id': 42,
            'message_id': 9,
            'user_id': 10001,
            'message': message if message is not None else [{'type': 'text', 'data': {'text': 'hello'}}],
            'raw_message': 'hello',
            'font': 0,
            'sender': self.user,
        }
        if kind == 'group':
            result.update(group_id=20001, anonymous=None, sender=self.member)
        return result
