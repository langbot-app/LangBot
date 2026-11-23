"""Best-effort, per-peer typing leases for the iLink transport."""

import asyncio
import contextlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Lease:
    users: int = 0
    task: asyncio.Task | None = None
    ticket: str = ''


class TypingIndicator:
    INTERVAL = 5.0
    TIMEOUT = 3.0
    TICKET_TTL = 600.0
    MAX_PEERS = 4096

    def __init__(self, client, context_token):
        self.client = client
        self.context_token = context_token
        self.leases: dict[str, Lease] = {}
        self.cache = OrderedDict()
        self.closed = False

    async def _ticket(self, peer):
        now = time.monotonic()
        cached = self.cache.get(peer)
        if cached and cached[1] > now:
            return cached[0]
        try:
            response = await asyncio.wait_for(
                self.client.get_config(peer, self.context_token(peer)),
                self.TIMEOUT,
            )
            if response.ret not in (None, 0):
                raise ValueError('getconfig failed')
            ticket = response.typing_ticket or ''
            delay = self.TICKET_TTL if ticket else 30.0
        except Exception:
            ticket = ''
            delay = min((cached[2] * 2 if cached else 5.0), 300.0)
            logger.debug('Weixin typing ticket unavailable; retry deferred')
        self.cache[peer] = (ticket, now + delay, delay)
        self.cache.move_to_end(peer)
        while len(self.cache) > self.MAX_PEERS:
            self.cache.popitem(last=False)
        return ticket

    async def _run(self, peer, lease):
        try:
            while not self.closed and lease.users:
                ticket = await self._ticket(peer)
                if ticket:
                    # Keep the last ticket so cancellation can stop an in-flight start.
                    lease.ticket = ticket
                    try:
                        await asyncio.wait_for(self.client.send_typing(peer, ticket), self.TIMEOUT)
                    except Exception:
                        self.cache[peer] = ('', time.monotonic() + 30, 30)
                        logger.debug('Weixin typing start failed; retry deferred')
                await asyncio.sleep(self.INTERVAL)
        finally:
            if lease.ticket:
                try:
                    # Refresh expired tickets before cancelling a long-running turn.
                    ticket = await self._ticket(peer) or lease.ticket
                    await asyncio.wait_for(self.client.stop_typing(peer, ticket), self.TIMEOUT)
                except Exception:
                    logger.debug('Weixin typing stop failed')

    @contextlib.asynccontextmanager
    async def processing(self, peer):
        lease = None
        while not self.closed:
            lease = self.leases.get(peer)
            if lease is None:
                if len(self.leases) >= self.MAX_PEERS:
                    lease = None
                    break
                lease = Lease(users=1)
                self.leases[peer] = lease
                lease.task = asyncio.create_task(self._run(peer, lease))
                break
            if lease.users:
                lease.users += 1
                break
            # Serialize stop/start for the same peer: an old stop must not cancel a new start.
            await asyncio.gather(asyncio.shield(lease.task), return_exceptions=True)
            if self.leases.get(peer) is lease:
                self.leases.pop(peer, None)
            lease = None
        try:
            yield
        finally:
            if lease is not None and lease.users:
                lease.users -= 1
                if not lease.users:
                    if not lease.task.cancelling():
                        lease.task.cancel()
                    await asyncio.gather(asyncio.shield(lease.task), return_exceptions=True)
                    if self.leases.get(peer) is lease:
                        self.leases.pop(peer, None)

    async def close(self):
        self.closed = True
        tasks = [lease.task for lease in self.leases.values()]
        for task in tasks:
            if not task.done() and not task.cancelling():
                task.cancel()
        await asyncio.gather(*(asyncio.shield(task) for task in tasks), return_exceptions=True)
        self.leases.clear()
        self.cache.clear()
