from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Optional

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CSV_SPLIT_RE = re.compile(r"[,，、;；]+")
_STRIP_PUNCT = "，,。.!！？?；;：:"

_DEFAULT_TOUCH_SEGMENTS = ("A1", "A2", "B1", "B2")
_TOUCH_USAGE = "摸料参数无效，请使用：摸料 A1|A2|B1|B2。"
_TOUCH_TAIL_CLEAN_RE = re.compile(r"[，,。.!！？?；;：:\-/\\_|]+")


@dataclass(frozen=True)
class ReportCommand:
    raw_text: str
    command: str
    date_arg: Optional[str]
    date_value: Optional[dt.date]
    sheet_names: list[str]


@dataclass(frozen=True)
class TouchMaterialCommand:
    raw_text: str
    command: str
    segment: str


@dataclass(frozen=True)
class SheetImageCommand:
    raw_text: str
    command: str
    sheet_name: str


@dataclass(frozen=True)
class CommandParseResult:
    triggered: bool
    error: str = ""
    value: Optional[ReportCommand | TouchMaterialCommand | SheetImageCommand] = None


def _normalize_token(text: str) -> str:
    return text.strip().strip(_STRIP_PUNCT)


def _split_csv_values(raw: str) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for part in _CSV_SPLIT_RE.split(raw):
        value = _normalize_token(part)
        if value:
            out.append(value)
    return out


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def parse_report_command(text: str, allowed_commands: set[str]) -> CommandParseResult:
    raw_text = (text or "").strip()
    if not raw_text:
        return CommandParseResult(triggered=False)

    parts = [p for p in re.split(r"\s+", raw_text) if p]
    if not parts:
        return CommandParseResult(triggered=False)

    cmd = _normalize_token(parts[0])
    if not cmd or cmd not in allowed_commands:
        return CommandParseResult(triggered=False)

    date_arg: Optional[str] = None
    date_value: Optional[dt.date] = None
    sheet_names: list[str] = []

    for token in parts[1:]:
        cleaned = _normalize_token(token)
        if not cleaned:
            continue

        # 支持把日期和线别写在同一 token（例如：2026-03-03,S18-A线）
        fragments = _split_csv_values(cleaned)
        if not fragments:
            fragments = [cleaned]

        for frag in fragments:
            if _DATE_RE.fullmatch(frag):
                if date_arg is not None:
                    return CommandParseResult(triggered=True, error="日期参数重复，请只保留一个 YYYY-MM-DD。")
                try:
                    date_value = dt.date.fromisoformat(frag)
                except ValueError:
                    return CommandParseResult(triggered=True, error=f"日期格式无效：{frag}，请使用 YYYY-MM-DD。")
                date_arg = frag
                continue
            sheet_names.append(frag)

    value = ReportCommand(
        raw_text=raw_text,
        command=cmd,
        date_arg=date_arg,
        date_value=date_value,
        sheet_names=_dedupe_keep_order(sheet_names),
    )
    return CommandParseResult(triggered=True, value=value)


def _normalize_touch_segments(allowed_segments: set[str] | None) -> list[str]:
    if not allowed_segments:
        return list(_DEFAULT_TOUCH_SEGMENTS)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in allowed_segments:
        segment = _normalize_token(str(item)).upper()
        if not segment or segment in seen:
            continue
        seen.add(segment)
        normalized.append(segment)
    return normalized or list(_DEFAULT_TOUCH_SEGMENTS)


def _touch_usage(segments: list[str]) -> str:
    return f"摸料参数无效，请使用：摸料 {'|'.join(segments)}。"


def parse_touch_material_command(
    text: str,
    allowed_commands: set[str],
    allowed_segments: set[str] | None = None,
) -> CommandParseResult:
    raw_text = (text or "").strip()
    if not raw_text:
        return CommandParseResult(triggered=False)

    normalized_allowed = {_normalize_token(item) for item in allowed_commands if _normalize_token(item)}
    if not normalized_allowed:
        normalized_allowed = {"摸料"}

    collapsed = re.sub(r"\s+", "", raw_text)
    collapsed = _normalize_token(collapsed)
    if not collapsed:
        return CommandParseResult(triggered=False)

    matched_command = ""
    for candidate in sorted(normalized_allowed, key=len, reverse=True):
        if collapsed.startswith(candidate):
            matched_command = candidate
            break

    if not matched_command:
        return CommandParseResult(triggered=False)

    valid_segments = _normalize_touch_segments(allowed_segments)
    usage = _touch_usage(valid_segments)
    tail = collapsed[len(matched_command) :]
    tail = _TOUCH_TAIL_CLEAN_RE.sub("", tail).upper()
    tail = _normalize_token(tail)
    if not tail:
        return CommandParseResult(triggered=True, error=usage)

    if tail not in set(valid_segments):
        return CommandParseResult(triggered=True, error=usage)

    return CommandParseResult(
        triggered=True,
        value=TouchMaterialCommand(raw_text=raw_text, command=matched_command, segment=tail),
    )


def parse_sheet_image_command(text: str, allowed_commands: set[str]) -> CommandParseResult:
    raw_text = (text or "").strip()
    if not raw_text:
        return CommandParseResult(triggered=False)

    parts = [p for p in re.split(r"\s+", raw_text) if p]
    if not parts:
        return CommandParseResult(triggered=False)

    cmd = _normalize_token(parts[0])
    if not cmd or cmd not in allowed_commands:
        return CommandParseResult(triggered=False)

    sheet_name = raw_text[len(parts[0]) :].strip()
    sheet_name = _normalize_token(sheet_name)
    if not sheet_name:
        return CommandParseResult(triggered=True, error="图片参数无效，请使用：图片 表名。")

    return CommandParseResult(
        triggered=True,
        value=SheetImageCommand(raw_text=raw_text, command=cmd, sheet_name=sheet_name),
    )
