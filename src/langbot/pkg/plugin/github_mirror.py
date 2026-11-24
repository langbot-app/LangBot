import asyncio
import re
from time import monotonic
from urllib.parse import urlsplit

import httpx

from .management import parse_github_repo_url


def parse_refs(body: bytes):
    branches, tags = {}, {}
    default = ''
    header = b'001e# service=git-upload-pack\n0000'
    if not body.startswith(header) or not body.endswith(b'0000'):
        raise ValueError('Invalid Git ref advertisement')
    offset = len(header)
    while offset < len(body) - 4:
        size = int(body[offset : offset + 4], 16)
        if size <= 4 or offset + size > len(body) - 4:
            raise ValueError('Invalid Git ref packet')
        line = body[offset + 4 : offset + size].rstrip(b'\n')
        offset += size
        record, _, caps = line.partition(b'\0')
        sha, ref = record.decode().split(' ', 1)
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('Invalid Git object identifier')
        if ref == 'HEAD':
            for cap in caps.decode().split():
                if cap.startswith('symref=HEAD:refs/heads/'):
                    default = cap.removeprefix('symref=HEAD:refs/heads/')
        elif ref.startswith('refs/heads/'):
            branches[ref.removeprefix('refs/heads/')] = sha
        elif ref.startswith('refs/tags/'):
            tags[ref.removeprefix('refs/tags/').removesuffix('^{}')] = sha
    return default, branches, tags


def source_url(prefix, url):
    if not prefix:
        return url
    return prefix.replace('{url}', url) if '{url}' in prefix else f'{prefix.rstrip("/")}/{url}'


async def fetch(client, url, hosts, limit):
    for _ in range(6):
        parsed = urlsplit(str(url))
        if (
            parsed.scheme != 'https'
            or parsed.hostname not in hosts
            or parsed.port not in (443, None)
            or parsed.username is not None
        ):
            raise ValueError('Untrusted GitHub download destination')
        async with client.stream('GET', url, headers={'Accept-Encoding': 'identity'}) as response:
            if response.has_redirect_location:
                url = response.url.join(response.headers['location'])
                continue
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=16384):
                if len(data) + len(chunk) > limit:
                    raise ValueError('GitHub response exceeds size limit')
                data.extend(chunk)
            return bytes(data)
    raise ValueError('Too many GitHub redirects')


class GitHubSources:
    def __init__(self, ap):
        config = ap.instance_config.data.get('plugin', {}).get('github_mirror', {})
        self.prefixes = ['', *(config.get('mirrors', []) if config.get('enabled', True) else [])]
        self.hosts = {'github.com', 'codeload.github.com', 'release-assets.githubusercontent.com'}
        self.hosts.update(urlsplit(prefix).hostname for prefix in self.prefixes if prefix)
        self.timeout = config.get('probe_timeout', 5)
        self.ap = ap
        self.cache = getattr(ap, '_github_ref_cache', {})
        ap._github_ref_cache = self.cache

    async def ranked(self, owner, repo):
        if (
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner)
            or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', repo)
            or repo in ('.', '..')
        ):
            raise ValueError('Invalid GitHub repository')
        url = f'https://github.com/{owner}/{repo}.git/info/refs?service=git-upload-pack'
        key = (url, tuple(self.prefixes))
        cached = self.cache.get(key)
        if cached and monotonic() < cached[0]:
            return cached[1]
        async with httpx.AsyncClient(trust_env=False, timeout=self.timeout) as client:

            async def probe(prefix):
                started = monotonic()
                try:
                    async with asyncio.timeout(self.timeout):
                        refs = parse_refs(await fetch(client, source_url(prefix, url), self.hosts, 2 << 20))
                    return prefix, round((monotonic() - started) * 1000), refs
                except (httpx.HTTPError, ValueError, TimeoutError):
                    return None

            results = [result for result in await asyncio.gather(*(probe(p) for p in self.prefixes)) if result]
        if not results:
            raise ValueError('No GitHub source returned repository refs')
        results.sort(key=lambda item: item[1] - (50 if not item[0] else 0))
        if len(self.cache) >= 16:
            del self.cache[next(iter(self.cache))]
        self.cache[key] = monotonic() + 600, results
        return results

    async def list_refs(self, url):
        parts = parse_github_repo_url(url)
        if not parts:
            raise ValueError('Invalid GitHub repository URL')
        prefix, latency, (default, branches, tags) = (await self.ranked(parts['owner'], parts['repo']))[0]
        requested = '/'.join(filter(None, (parts['ref'], parts['subdir'])))
        matching = [name for name in branches if requested == name or requested.startswith(name + '/')]
        ref = max(matching, key=len, default=parts['ref'])

        def entries(values):
            return [{'name': name, 'commit_sha': sha} for name, sha in list(values.items())[:500]]

        return {
            'owner': parts['owner'],
            'repo': parts['repo'],
            'default_branch': default,
            'requested_ref': ref,
            'source_subdir': requested[len(ref) :].lstrip('/'),
            'branches': entries(branches),
            'tags': entries(tags),
            'truncated': max(len(branches), len(tags)) > 500,
            'source': {
                'kind': 'mirror' if prefix else 'direct',
                'host': urlsplit(prefix).hostname or 'github.com',
                'latency_ms': latency,
            },
        }

    async def branch_package(self, info):
        from .github_archive import package_archive
        import zipfile

        ranked = await self.ranked(info['owner'], info['repo'])
        sha = ranked[0][2][1].get(info['ref'])
        if not sha:
            raise ValueError('Unknown GitHub branch')
        url = f'https://github.com/{info["owner"]}/{info["repo"]}/archive/{sha}.zip'
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            for prefix, _, _ in ranked:
                try:
                    data = await fetch(client, source_url(prefix, url), self.hosts, 32 << 20)
                    package = await asyncio.to_thread(package_archive, data, sha, info['source_subdir'])
                except (httpx.HTTPError, ValueError, zipfile.BadZipFile):
                    continue
                host = urlsplit(prefix).hostname or 'github.com'
                info.update(commit_sha=sha, download_source=host)
                self.ap.logger.info(f'GitHub branch package downloaded from {host}')
                return package
        raise ValueError('No source returned a valid GitHub branch archive')
