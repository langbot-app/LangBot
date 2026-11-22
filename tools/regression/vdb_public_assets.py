"""Download only versioned public benchmark inputs into an external cache."""

from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
from urllib.request import urlopen


def fetch_asset(cache, name, url, expected_sha256, max_bytes):
    if urlsplit(url).scheme != 'https':
        raise ValueError(f'Refusing a non-HTTPS asset URL: {name}')
    cache.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = cache / name
    if target.exists():
        digest = sha256()
        with target.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected_sha256:
            raise ValueError(f'Pinned cache file has wrong SHA-256; remove and retry: {name}')
        return target

    temporary = None
    try:
        with NamedTemporaryFile(dir=cache, prefix='.download-', delete=False) as sink:
            temporary = Path(sink.name)
            digest, size = sha256(), 0
            with urlopen(url, timeout=30) as response:
                if urlsplit(response.geturl()).scheme != 'https':
                    raise ValueError(f'Refusing a non-HTTPS asset URL: {name}')
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    size += len(block)
                    if size > max_bytes:
                        raise ValueError(f'Download exceeds pinned asset limit: {name}')
                    digest.update(block)
                    sink.write(block)
            if digest.hexdigest() != expected_sha256:
                raise ValueError(f'Download SHA-256 mismatch: {name}')
        temporary.replace(target)
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
