from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


AnalysisKind = Literal["batch", "abnormal", "product", "recipe", "similar"]


@dataclass(frozen=True)
class AnalysisCommand:
    kind: AnalysisKind
    raw_text: str
    command: str
    batch: str = ""
    abnormal: str = ""
    target: str = ""
    date_arg: str = ""


@dataclass(frozen=True)
class CommandParseResult:
    triggered: bool
    error: str = ""
    value: AnalysisCommand | None = None


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STRIP = "，,。.!！？?；;：:"


def _clean(text: str) -> str:
    return str(text or "").strip().strip(_STRIP)


def _split_commands(raw: str) -> set[str]:
    parts = re.split(r"[,\n;，；]+", raw or "")
    return {_clean(item) for item in parts if _clean(item)}


def parse_analysis_command(
    text: str,
    *,
    batch_commands: str = "批次分析,制程复盘",
    abnormal_commands: str = "异常分析",
    product_commands: str = "成品分析,成品趋势,成品异常",
    recipe_commands: str = "配方复盘,配方建议",
    similar_commands: str = "相似批次",
) -> CommandParseResult:
    raw_text = (text or "").strip()
    if not raw_text:
        return CommandParseResult(False)

    command_sets: list[tuple[AnalysisKind, set[str]]] = [
        ("batch", _split_commands(batch_commands)),
        ("abnormal", _split_commands(abnormal_commands)),
        ("product", _split_commands(product_commands)),
        ("recipe", _split_commands(recipe_commands)),
        ("similar", _split_commands(similar_commands)),
    ]
    all_commands = [(kind, cmd) for kind, cmds in command_sets for cmd in cmds]
    all_commands.sort(key=lambda item: len(item[1]), reverse=True)

    matched_kind: AnalysisKind | None = None
    matched_command = ""
    for kind, command in all_commands:
        if raw_text == command or raw_text.startswith(command + " ") or raw_text.startswith(command + "，"):
            matched_kind = kind
            matched_command = command
            break

    if matched_kind is None:
        return CommandParseResult(False)

    tail = _clean(raw_text[len(matched_command) :])
    tokens = [item for item in re.split(r"\s+", tail) if item]

    if matched_kind in {"batch", "recipe", "similar"}:
        if not tokens:
            return CommandParseResult(True, error=f"{matched_command} 参数无效，请提供批次号。")
        return CommandParseResult(
            True,
            value=AnalysisCommand(kind=matched_kind, raw_text=raw_text, command=matched_command, batch=_clean(tokens[0])),
        )

    if matched_kind == "abnormal":
        if not tokens:
            return CommandParseResult(True, error="异常分析参数无效，请使用：异常分析 批次号 异常现象。")
        abnormal = _clean(" ".join(tokens[1:])) if len(tokens) > 1 else ""
        return CommandParseResult(
            True,
            value=AnalysisCommand(
                kind="abnormal",
                raw_text=raw_text,
                command=matched_command,
                batch=_clean(tokens[0]),
                abnormal=abnormal,
            ),
        )

    date_arg = ""
    target_parts: list[str] = []
    for token in tokens:
        cleaned = _clean(token)
        if _DATE_RE.fullmatch(cleaned):
            if date_arg:
                return CommandParseResult(True, error="日期参数重复，请只保留一个 YYYY-MM-DD。")
            date_arg = cleaned
        elif cleaned:
            target_parts.append(cleaned)
    target = " ".join(target_parts).strip()
    return CommandParseResult(
        True,
        value=AnalysisCommand(
            kind="product",
            raw_text=raw_text,
            command=matched_command,
            target=target,
            date_arg=date_arg,
        ),
    )

