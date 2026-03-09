from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import quote

from components.report_core import day_metrics


class FeishuSheetsSource:
    def __init__(self, api_call):
        self._api_call = api_call

    @staticmethod
    def _sheet_title_and_id(item: Any) -> tuple[str, str]:
        if not isinstance(item, dict):
            return "", ""

        candidates: list[dict[str, Any]] = [item]
        nested = item.get("sheet")
        if isinstance(nested, dict):
            candidates.append(nested)

        for obj in candidates:
            title = str(obj.get("title", "")).strip()
            sheet_id = str(obj.get("sheet_id", "") or obj.get("sheetId", "")).strip()
            if title and sheet_id:
                return title, sheet_id
        return "", ""

    async def list_sheet_title_id_pairs(self, spreadsheet_token: str, headers: dict[str, str]) -> list[tuple[str, str]]:
        endpoint = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query"
        data = await self._api_call("GET", endpoint, headers=headers)

        pairs: list[tuple[str, str]] = []
        items = data.get("sheets", [])
        if not isinstance(items, list):
            items = []
        for item in items:
            title, sheet_id = self._sheet_title_and_id(item)
            if title and sheet_id:
                pairs.append((title, sheet_id))
        return pairs

    async def list_sheet_titles(self, spreadsheet_token: str, headers: dict[str, str]) -> list[str]:
        pairs = await self.list_sheet_title_id_pairs(spreadsheet_token, headers)
        out: list[str] = []
        seen: set[str] = set()
        for title, _ in pairs:
            if title in seen:
                continue
            seen.add(title)
            out.append(title)
        return out

    async def get_sheet_values(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        cell_range: str,
        headers: dict[str, str],
    ) -> list[list[Any]]:
        range_expr = f"{sheet_id}!{cell_range}"
        encoded_range = quote(range_expr, safe="")
        endpoint = (
            f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{encoded_range}"
            "?valueRenderOption=UnformattedValue"
        )
        data = await self._api_call("GET", endpoint, headers=headers)

        value_range = data.get("valueRange")
        if not isinstance(value_range, dict):
            value_range = data.get("value_range") if isinstance(data.get("value_range"), dict) else {}

        values = value_range.get("values", []) if isinstance(value_range, dict) else []
        if not isinstance(values, list):
            return []

        out: list[list[Any]] = []
        for row in values:
            if isinstance(row, list):
                out.append(row)
            else:
                out.append([row])
        return out

    async def fetch_line_matrices(
        self,
        spreadsheet_token: str,
        headers: dict[str, str],
        target_sheet_names: list[str],
        cell_range: str,
    ) -> tuple[dict[str, list[list[Any]]], list[str], list[str]]:
        pairs = await self.list_sheet_title_id_pairs(spreadsheet_token, headers)

        title_to_id: dict[str, str] = {}
        available_titles: list[str] = []
        for title, sheet_id in pairs:
            if title in title_to_id:
                continue
            title_to_id[title] = sheet_id
            available_titles.append(title)

        wanted = target_sheet_names if target_sheet_names else available_titles
        available_set = set(title_to_id.keys())
        missing = [name for name in wanted if name not in available_set]
        valid_targets = [name for name in wanted if name in available_set]

        matrices: dict[str, list[list[Any]]] = {}
        for sheet_title in valid_targets:
            sheet_id = title_to_id.get(sheet_title, "")
            if not sheet_id:
                continue
            matrices[sheet_title] = await self.get_sheet_values(
                spreadsheet_token=spreadsheet_token,
                sheet_id=sheet_id,
                cell_range=cell_range,
                headers=headers,
            )
        return matrices, available_titles, missing

    @staticmethod
    def field_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and math.isnan(value):
            return ""
        if isinstance(value, str):
            text = value.strip()
        else:
            text = str(value).strip()
        return "" if text.lower() == "nan" else text

    @staticmethod
    def normalize_key(text: str) -> str:
        raw = FeishuSheetsSource.field_to_text(text).lower()
        return re.sub(r"[\s_\-()（）【】\[\]/.%+]+", "", raw)

    @staticmethod
    def normalize_batch_core(batch_text: str) -> str:
        normalized = re.sub(r"\s*-\s*", "-", FeishuSheetsSource.field_to_text(batch_text).upper())
        if not normalized:
            return ""
        match = re.search(r"(D[ABC]\d{4}-\d+)", normalized)
        if match:
            return str(match.group(1))
        match = re.search(r"([ABC]\d{4}-\d+)", normalized)
        if match:
            return f"D{match.group(1)}"
        return normalized

    @staticmethod
    def _format_number(value: Any) -> str:
        text = FeishuSheetsSource.field_to_text(value)
        if not text:
            return ""
        try:
            number = float(text)
        except Exception:
            return text
        return f"{number:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def _infer_prefer_model(batch_core: str) -> str:
        normalized = FeishuSheetsSource.normalize_batch_core(batch_core)
        if normalized.startswith("DA"):
            return "S18"
        if normalized.startswith("DB"):
            return "S006"
        if normalized.startswith("DC"):
            return "C"
        return ""

    @classmethod
    def _order_sheet_titles(cls, titles: list[str], batch_core: str, prefer_line: str, prefer_model: str) -> list[str]:
        model_hint = (prefer_model or cls._infer_prefer_model(batch_core)).upper()
        line_hint = prefer_line.upper().strip()

        def sort_key(item: tuple[int, str]) -> tuple[int, int, int]:
            index, title = item
            title_upper = title.upper()
            model_rank = 0 if model_hint and model_hint in title_upper else 1
            line_rank = 0 if line_hint and f"{line_hint}线" in title else 1
            return (model_rank, line_rank, index)

        return [title for _, title in sorted(enumerate(titles), key=sort_key)]

    @classmethod
    def _find_best_column(cls, columns: list[str], aliases: list[str]) -> str:
        normalized_columns = [(column, cls.normalize_key(column)) for column in columns]
        normalized_aliases = [(alias, cls.normalize_key(alias)) for alias in aliases if cls.normalize_key(alias)]

        for _alias_raw, alias_key in normalized_aliases:
            for column, column_key in normalized_columns:
                if column_key == alias_key:
                    return column

        for _alias_raw, alias_key in normalized_aliases:
            for column, column_key in normalized_columns:
                if alias_key and column_key and (alias_key in column_key or column_key in alias_key):
                    return column

        return ""

    @classmethod
    def _format_recipe_field_value(cls, logical_field: str, column_name: str, value: Any, placeholder: str) -> str:
        raw = cls.field_to_text(value)
        if not raw:
            return placeholder

        normalized_column = cls.normalize_key(column_name)
        if logical_field == "酸量" and ("百分含量" in column_name or "百分含量" in normalized_column):
            try:
                number = float(raw)
            except Exception:
                return raw if raw.endswith("%") else raw
            if number <= 1:
                number *= 100
            return f"{number:.3f}".rstrip("0").rstrip(".") + "%"

        formatted = cls._format_number(raw)
        return formatted or placeholder

    @classmethod
    def _extract_recipe_from_row(
        cls,
        row_map: dict[str, Any],
        field_aliases: dict[str, list[str]],
        placeholder: str,
    ) -> dict[str, str]:
        result_fields = ("铁磷比", "锂量", "酸量", "钛量", "糖量", "peg量", "窑炉温度")
        result: dict[str, str] = {field: placeholder for field in result_fields}
        columns = list(row_map.keys())

        for field in result_fields:
            aliases = field_aliases.get(field, [field])
            matched_column = cls._find_best_column(columns, aliases)
            if not matched_column:
                continue
            result[field] = cls._format_recipe_field_value(
                logical_field=field,
                column_name=matched_column,
                value=row_map.get(matched_column),
                placeholder=placeholder,
            )

        return result

    async def query_recipe_by_batch(
        self,
        spreadsheet_token: str,
        headers: dict[str, str],
        target_sheet_names: list[str],
        cell_range: str,
        batch_core: str,
        prefer_line: str,
        field_aliases: dict[str, list[str]],
        placeholder: str = "--",
        prefer_model: str = "",
    ) -> dict[str, str]:
        result_fields = ("铁磷比", "锂量", "酸量", "钛量", "糖量", "peg量", "窑炉温度")
        result: dict[str, str] = {field: placeholder for field in result_fields}

        normalized_batch = self.normalize_batch_core(batch_core)
        if not normalized_batch:
            return result

        matrices, available_titles, _ = await self.fetch_line_matrices(
            spreadsheet_token=spreadsheet_token,
            headers=headers,
            target_sheet_names=target_sheet_names,
            cell_range=cell_range,
        )
        if not matrices and target_sheet_names:
            matrices, available_titles, _ = await self.fetch_line_matrices(
                spreadsheet_token=spreadsheet_token,
                headers=headers,
                target_sheet_names=[],
                cell_range=cell_range,
            )

        all_titles = [title for title in available_titles if title in matrices]
        search_titles = self._order_sheet_titles(
            titles=all_titles,
            batch_core=normalized_batch,
            prefer_line=prefer_line,
            prefer_model=prefer_model,
        )

        batch_aliases = field_aliases.get("批次号", ["批次号", "批次", "批号", "出窑批次"])
        for sheet_title in search_titles:
            matrix = matrices.get(sheet_title, [])
            if not matrix:
                continue

            try:
                table = day_metrics.load_sheet_table_from_matrix(matrix)
            except Exception:
                continue
            if table.empty:
                continue

            batch_column = self._find_best_column(list(table.columns), batch_aliases)
            if not batch_column:
                continue

            for _, row in table.iloc[::-1].iterrows():
                row_batch = self.normalize_batch_core(row.get(batch_column))
                if not row_batch or row_batch != normalized_batch:
                    continue
                row_map = {str(column): row.get(column) for column in table.columns}
                return self._extract_recipe_from_row(row_map, field_aliases=field_aliases, placeholder=placeholder)

        return result
