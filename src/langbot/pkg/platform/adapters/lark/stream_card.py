"""Compact streaming previews and a final card with collapsible reasoning."""

import re


def split_content(content: str) -> tuple[str, str]:
    reasoning, answer = [], []
    inside, offset = False, 0
    for marker in re.finditer(r'</?think>', content, re.IGNORECASE):
        (reasoning if inside else answer).append(content[offset : marker.start()])
        inside = marker.group().lower() == '<think>'
        offset = marker.end()
    tail = content[offset:]
    for size in range(min(7, len(tail)), 0, -1):
        if any(tag.startswith(tail[-size:].lower()) for tag in ('<think>', '</think>')):
            tail = tail[:-size]
            break
    (reasoning if inside else answer).append(tail)
    return tuple('\n\n'.join(part.strip() for part in pieces if part.strip()) for pieces in (reasoning, answer))


def streaming_text(content: str) -> str:
    reasoning, answer = split_content(content)
    if not reasoning:
        return answer
    # Keep live cards compact; the final card retains the complete reasoning.
    preview = reasoning[-360:]
    if len(reasoning) > 360:
        preview = '…' + preview
    quote = '> ' + preview.replace('\n', '\n> ')
    return '**思考过程 / Thinking**\n\n' + quote + ('\n\n---\n\n' + answer if answer else '')


def build_card(content: str = '', *, streaming: bool = False, finished: bool = True) -> dict:
    reasoning, answer = split_content(content)
    elements = []
    if streaming:
        elements.append({'tag': 'markdown', 'content': streaming_text(content), 'element_id': 'streaming_txt'})
    else:
        if reasoning:
            elements.append(
                {
                    'tag': 'collapsible_panel',
                    'expanded': not finished,
                    'header': {'title': {'tag': 'plain_text', 'content': '思考过程 / Thinking'}},
                    'elements': [{'tag': 'markdown', 'content': reasoning}],
                }
            )
        if answer:
            elements.append({'tag': 'markdown', 'content': answer})
    elements.append(
        {
            'tag': 'column_set',
            'horizontal_spacing': '8px',
            'columns': [
                {
                    'tag': 'column',
                    'width': 'weighted',
                    'weight': 1,
                    'vertical_align': 'center',
                    'elements': [
                        {'tag': 'markdown', 'content': '内容由 AI 生成 / AI-generated', 'text_size': 'notation'}
                    ],
                },
                {
                    'tag': 'column',
                    'width': 'auto',
                    'vertical_align': 'center',
                    'elements': [
                        {
                            'tag': 'markdown',
                            'content': '[LangBot](https://langbot.app?utm_source=feishu&utm_medium=bot_card&utm_campaign=langbot)',
                            'text_size': 'notation',
                            'text_align': 'right',
                            'icon': {
                                'tag': 'custom_icon',
                                'img_key': 'img_v3_02p3_05c65d5d-9bad-440a-a2fb-c89571bfd5bg',
                            },
                        }
                    ],
                },
            ],
        }
    )
    config = {'update_multi': True}
    if streaming:
        config.update(
            streaming_mode=True,
            streaming_config={
                'print_step': {'default': 3},
                'print_frequency_ms': {'default': 40},
                'print_strategy': 'fast',
            },
        )
    return {
        'schema': '2.0',
        'config': config,
        'body': {'direction': 'vertical', 'padding': '12px 12px 12px 12px', 'elements': elements},
    }
