from types import SimpleNamespace
from unittest.mock import Mock

from langbot.pkg.telemetry import execution, message_policy, trace, usage


def test_commands_and_discarded_policy_suppress_private_dimensions(monkeypatch):
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'space': {}}))
    context = SimpleNamespace(workspace_uuid='ws')
    inc, record = Mock(), Mock()
    monkeypatch.setattr(usage, 'inc', inc)
    monkeypatch.setattr(execution, 'record', record)
    observe = message_policy.observe
    observe(ap, context, 'command.run', kind='plugin', name='private-name', outcome='ok')
    with trace.suppress_reporting():
        observe(ap, context, 'policy.drop', item='rate-limit', layer='route')
    ap.instance_config.data['space']['disable_telemetry'] = True
    observe(ap, context, 'command.run', kind='builtin', name='help', outcome='denied')
    record.assert_not_called()
    inc.assert_not_called()
    ap.instance_config.data['space']['disable_telemetry'] = False
    observe(ap, context, 'policy.drop', item='rate-limit', layer='route')
    record.assert_called_once_with(
        ap, context, family='message_policy', operation='rate-limit', outcome='discarded', layer='route'
    )
