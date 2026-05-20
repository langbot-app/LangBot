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
_BATCH_RE = re.compile(r"\b(?:S\d{2,4}-)?(?:[A-Z]{2,4}-)?D[A-Z]\d{4}-\d{3,}(?:-[A-Z]\d)?\b", re.IGNORECASE)
_STRIP = "，,。.!！？?；;：:"


def _clean(text: str) -> str:
    return str(text or "").strip().strip(_STRIP)


def _split_commands(raw: str) -> set[str]:
    parts = re.split(r"[,\n;，；]+", raw or "")
    return {_clean(item) for item in parts if _clean(item)}


def _extract_batch(text: str) -> str:
    match = _BATCH_RE.search(text or "")
    return _clean(match.group(0)) if match else ""


def _looks_like_feishu_analysis_request(text: str) -> bool:
    return "飞书" in text and any(word in text for word in ("表格", "多维表", "Base", "Sheets", "sheet", "数据"))


def _parse_natural_language_request(raw_text: str) -> CommandParseResult:
    batch = _extract_batch(raw_text)
    has_analysis = any(word in raw_text for word in ("分析", "复盘", "诊断", "原因", "建议", "优化", "推荐"))
    mentions_feishu_data = _looks_like_feishu_analysis_request(raw_text)

    if "相似批次" in raw_text:
        if not batch:
            return CommandParseResult(True, error="已命中相似批次分析，但缺少批次号。请使用：相似批次 <批次号>。")
        return CommandParseResult(True, value=AnalysisCommand(kind="similar", raw_text=raw_text, command="相似批次", batch=batch))

    if "配方" in raw_text or "原料" in raw_text:
        if not has_analysis and not mentions_feishu_data:
            return CommandParseResult(False)
        if not batch:
            return CommandParseResult(True, error="已命中配方/原料复盘分析，但缺少批次号。请使用：配方复盘 <批次号> 或 配方建议 <批次号>。")
        return CommandParseResult(True, value=AnalysisCommand(kind="recipe", raw_text=raw_text, command="配方复盘", batch=batch))

    if "成品" in raw_text and (has_analysis or mentions_feishu_data):
        tokens = [_clean(item) for item in re.split(r"\s+", raw_text) if _clean(item)]
        date_arg = ""
        target_parts: list[str] = []
        skip_words = {"请", "帮我", "帮忙", "分析", "成品", "数据", "飞书", "表格", "多维表", "Sheets", "sheet"}
        for token in tokens:
            if _DATE_RE.fullmatch(token):
                date_arg = token if not date_arg else date_arg
            elif token not in skip_words:
                target_parts.append(token)
        target = " ".join(target_parts).strip()
        return CommandParseResult(
            True,
            value=AnalysisCommand(kind="product", raw_text=raw_text, command="成品分析", target=target, date_arg=date_arg),
        )

    if any(word in raw_text for word in ("制程异常", "异常原因", "原因分析", "制程数据")) or (
        "异常" in raw_text and (has_analysis or mentions_feishu_data)
    ):
        if not batch:
            return CommandParseResult(True, error="已命中制程异常分析，但缺少批次号。请使用：异常分析 <批次号> <异常现象>。")
        abnormal = raw_text.replace(batch, " ")
        for word in ("请", "帮我", "帮忙", "分析", "制程", "异常", "原因", "飞书", "表格", "多维表", "数据"):
            abnormal = abnormal.replace(word, " ")
        abnormal = _clean(re.sub(r"\s+", " ", abnormal))
        return CommandParseResult(
            True,
            value=AnalysisCommand(kind="abnormal", raw_text=raw_text, command="异常分析", batch=batch, abnormal=abnormal),
        )

    if ("批次" in raw_text or batch) and (has_analysis or mentions_feishu_data):
        if not batch:
            return CommandParseResult(True, error="已命中批次分析，但缺少批次号。请使用：批次分析 <批次号>。")
        return CommandParseResult(True, value=AnalysisCommand(kind="batch", raw_text=raw_text, command="批次分析", batch=batch))

    if mentions_feishu_data and has_analysis:
        return CommandParseResult(
            True,
            error=(
                "已命中飞书数据分析插件，但参数不完整。\n"
                "可用格式：\n"
                "异常分析 <批次号> <异常现象>\n"
                "成品分析 <日期，可选> <型号或产线关键词>\n"
                "配方复盘 <批次号>\n"
                "批次分析 <批次号>"
            ),
        )

    return CommandParseResult(False)


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
        return _parse_natural_language_request(raw_text)

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

