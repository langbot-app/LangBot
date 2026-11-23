"""Keep LiteLLM's bundled tiktoken encodings usable offline.

LiteLLM ships cl100k / o200k / p50k encoding files and points tiktoken at
them, so token counting normally never touches the network. Its Windows
wheels (``win_amd64``) ship those files with CRLF line endings, which fail
tiktoken's SHA-256 check. tiktoken then deletes the cached file and downloads
it again from openaipublic.blob.core.windows.net. Where that host is slow or
blocked, the first token count of every process hangs on the download, and
LiteLLM's cost calculation on the event loop waits on the same import lock.

``ensure_offline_tiktoken_cache`` runs before LiteLLM is imported. When the
bundled files contain CRLF, it writes LF copies into a LangBot-owned
directory and points LiteLLM at it through ``CUSTOM_TIKTOKEN_CACHE_DIR``. It
does nothing when the user already set that variable or the bundled files
are fine (Linux and macOS wheels, Docker images).
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

CUSTOM_CACHE_ENV = 'CUSTOM_TIKTOKEN_CACHE_DIR'
# tiktoken cache files are named after the sha1 of their source URL.
_CACHE_FILE_NAME = re.compile(r'^[0-9a-f]{40}$')


def _bundled_tokenizer_dir() -> Path | None:
    try:
        spec = importlib.util.find_spec('litellm')
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    for location in spec.submodule_search_locations:
        candidate = Path(location) / 'litellm_core_utils' / 'tokenizers'
        if candidate.is_dir():
            return candidate
    return None


def ensure_offline_tiktoken_cache(target_dir: str | os.PathLike[str]) -> Path | None:
    """Return the directory LiteLLM was pointed at, or None when nothing was needed."""
    if os.environ.get(CUSTOM_CACHE_ENV):
        return None
    bundled = _bundled_tokenizer_dir()
    if bundled is None:
        return None

    sources = sorted(p for p in bundled.iterdir() if p.is_file() and _CACHE_FILE_NAME.match(p.name))
    if not sources:
        return None
    contents = {}
    for source in sources:
        data = source.read_bytes()
        if b'\r\n' not in data:
            continue
        contents[source.name] = data.replace(b'\r\n', b'\n')
    if not contents:
        return None

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    for source in sources:
        data = contents.get(source.name)
        if data is None:
            data = source.read_bytes()
        destination = target / source.name
        if destination.is_file() and destination.read_bytes() == data:
            continue
        temporary = destination.with_name(f'{destination.name}.{os.getpid()}.tmp')
        temporary.write_bytes(data)
        os.replace(temporary, destination)

    os.environ[CUSTOM_CACHE_ENV] = str(target)
    return target
