# -*- coding: utf-8 -*-
"""
test_send_streaming.py — WO-LINE-03 send_api / streaming selftest。

覆盖：RetryPolicy 退避計算／重試成功／超限失敗；
LineSendApi payload 建構（text/image/flex／无效 type／缺字段）／
reply 快速通道（缺 token+push→SendError／過期轉 Push）／push 文字；
LineStreamClient 長連骨架（start/stop/connected）／
LineStreamOutput is_stream_output_supported 保守 False／chunk 打字機推送。

self-contained（mock client，解耦 SDK）。
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from send_api import RetryPolicy, SendError, LineSendApi
from streaming import LineStreamClient, LineStreamOutput


class MockLineBotApi:
    """mock LINE SDK client（据 §2.2 push/reply 签名）。"""

    def __init__(self, reply_fail_times=0, push_fail_times=0):
        self.reply_fail_times = reply_fail_times
        self.push_fail_times = push_fail_times
        self.reply_calls = []
        self.push_calls = []
        self._reply_fail = 0
        self._push_fail = 0

    async def reply_message(self, reply_token=None, message=None):
        self.reply_calls.append({'reply_token': reply_token, 'message': message})
        if self._reply_fail < self.reply_fail_times:
            self._reply_fail += 1
            raise ConnectionError('mock reply fail')

    async def push_message(self, to_user=None, message=None):
        self.push_calls.append({'to_user': to_user, 'message': message})
        if self._push_fail < self.push_fail_times:
            self._push_fail += 1
            raise TimeoutError('mock push fail')


class TestRetryPolicy(unittest.TestCase):
    def test_backoff_monotonic(self):
        rp = RetryPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=100.0, jitter=0.0)
        # jitter=0 → 确定退避（2^attempt × base_delay，cap max_delay）
        self.assertGreaterEqual(rp.backoff(1), rp.backoff(0))
        self.assertGreaterEqual(rp.backoff(2), rp.backoff(1))
        self.assertLessEqual(rp.backoff(50), 100.0)  # 上限

    def test_retry_success_after_fails(self):
        async def go():
            client = MockLineBotApi(reply_fail_times=2)
            api = LineSendApi(client)
            result = await api.reply_message('token', {'type': 'text', 'text': 'hi'})
            self.assertEqual(result, 'replied')
            self.assertEqual(len(client.push_calls), 0)  # 非过期→未转 push
            return 'ok'

        asyncio.run(go())

    def test_retry_exhausted_raises(self):
        async def go():
            client = MockLineBotApi(push_fail_times=100)
            api = LineSendApi(client, retry=RetryPolicy(retries=2, jitter=0.0))
            with self.assertRaises(SendError):
                await api.push_message('uid', {'type': 'text', 'text': 'hi'})

        asyncio.run(go())

    def test_retry_does_not_retry_non_retryable(self):
        # 非 retryable 异常应立即抛出（不重试）
        class Boom(Exception):
            pass

        async def go():
            client = MockLineBotApi()

            async def failer():
                raise Boom('non-retryable')

            api = LineSendApi(client, retry=RetryPolicy(retries=3))
            with self.assertRaises(Boom):
                await api.retry.run(failer)

        asyncio.run(go())


class TestLineSendApi(unittest.TestCase):
    def test_build_payload_text(self):
        api = LineSendApi(MockLineBotApi())
        self.assertEqual(api._build_payload({'type': 'text', 'text': 'hi'}), {'type': 'text', 'text': 'hi'})

    def test_build_payload_image(self):
        api = LineSendApi(MockLineBotApi())
        p = api._build_payload({'type': 'image', 'original_content_url': 'u', 'preview_image_url': 'p'})
        self.assertEqual(p['type'], 'image')
        self.assertEqual(p['original_content_url'], 'u')
        self.assertEqual(p['preview_image_url'], 'p')

    def test_build_payload_flex(self):
        api = LineSendApi(MockLineBotApi())
        flex = {'type': 'bubble', 'body': {'type': 'box'}}
        p = api._build_payload({'type': 'flex', 'alternative_text': 'alt', 'flex': flex})
        self.assertEqual(p['type'], 'flex')
        self.assertEqual(p['alternative_text'], 'alt')
        self.assertEqual(p['flex'], flex)

    def test_build_payload_invalid_type(self):
        api = LineSendApi(MockLineBotApi())
        with self.assertRaises(SendError):
            api._build_payload({'type': 'audio'})

    def test_build_payload_empty_text(self):
        api = LineSendApi(MockLineBotApi())
        with self.assertRaises(SendError):
            api._build_payload({'type': 'text'})

    def test_push_message_text(self):
        async def go():
            client = MockLineBotApi()
            api = LineSendApi(client, retry=RetryPolicy(retries=1))
            await api.push_message('uid', {'type': 'text', 'text': 'hello'})
            self.assertEqual(len(client.push_calls), 1)
            self.assertEqual(client.push_calls[0]['to_user'], 'uid')
            self.assertEqual(client.push_calls[0]['message']['type'], 'text')

        asyncio.run(go())

    def test_reply_expires_to_push(self):
        async def go():
            client = MockLineBotApi(reply_fail_times=1)  # reply 失败一次
            api = LineSendApi(client, retry=RetryPolicy(retries=1, jitter=0.0))
            result = await api.reply_message(
                'token',
                {'type': 'text', 'text': 'hi'},
                push_target_id='uid',
            )
            self.assertEqual(result, 'replied')  # 平滑转 push 后返回
            # 第一次 reply 失败（ConnectionError），重试后仍失败 → 转 push
            # 至少一次 push 成功补完
            self.assertTrue(any(c['message']['type'] == 'text' for c in client.push_calls))

        asyncio.run(go())

    def test_reply_without_token_or_push_raises(self):
        api = LineSendApi(MockLineBotApi())
        with self.assertRaises(SendError):
            # target_id 空 + 无 push_target_id
            asyncio.run(api.reply_message(None, {'type': 'text', 'text': 'hi'}))


class TestLineStreamClient(unittest.TestCase):
    def test_stream_lifecycle(self):
        async def go():
            c = LineStreamClient()
            self.assertFalse(c.connected)
            status = await c.start_stream()
            self.assertTrue(c.connected)
            self.assertIn('skeleton', status)
            self.assertTrue(await c.stop_stream())
            self.assertFalse(c.connected)

        asyncio.run(go())

    def test_connect_with_retry_success(self):
        async def go():
            c = LineStreamClient(retry=RetryPolicy(retries=1, base_delay=0.0))
            self.assertTrue(await c.connect_with_retry())

        asyncio.run(go())


class TestLineStreamOutput(unittest.TestCase):
    def test_stream_output_default_unsupported(self):
        out = LineStreamOutput(MockLineBotApi())
        self.assertFalse(out.is_stream_output_supported())

    def test_reply_message_chunk_pushes_all(self):
        async def go():
            client = MockLineBotApi()
            api = LineSendApi(client, retry=RetryPolicy(retries=1, jitter=0.0))
            out = LineStreamOutput(api, chunk_delay=0.0)
            result = await out.reply_message_chunk('uid', ['h', 'he', 'hel', 'hell'])
            self.assertEqual(result, 'streaming_done')
            # 4 个 chunk → 4 次 push
            self.assertEqual(len(client.push_calls), 4)

        asyncio.run(go())

    def test_reply_message_chunk_empty_raises(self):
        async def go():
            api = LineSendApi(MockLineBotApi(), retry=RetryPolicy(retries=1))
            out = LineStreamOutput(api)
            with self.assertRaises(SendError):
                await out.reply_message_chunk('uid', [])

        asyncio.run(go())


if __name__ == '__main__':
    unittest.main()
