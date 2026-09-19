"""Packaged capability catalog and projections from existing runtime declarations."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from . import diagnostic_privacy as privacy


@lru_cache(maxsize=1)
def catalog():
    result = {}
    base = Path(__file__).resolve().parents[1] / 'platform'
    for manifest in sorted((base / 'adapters').glob('*/manifest.yaml')):
        data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
        spec = data.get('spec', {})
        name = data['metadata']['name']
        privacy.code_value('adapter', name)
        events = spec.get('supported_events', [])
        apis = spec.get('supported_apis', {})
        apis = apis if isinstance(apis, list) else [v for items in apis.values() for v in items]
        for event in events:
            privacy.code_value('platform_event_type', event)
        for operation in apis:
            privacy.code_value('operation', operation)
        specific_apis = []
        for api in spec.get('platform_specific_apis', []):
            privacy.code_value('operation', api['action'])
            specific_apis.append(privacy.code_value('operation', 'platform_api.' + api['action']))
        result[manifest.parent.name] = {
            'adapter': name,
            'events': events,
            'apis': apis,
            'specific_apis': specific_apis,
        }
    return result


def adapter_fields(adapter):
    module = type(adapter).__module__.split('.')
    entry = next((entry for directory, entry in catalog().items() if directory in module), None)
    return {'adapter': entry['adapter']} if entry else {}


def _snapshot_bot(bot, *, listener_registered=False):
    from . import diagnostics

    manager = getattr(bot.ap, 'diagnostics', None)
    if not isinstance(manager, diagnostics.DiagnosticsManager) or not manager.enabled:
        return
    fields = adapter_fields(bot.adapter)
    if not fields:
        return
    fields['workspace_uuid'] = bot.execution_context.workspace_uuid
    entry = next(e for e in catalog().values() if e['adapter'] == fields['adapter'])
    for capability_type, method, declared in (
        ('event', 'get_supported_events', entry['events']),
        ('api', 'get_supported_apis', entry['apis'] + entry['specific_apis']),
    ):
        try:
            supported = set(getattr(bot.adapter, method)() or [])
        except Exception:
            supported = set()
        for name in declared:
            if name == 'call_platform_api':
                continue
            manager.emit(
                'capability',
                name if capability_type == 'api' else 'platform.receive',
                'succeeded',
                source='platform',
                stage='snapshot',
                **fields,
                platform_event_type=name if capability_type == 'event' else '',
                attributes={
                    'capability_type': capability_type,
                    'capability_name': name,
                    'supported': name in supported
                    or (name in entry['specific_apis'] and 'call_platform_api' in supported),
                    'configured': True,
                    **({'listener_registered': listener_registered} if capability_type == 'event' else {}),
                },
            )


def snapshot_bot(bot, *, listener_registered=False):
    try:
        _snapshot_bot(bot, listener_registered=listener_registered)
    except Exception:
        pass
