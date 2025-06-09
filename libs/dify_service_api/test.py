from v1 import client  # type: ignore

import asyncio

import os
import json


class TestDifyClient:
    async def test_chat_messages(self):
        cln = client.AsyncDifyServiceClient(api_key=os.getenv('DIFY_API_KEY'), base_url=os.getenv('DIFY_BASE_URL'))

        async for chunk in cln.chat_messages(inputs={}, query='调用工具查看现在几点？', user='test'):
            print(json.dumps(chunk, ensure_ascii=False, indent=4))

    async def test_upload_file(self):
        cln = client.AsyncDifyServiceClient(api_key=os.getenv('DIFY_API_KEY'), base_url=os.getenv('DIFY_BASE_URL'))

        file_bytes = open('img.png', 'rb').read()

        print(type(file_bytes))

        file = ('img2.png', file_bytes, 'image/png')

        resp = await cln.upload_file(file=file, user='test')
        print(json.dumps(resp, ensure_ascii=False, indent=4))

    async def test_workflow_run(self):
        cln = client.AsyncDifyServiceClient(api_key=os.getenv('DIFY_API_KEY'), base_url=os.getenv('DIFY_BASE_URL'))

        # resp = await cln.workflow_run(inputs={}, user="test")
        # # print(json.dumps(resp, ensure_ascii=False, indent=4))
        # print(resp)
        chunks = []

        ignored_events = ['text_chunk']
        async for chunk in cln.workflow_run(inputs={}, user='test'):
            if chunk['event'] in ignored_events:
                continue
            chunks.append(chunk)
        print(json.dumps(chunks, ensure_ascii=False, indent=4))


if __name__ == '__main__':
    asyncio.run(TestDifyClient().test_chat_messages())
