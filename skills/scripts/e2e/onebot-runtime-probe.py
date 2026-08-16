#!/usr/bin/env python3
"""Drive one deterministic event through an enabled OneBot reverse WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import websockets


async def run(port: int) -> None:
    uri = f'ws://127.0.0.1:{port}/ws'
    headers = {
        'X-Self-ID': '900001',
        'X-Client-Role': 'Universal',
        'User-Agent': 'LangBot-E2E-OneBot/1.0',
    }
    connect_deadline = time.monotonic() + 15
    connection = None
    while time.monotonic() < connect_deadline:
        try:
            connection = await websockets.connect(uri, additional_headers=headers)
            break
        except OSError:
            await asyncio.sleep(0.25)
    if connection is None:
        raise RuntimeError(f'OneBot reverse WebSocket did not open on port {port}')

    actions: list[str] = []
    event_deadline = time.monotonic() + 20
    async with connection as ws:
        await ws.send(
            json.dumps(
                {
                    'post_type': 'notice',
                    'notice_type': 'group_increase',
                    'sub_type': 'invite',
                    'time': int(time.time()),
                    'self_id': 900001,
                    'group_id': 20001,
                    'operator_id': 10002,
                    'user_id': 10003,
                }
            )
        )

        delivered = False
        while time.monotonic() < event_deadline and not delivered:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            request = json.loads(raw)
            action = request.get('action', '')
            actions.append(action)
            if action == 'get_group_info':
                data = {'group_id': 20001, 'group_name': 'LangBot Runtime QA'}
            elif action == 'get_group_member_info':
                data = {
                    'group_id': 20001,
                    'user_id': 10003,
                    'nickname': 'Runtime QA Member',
                    'card': 'Runtime QA Member',
                }
            elif action == 'send_group_msg':
                data = {'message_id': 70001}
                delivered = True
            else:
                data = {}
            await ws.send(
                json.dumps(
                    {
                        'status': 'ok',
                        'retcode': 0,
                        'data': data,
                        'echo': request.get('echo'),
                    }
                )
            )

        if not delivered:
            raise RuntimeError(f'Agent output was not delivered; actions={actions}')
        print(json.dumps({'connected': True, 'actions': actions, 'delivered': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.port))
