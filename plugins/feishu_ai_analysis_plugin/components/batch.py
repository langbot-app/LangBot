from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BatchIdentity:
    raw: str
    model: str
    stage: str
    core: str
    segment: str
    line: str


_STAGE_CODES = {"TL", "CM", "XM", "HP", "QQT", "SC", "FS"}


def field_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "".join(field_to_text(item) for item in value).strip()
    if isinstance(value, dict):
        for key in ("text", "name", "en_name", "email", "link", "url"):
            text = field_to_text(value.get(key))
            if text:
                return text
        return str(value).strip()
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    text = field_to_text(value).replace(",", ".")
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def normalize_batch(batch_text: Any) -> BatchIdentity:
    raw = field_to_text(batch_text)
    text = re.sub(r"\s*-\s*", "-", raw.upper())
    text = text.replace("—", "-").replace("－", "-")

    model = ""
    stage = ""
    segment = ""
    core = ""

    model_match = re.search(r"\b(S\d{2,4})\b", text)
    if model_match:
        model = model_match.group(1)

    parts = [part for part in text.split("-") if part]
    for part in parts:
        if part in _STAGE_CODES:
            stage = part
            break

    core_match = re.search(r"(D[A-Z]\d{4}-\d{3,})", text)
    if core_match:
        core = core_match.group(1)
    else:
        short_match = re.search(r"\b([A-Z]\d{4}-\d{3,})\b", text)
        if short_match:
            core = f"D{short_match.group(1)}"

    segment_match = re.search(r"(?:^|-)([A-Z]\d)(?:-|$)", text)
    if segment_match:
        candidate = segment_match.group(1)
        if not re.fullmatch(r"D[A-Z]", candidate):
            segment = candidate

    line = ""
    if segment:
        line = segment[0]
    elif core and len(core) >= 2:
        line = core[1]

    return BatchIdentity(raw=raw, model=model, stage=stage, core=core or text, segment=segment, line=line)


def normalize_key(text: str) -> str:
    return re.sub(r"[\s_\-()（）【】\[\]/.%+：:]+", "", field_to_text(text).lower())


def compact_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")

