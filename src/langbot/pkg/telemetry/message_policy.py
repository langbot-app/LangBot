from ..command.catalog import DESCRIPTIONS


COMMANDS = frozenset(DESCRIPTIONS)
KINDS = {'builtin', 'plugin', 'processor'}
OUTCOMES = {'ok', 'denied', 'failed', 'intercepted'}
RULES = {
    'access-control',
    'group-respond-rules',
    'rate-limit',
    'ignore-rules',
    'content-filter',
    'outbound-content-filter',
}
LAYERS = {'bot', 'route'}
DIMENSIONS = {
    'command.run': {'kind': KINDS, 'name': COMMANDS | {'plugin'}, 'outcome': OUTCOMES},
    'policy.drop': {'item': RULES, 'layer': LAYERS},
    'hook.intercept': {'event': {'MessageReceived', 'CommandSent', 'NormalMessageReceived'}},
    'output.transform': {'kind': {'long_text', 'delay', 'at', 'quote', 'outbound_block'}},
}


def observe(ap, context, metric, **dims):
    from . import execution, trace, usage

    if trace.reporting_suppressed() or not usage.enabled(ap):
        return
    allowed = DIMENSIONS[metric]
    if any(dims.get(key) not in options for key, options in allowed.items()):
        return
    if metric == 'command.run' and (dims['kind'] == 'builtin') != (dims['name'] in COMMANDS):
        return
    usage.inc(ap, getattr(context, 'workspace_uuid', ''), metric, **dims)
    if metric == 'command.run':
        trace.admit()
        operation = 'builtin:' + dims['name'] if dims['kind'] == 'builtin' else dims['kind']
        execution.record(ap, context, family='command', operation=operation, outcome=dims['outcome'])
    elif metric == 'policy.drop':
        trace.admit()
        execution.record(
            ap, context, family='message_policy', operation=dims['item'], outcome='discarded', layer=dims['layer']
        )
