"""Exercise the Core connector against an isolated Docker Plugin Runtime."""

import argparse
import asyncio
import base64
import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langbot.pkg.api.context import ExecutionContext
from langbot.pkg.plugin import connector as connector_module
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.platform import message


async def docker(*args):
    process = await asyncio.create_subprocess_exec(
        'docker', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()


async def main(args):
    logging.basicConfig(level=logging.WARNING)
    execution = ExecutionContext(
        instance_uuid='lang394-test', workspace_uuid='lang394-workspace', placement_generation=1
    )
    connector_module.constants.instance_id = execution.instance_uuid
    connector_module.platform.use_websocket_to_connect_plugin_runtime = lambda: True
    app = SimpleNamespace(
        logger=logging.getLogger('lang394'),
        deployment=SimpleNamespace(mode='oss'),
        instance_config=SimpleNamespace(
            data={
                'plugin': {
                    'enable': True,
                    'runtime_ws_url': args.url,
                    'connect_timeout_seconds': 30,
                    'worker': {
                        'max_cpus': 1.0,
                        'max_memory_mb': 512,
                        'max_pids': 128,
                        'max_open_files': 256,
                        'max_file_size_mb': 512,
                        'require_hard_limits': False,
                    },
                },
                'space': {'url': ''},
            }
        ),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(return_value=execution)),
    )

    async def disconnected(connector):
        connector.schedule_reconnect()

    connector = PluginRuntimeConnector(app, disconnected)
    connector._synchronize_workspace = AsyncMock(return_value=[])
    connector._load_workspace_settings = AsyncMock(return_value=[])

    async def prepare():
        with connector.handler.installation_scope(connector._legacy_oss_bridge_binding(execution)):
            await connector.handler.list_plugins()

    connector._prepare_connected_runtime = prepare

    async def dispatch(chain):
        await connector.require_workspace_context(execution)
        return await connector.emit_event(
            events.MessageReceived(
                instance_uuid=execution.instance_uuid,
                workspace_uuid=execution.workspace_uuid,
                placement_generation=execution.placement_generation,
                message_chain=chain,
            )
        )

    async def restore():
        await asyncio.sleep(1)
        await docker('start', args.container)

    report = {}
    recovery = None
    try:
        await connector.initialize()
        await dispatch(message.MessageChain([message.Plain(text='before restart')]))
        await docker('stop', '--time', '1', args.container)
        async with asyncio.timeout(5):
            while connector._runtime_available() or connector._reconnect_task is None:
                await asyncio.sleep(0.01)
        recovery = asyncio.create_task(restore())
        started = time.monotonic()
        try:
            await dispatch(message.MessageChain([message.Plain(text='during restart')]))
            report['restart_dispatch'] = 'delivered'
        except Exception as exc:
            report['restart_dispatch'] = f'{type(exc).__name__}: {exc}'
        report['restart_dispatch_seconds'] = round(time.monotonic() - started, 3)
        await recovery
        if connector._reconnect_task is not None:
            await asyncio.wait_for(asyncio.shield(connector._reconnect_task), 35)
        payload = base64.b64encode(b'x' * (12 * 1024 * 1024)).decode('ascii')
        try:
            await dispatch(message.MessageChain([message.Image(base64=payload)]))
        except Exception as exc:
            report['oversized_attachment'] = f'{type(exc).__name__}: {exc}'
        await dispatch(message.MessageChain([message.Plain(text='after oversized attachment')]))
        report['following_message'] = 'delivered'
        report['runtime_oom_killed'] = await docker('inspect', '--format', '{{.State.OOMKilled}}', args.container)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.expect_recovery:
            assert report['restart_dispatch'] == 'delivered'
            assert 'reference' in report['oversized_attachment']
        else:
            assert report['restart_dispatch'].startswith('PluginRuntimeNotConnectedError:')
    finally:
        if recovery is not None:
            await recovery
        await connector.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--expect-recovery', action='store_true')
    asyncio.run(main(parser.parse_args()))
