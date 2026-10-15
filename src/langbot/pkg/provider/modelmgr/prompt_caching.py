"""Opt-in upstream prompt caching; never cache generated answers locally."""

import copy
import hashlib

from .errors import RequesterError


def _has_breakpoint(value):
    if isinstance(value, dict):
        return 'cache_control' in value or any(_has_breakpoint(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_breakpoint(item) for item in value)
    return False


def apply_prompt_caching(args, state, *, provider, family):
    config = args.pop('prompt_caching', None)
    if config is None:
        return
    if not isinstance(config, dict) or set(config) - {'mode', 'retention', 'ttl'}:
        raise RequesterError('Invalid prompt_caching fields', code='invalid_policy')
    mode = config.get('mode', 'provider_default')
    if mode not in ('provider_default', 'openai', 'anthropic'):
        raise RequesterError('Unsupported prompt_caching mode', code='invalid_policy')
    if mode == 'provider_default':
        if set(config) - {'mode'}:
            raise RequesterError('Cache settings require an explicit mode', code='invalid_policy')
        return
    if mode == 'openai':
        if provider not in ('openai', 'openrouter') or family not in ('openai', 'openrouter'):
            raise RequesterError('OpenAI caching requires an OpenAI-compatible model', code='invalid_policy')
        if 'ttl' in config or config.get('retention') not in (None, 'in_memory', '24h'):
            raise RequesterError('Invalid OpenAI cache retention', code='invalid_policy')
        body = copy.deepcopy(args.get('extra_body') or {})
        if not isinstance(body, dict):
            raise RequesterError('extra_body must be an object', code='invalid_policy')
        # Bypass LiteLLM's model-specific parameter filter for explicit opt-in
        # caching fields as well as generated hints. The SDK's extra_body wins
        # when the same native field appears in both locations.
        for key in ('prompt_cache_key', 'prompt_cache_retention', 'prompt_cache_options'):
            if key in args:
                body.setdefault(key, args.pop(key))
        # Explicit provider-native settings win. A key is a routing hint only;
        # it neither enables caching nor guarantees a hit.
        if (
            state
            and state.conversation_id
            and not any(key in body for key in ('prompt_cache_key', 'prompt_cache_options'))
        ):
            scope = f'{state.conversation_id}:{args["model"]}'
            body['prompt_cache_key'] = 'lb-' + hashlib.sha256(scope.encode()).hexdigest()
        if config.get('retention') and not any(
            key in location for key in ('prompt_cache_retention', 'prompt_cache_options') for location in (args, body)
        ):
            body['prompt_cache_retention'] = config['retention']
        if body:
            args['extra_body'] = body
        return
    if family != 'anthropic':
        raise RequesterError('Anthropic caching requires an Anthropic model', code='invalid_policy')
    if 'retention' in config or config.get('ttl', '5m') not in ('5m', '1h'):
        raise RequesterError('Invalid Anthropic cache TTL', code='invalid_policy')
    # Existing manual or automatic breakpoints are authoritative. Do not exceed
    # a provider's breakpoint limit or change its TTL ordering.
    if _has_breakpoint(args):
        return
    messages = copy.deepcopy(args['messages'])
    boundary = None
    for message in messages:
        if message.get('role') not in ('system', 'developer'):
            break
        content = message.get('content')
        if isinstance(content, str) and content:
            message['content'] = [{'type': 'text', 'text': content}]
        if isinstance(message.get('content'), list):
            for part in message['content']:
                if isinstance(part, dict) and part.get('type') == 'text' and part.get('text'):
                    boundary = part
    if boundary is not None:
        boundary['cache_control'] = {'type': 'ephemeral', 'ttl': config.get('ttl', '5m')}
        args['messages'] = messages
