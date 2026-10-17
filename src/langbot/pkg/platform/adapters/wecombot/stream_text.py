"""Render multi-round reasoning as one WeCom thinking section."""

import re


def format_stream_text(content: str) -> str:
    if content.strip().lower() in {'<', '<t', '<th', '<thi', '<thin', '<think'}:
        return ''
    if '<think' not in content.lower() and '</think' not in content.lower():
        return content
    # Every invocation receives the full snapshot, so split tags may simply
    # wait for the next snapshot instead of leaking into the visible answer.
    content = re.sub(r'<(?:/?t(?:h(?:i(?:n(?:k)?)?)?)?|/?)$', '', content, flags=re.IGNORECASE)
    tokens = re.split(r'(</?think\s*>)', content, flags=re.IGNORECASE)
    thoughts: list[str] = []
    answers: list[str] = []
    thinking = False
    for token in tokens:
        if re.fullmatch(r'<think\s*>', token, flags=re.IGNORECASE):
            thinking = True
        elif re.fullmatch(r'</think\s*>', token, flags=re.IGNORECASE):
            thinking = False
        elif token.strip():
            (thoughts if thinking else answers).append(token.strip())
    if not thoughts:
        return '\n\n'.join(answers)
    reasoning = '\n\n'.join(thoughts)
    answer = '\n\n'.join(answers)
    if thinking and not answer:
        return f'<think>\n{reasoning}'
    return f'<think>\n{reasoning}\n</think>' + (f'\n\n{answer}' if answer else '')
