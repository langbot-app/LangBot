from . import client

import asyncio

import os


class TestDifyClient:
    async def test_chat_messages(self):
        cln = client.DifyClient(api_key=os.getenv('DIFY_API_KEY'))

        resp = await cln.chat_messages(inputs={}, query='Who are you?', user_id='test')
        print(resp)


if __name__ == '__main__':
    asyncio.run(TestDifyClient().test_chat_messages())
