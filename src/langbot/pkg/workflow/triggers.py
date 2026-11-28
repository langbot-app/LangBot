def accepts_event(workflow, event_type):
    for trigger in workflow.get('triggers', [{'type': 'message'}]):
        if trigger['type'] == 'message' and event_type == 'message.received':
            return True
        if trigger['type'] == 'event' and event_type in trigger['events']:
            return True
    return False


def validate_triggers(triggers):
    if not isinstance(triggers, list) or not triggers:
        raise ValueError('Choose at least one trigger')
    for trigger in triggers:
        kind = trigger.get('type') if isinstance(trigger, dict) else None
        if kind == 'message':
            continue
        if kind != 'event':
            raise ValueError('Unsupported workflow trigger')
        events = trigger.get('events')
        if (
            not isinstance(events, list)
            or not events
            or not all(isinstance(event, str) and event and event != 'message.received' for event in events)
        ):
            raise ValueError('Select at least one non-message event')
