"""Workflow triggers: what starts a run besides a bot message route."""

import re
import secrets

COMMAND_NAME = re.compile(r'^[^\s/]{1,32}$')
TARGET_TYPES = ('person', 'group')


def _covers(pattern, event_type):
    # Same rules as event routes: "*" or "group.*" cover a family of events.
    if event_type == 'message.received':
        return False
    if pattern == '*' or pattern == event_type:
        return True
    return pattern.endswith('.*') and event_type.startswith(pattern[:-1])


def accepts_event(workflow, event_type):
    for trigger in workflow.get('triggers', [{'type': 'message'}]):
        if trigger['type'] == 'message' and event_type == 'message.received':
            return True
        if trigger['type'] == 'event' and any(_covers(pattern, event_type) for pattern in trigger['events']):
            return True
    return False


def event_patterns(workflow):
    """Event patterns a bot can route to this workflow."""
    patterns = []
    for trigger in workflow.get('triggers', [{'type': 'message'}]) or []:
        if trigger.get('type') == 'message':
            patterns.append('message.received')
        elif trigger.get('type') == 'event':
            patterns.extend(trigger.get('events') or [])
    return list(dict.fromkeys(patterns))


def accepts_route(workflow, route_pattern):
    """Whether a bot event route (possibly a wildcard) can reach this workflow."""
    for pattern in event_patterns(workflow):
        if route_pattern == 'message.received':
            if pattern == route_pattern:
                return True
            continue
        if pattern == route_pattern or route_pattern == '*' or pattern == '*':
            return True
        if route_pattern.endswith('.*') and pattern.startswith(route_pattern[:-1]):
            return True
        if pattern.endswith('.*') and route_pattern.startswith(pattern[:-1]):
            return True
    return False


def triggers_of(workflow, kind):
    return [trigger for trigger in workflow.get('triggers') or [] if trigger.get('type') == kind]


def _cron_field(field, low, high):
    values = set()
    for part in field.split(','):
        step = 1
        if '/' in part:
            part, raw_step = part.split('/', 1)
            step = int(raw_step)
            if step < 1:
                raise ValueError('Cron step must be positive')
        if part == '*':
            start, end = low, high
        elif '-' in part:
            start, end = (int(value) for value in part.split('-', 1))
        else:
            start = end = int(part)
        if not low <= start <= end <= high:
            raise ValueError('Cron value out of range')
        values.update(range(start, end + 1, step))
    return values


def parse_cron(expression):
    """Parse a five-field cron expression into sets of allowed values."""
    fields = str(expression).split()
    if len(fields) != 5:
        raise ValueError('Cron needs five fields: minute hour day month weekday')
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    try:
        minute, hour, day, month, weekday = (
            _cron_field(field, low, high) for field, (low, high) in zip(fields, bounds)
        )
    except ValueError as exc:
        raise ValueError(f'Invalid cron expression: {exc}') from exc
    if 7 in weekday:
        weekday = (weekday - {7}) | {0}
    return minute, hour, day, month, weekday, fields[2] == '*', fields[4] == '*'


def cron_matches(expression, moment):
    minute, hour, day, month, weekday, any_day, any_weekday = parse_cron(expression)
    if moment.minute not in minute or moment.hour not in hour or moment.month not in month:
        return False
    day_ok = moment.day in day
    weekday_ok = (moment.isoweekday() % 7) in weekday
    # Standard cron: when both day fields are restricted, either may match.
    if any_day or any_weekday:
        return day_ok and weekday_ok
    return day_ok or weekday_ok


def schedule_due(trigger, moment):
    """Whether a schedule trigger fires in the minute of ``moment`` (workflow timezone)."""
    if trigger.get('every'):
        every = int(trigger['every'])
        return (moment.hour * 60 + moment.minute) % every == 0
    return cron_matches(trigger['cron'], moment)


def parse_command_args(trigger, text):
    """Split the text after a command into named arguments; the last one takes the rest."""
    declared = [arg for arg in trigger.get('args') or [] if isinstance(arg, dict) and arg.get('name')]
    words = text.split(maxsplit=max(len(declared) - 1, 0)) if declared else []
    args = {arg['name']: (words[index] if index < len(words) else '') for index, arg in enumerate(declared)}
    missing = [arg['name'] for arg in declared if arg.get('required') and not args[arg['name']]]
    return args, missing


def validate_triggers(triggers):
    """Validate triggers in place; webhook triggers receive their secret here."""
    if not isinstance(triggers, list) or not triggers:
        raise ValueError('Choose at least one trigger')
    commands = set()
    for trigger in triggers:
        kind = trigger.get('type') if isinstance(trigger, dict) else None
        if kind == 'message':
            continue
        if kind == 'event':
            events = trigger.get('events')
            if (
                not isinstance(events, list)
                or not events
                or not all(isinstance(event, str) and event and event != 'message.received' for event in events)
            ):
                raise ValueError('Select at least one non-message event')
            continue
        if kind == 'command':
            names = [trigger.get('name'), *(trigger.get('aliases') or [])]
            if not all(isinstance(name, str) and COMMAND_NAME.match(name) for name in names):
                raise ValueError('Command names must be 1-32 characters without spaces or "/"')
            if len(set(names)) != len(names) or commands & set(names):
                raise ValueError('A command name is used twice in this workflow')
            commands.update(names)
            args = trigger.get('args') or []
            if not isinstance(args, list) or not all(
                isinstance(arg, dict) and isinstance(arg.get('name'), str) and arg['name'].strip() for arg in args
            ):
                raise ValueError('Every command argument needs a name')
            bots = trigger.get('bots', 'all')
            if bots != 'all' and not (isinstance(bots, list) and all(isinstance(bot, str) for bot in bots)):
                raise ValueError('Command bots must be "all" or a list of bots')
            continue
        if kind == 'schedule':
            if trigger.get('every'):
                every = trigger['every']
                if not isinstance(every, int) or not 1 <= every <= 1440:
                    raise ValueError('Repeat interval must be 1-1440 minutes')
            else:
                parse_cron(trigger.get('cron', ''))
            if not isinstance(trigger.get('bot_uuid'), str) or not trigger['bot_uuid']:
                raise ValueError('Choose the bot that sends scheduled messages')
            targets = trigger.get('targets')
            if (
                not isinstance(targets, list)
                or not targets
                or not all(
                    isinstance(target, dict)
                    and target.get('type') in TARGET_TYPES
                    and isinstance(target.get('id'), str)
                    and target['id'].strip()
                    for target in targets
                )
            ):
                raise ValueError('Add at least one chat to send scheduled messages to')
            continue
        if kind == 'webhook':
            if not isinstance(trigger.get('bot_uuid'), str) or not trigger['bot_uuid']:
                raise ValueError('Choose the bot that receives the webhook')
            if not isinstance(trigger.get('secret'), str) or len(trigger['secret']) < 16:
                trigger['secret'] = secrets.token_urlsafe(24)
            continue
        raise ValueError('Unsupported workflow trigger')
