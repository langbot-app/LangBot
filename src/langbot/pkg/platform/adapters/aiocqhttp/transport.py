"""OneBot v11 duplex transport, independent of an HTTP server."""

from __future__ import annotations

import asyncio
import functools
import json
import uuid

from aiocqhttp.exceptions import ActionFailed, ApiNotAvailable


class OneBotConnection:
    def __init__(self, send, receive, close, on_event, validate, *, self_id='', timeout=30):
        self.send = send
        self.receive = receive
        self.close_socket = close
        self.on_event = on_event
        self.validate = validate
        self.self_id = self_id
        self.timeout = timeout
        self.pending = {}
        self.events = asyncio.Queue(maxsize=256)
        self.closed = False
        self.send_lock = asyncio.Lock()

    async def call_action(self, action, **params):
        await self.validate()
        if self.closed:
            raise ApiNotAvailable('OneBot connection closed')
        if len(self.pending) >= 256:
            raise ApiNotAvailable('Too many pending OneBot actions')
        echo = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[echo] = future
        try:
            async with asyncio.timeout(self.timeout):
                async with self.send_lock:
                    await self.validate()
                    await self.send(json.dumps({'action': action, 'params': params, 'echo': echo}))
                result = await future
            if (result.get('status'), result.get('retcode')) not in (('ok', 0), ('async', 1)):
                raise ActionFailed(result)
            return result.get('data')
        finally:
            self.pending.pop(echo, None)
            if not future.done():
                future.cancel()

    async def _read(self):
        while True:
            raw = await self.receive()
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('OneBot frame too large')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('OneBot frame must be an object')
            await self.validate()
            if 'post_type' in data:
                account = str(data.get('self_id', ''))
                if not account or (self.self_id and account != self.self_id):
                    raise ValueError('OneBot account mismatch')
                self.self_id = account
                # Never block responses behind an event that itself calls an API.
                self.events.put_nowait(data)
            else:
                echo = data.get('echo')
                future = self.pending.get(echo) if isinstance(echo, str) else None
                if future is not None and not future.done():
                    future.set_result(data)

    async def _consume(self):
        while True:
            data = await self.events.get()
            await self.validate()
            await self.on_event(data)

    async def _watch_placement(self):
        while True:
            await asyncio.sleep(5)
            await self.validate()

    async def run(self):
        tasks = [asyncio.create_task(coro()) for coro in (self._read, self._consume, self._watch_placement)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.close()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ApiNotAvailable('OneBot connection closed'))
        self.pending.clear()
        await self.close_socket()


class OneBotClient:
    """Keep the existing converter/API call surface without CQHttp's server."""

    def __init__(self):
        self.connection = None

    async def call_action(self, action, **params):
        connection = self.connection
        if connection is None:
            raise ApiNotAvailable('OneBot protocol endpoint is not connected')
        return await connection.call_action(action, **params)

    def __getattr__(self, action):
        if action.startswith('_'):
            raise AttributeError(action)
        return functools.partial(self.call_action, action)

    async def send(self, event, message, **kwargs):
        params = {key: event[key] for key in ('message_type', 'user_id', 'group_id', 'discuss_id') if key in event}
        return await self.call_action('send_msg', **(params | {'message': message} | kwargs))
