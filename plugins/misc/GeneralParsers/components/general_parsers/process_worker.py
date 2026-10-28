"""Worker entry point for :mod:`components.general_parsers.isolated_process`.

A fresh interpreter runs this file as a plain script:

    python process_worker.py <plugin_root> <module:attribute>

The pickled positional arguments are read from stdin, the target is imported
from the plugin and the pickled ``('ok', result)`` / ``('error', message)``
envelope is written back to the stdout pipe.  Python level output is captured in
memory and attached to errors, and the stdout pipe is duplicated away before
any parsing starts, so nothing the parsed document or its dependencies print can
corrupt the result channel.
"""

from __future__ import annotations

import io
import os
import pickle
import sys
from importlib import import_module

_DIAGNOSTIC_LIMIT = 2000
_SEARCH_PATH_ENV = 'GENERAL_PARSERS_WORKER_SEARCH_PATH'


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(descriptor, view):]


def _extend_search_path(plugin_root: str) -> None:
    inherited = [entry for entry in os.environ.get(_SEARCH_PATH_ENV, '').split(os.pathsep) if entry]
    for entry in reversed(inherited):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    if plugin_root not in sys.path:
        sys.path.insert(0, plugin_root)


def _resolve_target(plugin_root: str, reference: str):
    _extend_search_path(plugin_root)
    module_name, _, attribute = reference.partition(':')
    if not module_name or not attribute:
        raise ValueError(f'invalid worker target reference: {reference!r}')
    return getattr(import_module(module_name), attribute)


def _diagnostics(output: io.StringIO) -> str:
    text = output.getvalue().strip()
    return text[-_DIAGNOSTIC_LIMIT:]


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    plugin_root, reference = sys.argv[1], sys.argv[2]

    result_descriptor = os.dup(1)
    os.dup2(2, 1)  # keep the result pipe free of stray native output
    output = io.StringIO()
    sys.stdout = output
    sys.stderr = output

    try:
        arguments = pickle.load(sys.stdin.buffer)
        result = _resolve_target(plugin_root, reference)(*arguments)
    except BaseException as error:  # noqa: BLE001 - reported to the parent instead of raised
        message = f'{type(error).__name__}: {error}'
        diagnostics = _diagnostics(output)
        if diagnostics:
            message = f'{message}\n--- worker output ---\n{diagnostics}'
        envelope = ('error', message)
    else:
        envelope = ('ok', result)

    try:
        _write_all(result_descriptor, pickle.dumps(envelope, protocol=pickle.HIGHEST_PROTOCOL))
    except OSError:
        return 1
    finally:
        os.close(result_descriptor)
    return 0


if __name__ == '__main__':
    sys.exit(main())
