from __future__ import annotations

import json
from typing import Any

from components.batch import field_to_text, normalize_batch, parse_float
from components.data_sources import FeishuBaseSource, FeishuSheetSource
from components.diagnosis import RuleHit, build_fallback_report, diagnose_process
from components.llm_client import LlmClient


DEFAULT_PROCESS_TABLES = {
    "feeding": ["A线投料汇总", "B线投料汇总", "C线投料汇总", "D线投料汇总", "E线投料汇总"],
    "wet_process": ["A线湿法汇总", "B线湿法汇总", "C线湿法汇总", "D线湿法汇总", "E线湿法汇总"],
    "spray": ["A线喷雾汇总", "B线喷雾汇总", "C线喷雾汇总", "D线喷雾汇总", "E线喷雾汇总"],
    "sintering": ["A线烧结汇总", "B线烧结汇总", "C线烧结汇总", "D线烧结汇总", "E线烧结汇总"],
    "crushing": ["A线粉碎压实汇总", "B线粉碎压实汇总", "C线粉碎压实汇总", "D线粉碎压实汇总", "E线粉碎压实汇总"],
    "kiln": ["窑炉批次进窑出窑表", "二期窑炉批次进窑出窑表"],
}


class AnalysisService:
    def __init__(
        self,
        *,
        base_source: FeishuBaseSource,
        sheet_source: FeishuSheetSource,
        llm_client: LlmClient | None = None,
    ) -> None:
        self.base_source = base_source
        self.sheet_source = sheet_source
        self.llm_client = llm_client

    @staticmethod
    def _json_config(raw: Any, fallback: Any) -> Any:
        if isinstance(raw, (dict, list)):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                return json.loads(raw)
            except Exception:
                return fallback
        return fallback

    @classmethod
    def resolve_process_tables(cls, raw: Any) -> dict[str, list[str]]:
        payload = cls._json_config(raw, DEFAULT_PROCESS_TABLES)
        if not isinstance(payload, dict):
            return DEFAULT_PROCESS_TABLES
        out: dict[str, list[str]] = {}
        for stage, value in payload.items():
            if isinstance(value, list):
                tables = [str(item).strip() for item in value if str(item).strip()]
            else:
                tables = [item.strip() for item in str(value).split(",") if item.strip()]
            if tables:
                out[str(stage)] = tables
        return out or DEFAULT_PROCESS_TABLES

    @staticmethod
    def _compact_fields(fields: dict[str, Any], max_fields: int) -> dict[str, Any]:
        ignore = {"原始文本", "OCR文本", "多行文本", "发送者ID", "会话ID", "源消息ID"}
        preferred_tokens = (
            "批次",
            "时间",
            "产线",
            "路由",
            "D10",
            "D50",
            "D90",
            "D99",
            "压实",
            "均值",
            "水分",
            "温度",
            "开度",
            "转速",
            "频率",
            "固含",
            "研磨",
            "窑炉",
            "窑位",
            "出窑",
            "进窑",
            "需补",
            "总量",
            "露点",
            "压力",
            "差压",
        )
        items: list[tuple[str, Any]] = []
        for key, value in fields.items():
            key_text = str(key).strip()
            if not key_text or key_text in ignore:
                continue
            value_text = field_to_text(value)
            if not value_text:
                continue
            score = 0 if any(token in key_text for token in preferred_tokens) else 1
            items.append((key_text, value_text if parse_float(value_text) is None else parse_float(value_text)))
            if score == 0 and len(items) >= max_fields:
                break
        if len(items) < max_fields:
            for key, value in fields.items():
                key_text = str(key).strip()
                if not key_text or key_text in ignore or any(k == key_text for k, _ in items):
                    continue
                value_text = field_to_text(value)
                if value_text:
                    items.append((key_text, value_text))
                if len(items) >= max_fields:
                    break
        return dict(items[:max_fields])

    async def build_batch_wide_table(
        self,
        *,
        app_token: str,
        spreadsheet_token: str,
        headers: dict[str, str],
        batch_text: str,
        process_tables_raw: Any,
        product_sheet_patterns: list[str],
        product_range: str,
        batch_field: str,
        message_time_field: str,
        scan_limit: int,
        max_stage_fields: int,
    ) -> dict[str, Any]:
        identity = normalize_batch(batch_text)
        tables_by_stage = self.resolve_process_tables(process_tables_raw)
        stages: dict[str, dict[str, Any]] = {}
        missing: list[str] = []

        for stage, table_names in tables_by_stage.items():
            latest: dict[str, Any] = {}
            for table_name in table_names:
                records = await self.base_source.query_records_by_batch(
                    app_token=app_token,
                    headers=headers,
                    table_name_or_id=table_name,
                    batch_core=identity.core,
                    batch_field=batch_field,
                    message_time_field=message_time_field,
                    scan_limit=scan_limit,
                )
                fields = self.base_source.latest_fields(records)
                if fields:
                    latest = fields
                    break
            if latest:
                stages[stage] = self._compact_fields(latest, max_stage_fields)
            else:
                missing.append(f"{stage} 未查询到记录")

        product: dict[str, Any] = {}
        if spreadsheet_token:
            product = await self.sheet_source.query_product_by_batch(
                spreadsheet_token=spreadsheet_token,
                headers=headers,
                sheet_patterns=product_sheet_patterns,
                cell_range=product_range,
                batch_core=identity.core,
                scan_sheet_limit=8,
            )
            if not product:
                missing.append("成品 Sheets 未查询到匹配批次")

        return {
            "identity": {
                "raw": identity.raw,
                "model": identity.model,
                "stage": identity.stage,
                "core": identity.core,
                "segment": identity.segment,
                "line": identity.line,
            },
            "stages": stages,
            "product": product,
            "missing_data": missing,
        }

    @staticmethod
    def _rule_hits_payload(hits: list[RuleHit]) -> list[dict[str, str]]:
        return [
            {"level": hit.level, "title": hit.title, "evidence": hit.evidence, "suggestion": hit.suggestion}
            for hit in hits
        ]

    async def analyze_batch(self, wide: dict[str, Any], *, abnormal: str = "", mode: str = "batch") -> str:
        hits = diagnose_process(wide, abnormal=abnormal)
        payload = {
            "task": mode,
            "abnormal": abnormal,
            "batch_wide_table": wide,
            "rule_hits": self._rule_hits_payload(hits),
            "output_contract": "按 事实 -> 判断 -> 建议措施 -> 待确认项 -> 风险边界 输出。",
        }
        fallback_title = "异常分析" if mode == "abnormal" else ("配方复盘" if mode == "recipe" else "批次分析")
        if self.llm_client and self.llm_client.enabled:
            try:
                return await self.llm_client.complete_report(payload)
            except Exception as exc:
                fallback = build_fallback_report(wide, hits, fallback_title)
                return f"{fallback}\n\nAI生成失败，已使用规则兜底：{exc}"
        return build_fallback_report(wide, hits, fallback_title)

    async def analyze_product(
        self,
        *,
        spreadsheet_token: str,
        headers: dict[str, str],
        target: str,
        date_arg: str,
        sheet_patterns: list[str],
        product_range: str,
        max_rows: int,
    ) -> str:
        summary = await self.sheet_source.summarize_product_target(
            spreadsheet_token=spreadsheet_token,
            headers=headers,
            target=target,
            date_arg=date_arg,
            sheet_patterns=sheet_patterns,
            cell_range=product_range,
            scan_sheet_limit=6,
            max_rows=max_rows,
        )
        payload = {
            "task": "product_analysis",
            "summary": summary,
            "output_contract": "输出数据完整性、趋势波动、规格关注、数据处理建议；不得修改原始数据。",
        }
        if self.llm_client and self.llm_client.enabled:
            try:
                return await self.llm_client.complete_report(payload)
            except Exception as exc:
                return self._product_fallback(summary) + f"\n\nAI生成失败，已使用统计兜底：{exc}"
        return self._product_fallback(summary)

    @staticmethod
    def _product_fallback(summary: dict[str, Any]) -> str:
        lines = ["成品数据分析", ""]
        sheets = summary.get("sheets", []) if isinstance(summary.get("sheets"), list) else []
        if not sheets:
            return "未读取到可分析的成品数据，请检查工作表名称、日期或读取范围。"
        for sheet in sheets:
            lines.append(f"【{sheet.get('sheet')}】")
            lines.append(f"- 纳入行数：{sheet.get('row_count', 0)}")
            lines.append(f"- 空白单元格计数：{sheet.get('missing_cells', 0)}")
            metrics = sheet.get("metrics", {}) if isinstance(sheet.get("metrics"), dict) else {}
            for name, stat in list(metrics.items())[:8]:
                lines.append(
                    f"- {name}：n={int(stat.get('count', 0))}，均值={stat.get('mean'):.4g}，"
                    f"范围={stat.get('min'):.4g}~{stat.get('max'):.4g}"
                )
        lines.append("")
        lines.append("建议：对边界值、缺失值、公式未计算结果先做标记和复核，不直接改写原始数据。")
        return "\n".join(lines).strip()

