"""Record assertion evidence and interpret shared CLI/HTTP response contracts."""

import base64
import json


def checked(row, name, action):
    """Record an evaluated assertion; transport failures leave it unverified."""
    assertions = row.setdefault('assertions', {})
    try:
        result = action()
    except ValueError:
        assertions[name] = 'failed'
        raise
    assertions[name] = 'passed'
    return result


def check_response(data, expected, forbidden=()):
    text = json.dumps(data, ensure_ascii=False)
    if expected not in text:
        raise ValueError('Response does not contain the expected business result')
    if any(value in text for value in forbidden):
        raise ValueError('Response contains forbidden content')


def check_attachment(data, expected):
    replies = data.get('replies')
    if not isinstance(replies, list) or any(
        not isinstance(reply, dict)
        or not isinstance(reply.get('message_chain'), list)
        or any(not isinstance(part, dict) for part in reply['message_chain'])
        for reply in replies
    ):
        raise ValueError('Malformed file delivery response')
    attachments = [part for reply in replies for part in reply.get('message_chain', []) if part.get('type') == 'File']
    if len(attachments) != 1 or attachments[0].get('name') != expected['name']:
        raise ValueError('Expected exactly one file attachment with the configured name')
    encoded = attachments[0].get('base64')
    if not isinstance(encoded, str):
        raise ValueError('Attachment must contain base64 bytes')
    content = base64.b64decode(encoded, validate=True)
    if content != expected['text'].encode('utf-8'):
        raise ValueError('Exported attachment bytes differ from the expected fixture')
    return {'name': expected['name'], 'bytes': len(content), 'content_matched': True}


def check_fields(data, expected):
    for path, value in expected.items():
        actual = data
        try:
            for key in path.split('.'):
                actual = actual[int(key)] if isinstance(actual, list) else actual[key]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f'Response field {path} is missing or malformed') from exc
        if actual != value:
            raise ValueError(f'Response field {path} differs from the expected value')
    return expected
