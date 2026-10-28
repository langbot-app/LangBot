"""User-side daemon for Claude Code Runner."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging

from pkg.native_cli import NativeClaudeCodeDaemon


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect Claude Code CLI to LangBot.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--daemon-id", required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--reconnect-delay", type=float, default=5.0)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    daemon = NativeClaudeCodeDaemon(
        url=args.url,
        daemon_id=args.daemon_id,
        token=args.token,
        reconnect_delay=args.reconnect_delay,
    )
    await daemon.run_forever()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())
