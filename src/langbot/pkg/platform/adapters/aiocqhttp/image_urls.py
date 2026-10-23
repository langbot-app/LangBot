"""Connection-local OneBot image references and expiring download credentials."""

import asyncio
import math
import time
from collections import OrderedDict
from urllib.parse import parse_qsl, quote, unquote_plus, urlsplit, urlunsplit

from aiocqhttp import Message


def image_nodes(value, message_id=None):
    """Yield structured image nodes with the nearest original message identity."""
    if isinstance(value, list):
        source = next((v.get('id') for v in value if isinstance(v, dict) and v.get('type') == 'Source'), None)
        current_id = source if source is not None else message_id
        for child in value:
            if isinstance(child, dict) and child.get('type') == 'Source':
                current_id = child.get('id')
            yield from image_nodes(child, current_id)
    elif isinstance(value, dict):
        message_id = value.get('message_id', message_id)
        if value.get('type') in ('Image', 'image', 'image_url'):
            target = value.get('image_url') if value.get('type') == 'image_url' else value
            if isinstance(target, dict) and remote_image_url(target.get('url')):
                yield target, message_id, value.get('image_id') or value.get('id')
        for key, child in value.items():
            if key == 'origin' and value.get('type') == 'Quote':
                yield from image_nodes(child, value.get('id'))
            elif key not in ('image_url',):
                yield from image_nodes(child, message_id)


def remote_image_url(url):
    """Exclude inline data, local media paths and malformed URLs from peer refresh."""
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username and not parsed.password
        )
    except ValueError:
        return False


def nt_image_type(url):
    """Recognize only QQ NT download URLs with unambiguous resource parameters."""
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        params = dict(pairs)
        if (
            parsed.scheme not in ('http', 'https')
            or parsed.hostname != 'multimedia.nt.qq.com.cn'
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
            or parsed.path != '/download'
            or any(sum(key == name for key, _ in pairs) != 1 for name in ('appid', 'fileid', 'rkey'))
            or not params.get('fileid')
            or not params.get('rkey')
        ):
            return None
        return {'1406': 10, '1407': 20}.get(params['appid'])
    except ValueError:
        return None


class OneBotImageURLs:
    """Keep credentials and bounded source mappings within a single connection."""

    def __init__(self, connection):
        self.connection = connection
        self.lock = asyncio.Lock()
        self.app_name = None
        self.keys = {}
        self.references = OrderedDict()
        self.messages = OrderedDict()
        self.urls = OrderedDict()
        self.retry_after = 0

    def remember(self, url, message_id, image_id):
        if message_id in (None, '', -1, '-1') or not image_id:
            return
        self.references[url] = (message_id, str(image_id))
        self.references.move_to_end(url)
        while len(self.references) > 2048:
            self.references.popitem(last=False)

    async def identify(self):
        """Identify lazily with the same backoff as resource renewal."""
        async with self.lock:
            if self.connection.closed or time.monotonic() < self.retry_after:
                return False
            try:
                await self._identify()
                return True
            except Exception:
                self.retry_after = time.monotonic() + 30
                raise

    async def _identify(self):
        if self.app_name is None:
            info = await self.connection.call_action('get_version_info')
            self.app_name = info.get('app_name', '')

    async def refresh(self, payload):
        nodes = list(image_nodes(payload))
        if not nodes or self.connection.closed:
            return False
        for node, message_id, image_id in nodes:
            self.remember(node['url'], message_id, image_id)
        async with self.lock:
            if self.connection.closed or time.monotonic() < self.retry_after:
                return False
            try:
                await self._identify()
                if self.app_name == 'NapCat.Onebot':
                    return await self._napcat(nodes)
                return await self._standard(nodes)
            except Exception:
                # Failed/unsupported APIs must not break history reads or hammer the peer.
                self.retry_after = time.monotonic() + 30
                raise

    async def _napcat(self, nodes):
        wanted = {kind for node, _, _ in nodes if (kind := nt_image_type(node['url'])) is not None}
        if not wanted:
            return set()
        if any(self.keys.get(kind, ('', 0))[1] <= time.time() for kind in wanted):
            result = await self.connection.call_action('nc_get_rkey')
            keys = {}
            for item in result:
                kind = int(item['type'])
                if kind not in (10, 20):
                    continue
                expires = float(item['time']) + float(item['ttl'])
                key = item['rkey']
                if isinstance(key, str) and key.startswith('&rkey='):
                    key = key[len('&rkey=') :]
                if isinstance(key, str) and key and math.isfinite(expires) and expires > time.time():
                    keys[kind] = (key, expires)
            if not wanted.issubset(keys):
                raise ValueError('NapCat returned no valid image credentials')
            self.keys.update(keys)
        completed = set()
        for node, _, _ in nodes:
            kind = nt_image_type(node['url'])
            if kind not in wanted:
                continue
            completed.add(node['url'])
            parsed = urlsplit(node['url'])
            parts = parsed.query.split('&')
            # Preserve every other parameter byte-for-byte, including signed resource IDs.
            parts = [
                part.split('=', 1)[0] + '=' + quote(self.keys[kind][0], safe='')
                if unquote_plus(part.split('=', 1)[0]) == 'rkey'
                else part
                for part in parts
            ]
            node['url'] = urlunsplit(parsed._replace(query='&'.join(parts)))
        return completed

    async def _standard(self, nodes):
        completed = set()
        for node, _, _ in nodes:
            old_url = node['url']
            refreshed = self.urls.get(old_url)
            if refreshed is not None and refreshed[1] > time.monotonic():
                node['url'] = refreshed[0]
                completed.add(old_url)
                continue
            ref = self.references.get(old_url)
            if ref is None:
                continue
            message_id, image_id = ref
            cached = self.messages.get(str(message_id))
            if cached is None or cached[1] <= time.monotonic():
                raw = await self.connection.call_action('get_msg', message_id=int(message_id))
                images = {}
                for segment in Message(raw.get('message', [])):
                    if segment.type == 'image':
                        data = segment.data
                        if data.get('file') and remote_image_url(data.get('url')):
                            images[str(data['file'])] = data['url']
                cached = (images, time.monotonic() + 1800)
                self.messages[str(message_id)] = cached
                self.messages.move_to_end(str(message_id))
                while len(self.messages) > 256:
                    self.messages.popitem(last=False)
            new_url = cached[0].get(image_id)
            if new_url:
                completed.add(old_url)
                self.remember(new_url, message_id, image_id)
                deadline = cached[1]
                self.urls[old_url] = (new_url, deadline)
                self.urls[new_url] = (new_url, deadline)
                while len(self.urls) > 2048:
                    self.urls.popitem(last=False)
                node['url'] = new_url
        return completed
