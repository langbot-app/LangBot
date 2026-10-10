"""Render reasoning markers without changing the pipeline output policy."""

import re

_MARKER = re.compile(r"</?think>", re.IGNORECASE)


def visible_think_markers(content: str, markdown: bool = True) -> str:
    def replace(match):
        tag = match.group(1).lower()
        separator = "\n\n" if markdown else "\n"
        return separator + (f"`{tag}`" if markdown else tag) + separator

    # Normalize only marker boundaries; preserve paragraph spacing in the body.
    return re.sub(r"[ \t\r\n]*(</?think>)[ \t\r\n]*", replace, content, flags=re.IGNORECASE).strip()


def card_text_fields(content: str) -> dict[str, str]:
    thinking, answer = [], []
    inside = False
    offset = 0
    for match in _MARKER.finditer(content):
        (thinking if inside else answer).append(content[offset:match.start()])
        inside = match.group(0).lower() == "<think>"
        offset = match.end()
    tail = content[offset:]
    # A stream can stop in the middle of an opening or closing marker.
    for size in range(min(len(tail), 7), 0, -1):
        if any(marker.startswith(tail[-size:].lower()) for marker in ("<think>", "</think>")):
            tail = tail[:-size]
            break
    (thinking if inside else answer).append(tail)
    reasoning = "\n".join(part.strip() for part in thinking if part.strip())
    response = "\n".join(part.strip() for part in answer if part.strip())
    return {
        "reasoning": "> " + reasoning.replace("\n", "\n> ") if reasoning else "",
        "answer": response,
        "hasReasoning": "true" if reasoning else "",
    }
