"""Bounded, process-local fan-out. One snapshot producer per watched Workspace.

Writes wake the producer; quiet workspaces reconcile every 15 seconds to cover
external workers. A shared broker can replace notify without changing clients.
No payloads or subscriptions survive the final viewer disconnecting.
"""

import asyncio
import contextlib
import time


class InflightHub:
    def __init__(self):
        self.channels = {}
        self.run_workspaces = {}

    def notify(self, workspace):
        channel = self.channels.get(workspace)
        if channel:
            channel['dirty'].set()

    def notify_run(self, run_id, event_type):
        workspace = self.run_workspaces.get(run_id)
        channel = self.channels.get(workspace)
        if channel and channel['phases'].get(run_id) != event_type:
            channel['phases'][run_id] = event_type
            channel['dirty'].set()

    def track(self, workspace, run_ids):
        self.run_workspaces = {key: value for key, value in self.run_workspaces.items() if value != workspace}
        if workspace not in self.channels:
            return
        self.run_workspaces.update({run_id: workspace for run_id in run_ids})
        if workspace in self.channels:
            phases = self.channels[workspace]['phases']
            self.channels[workspace]['phases'] = {key: value for key, value in phases.items() if key in run_ids}

    async def watch(self, workspace, loader):
        if sum(len(c['queues']) for c in self.channels.values()) >= 1024:
            raise RuntimeError('Too many monitoring connections')
        channel = self.channels.get(workspace)
        if channel is None:
            channel = dict(queues=set(), dirty=asyncio.Event(), phases={}, snapshot=None)
            self.channels[workspace] = channel
            channel['task'] = asyncio.create_task(self._produce(channel, loader))
        if len(channel['queues']) >= 64:
            raise RuntimeError('Too many Workspace monitoring connections')
        queue = asyncio.Queue(maxsize=1)
        channel['queues'].add(queue)
        if channel['snapshot'] is not None:
            queue.put_nowait(channel['snapshot'])
        try:
            # Reconnect periodically so HTTP authentication/authorization is renewed.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=min(10, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    yield {'kind': 'heartbeat'}
        finally:
            channel['queues'].discard(queue)
            if not channel['queues']:
                self.channels.pop(workspace, None)
                self.track(workspace, [])
                channel['task'].cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await channel['task']

    async def _produce(self, channel, loader):
        previous = None
        while True:
            channel['dirty'].clear()
            try:
                snapshot = await loader()
                frame = {'kind': 'snapshot', 'data': snapshot}
            except Exception:
                frame = {'kind': 'unavailable'}
            # Heartbeats are sent separately; unchanged snapshots generate no traffic.
            if frame != previous:
                channel['snapshot'] = frame
                for queue in tuple(channel['queues']):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(frame)
                previous = frame
            await asyncio.sleep(0.75)
            try:
                await asyncio.wait_for(channel['dirty'].wait(), timeout=15)
            except asyncio.TimeoutError:
                pass


inflight_hub = InflightHub()
