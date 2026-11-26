from . import schema
from ..platform.botmgr import RuntimeBot


def _command_policy(policy):
    return (
        *(policy['trigger'][key] for key in ('group-respond-rules', 'access-control', 'ignore-rules')),
        policy['safety'],
        policy['output']['long-text-processing'],
        policy['output']['force-delay'],
        policy['output']['misc']['at-sender'],
        policy['output']['misc']['quote-origin'],
        schema.enabled_plugins(policy),
    )


def policy_promotion(bot_uuid, default, bindings):
    routes = [
        route for route in bindings if RuntimeBot._match_event_pattern('message.received', route.get('event_pattern'))
    ]
    route_ids = [route['id'] for route in routes if 'policy' in route]
    if not route_ids:
        return None
    current = schema.coerce_policy(schema.resolve_policy(default))
    effective = [schema.coerce_policy(schema.resolve_policy(default, route.get('policy'))) for route in routes]
    candidate = effective[0]
    if any(policy != candidate for policy in effective[1:]):
        return None
    return {
        'bot_uuid': bot_uuid,
        'route_ids': route_ids,
        'message_policy': candidate,
        'changes_unrouted_commands': _command_policy(candidate) != _command_policy(current),
    }
