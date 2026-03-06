from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote


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
        endpoint = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{encoded_range}"
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
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def normalize_key(text: str) -> str:
        raw = FeishuSheetsSource.field_to_text(text).lower()
        return re.sub(r"[\s_\-()（）【】\[\]/]+", "", raw)

    @staticmethod
    def normalize_batch_core(batch_text: str) -> str:
        normalized = re.sub(r"\s*-\s*", "-", FeishuSheetsSource.field_to_text(batch_text).upper())
        if not normalized:
            return ""
        match = re.search(r"(D[AB]\d{4}-\d+)", normalized)
        if match:
            return str(match.group(1))
        match = re.search(r"([AB]\d{4}-\d+)", normalized)
        if match:
            return f"D{match.group(1)}"
        return normalized

    @staticmethod
    def _build_field_index_map(header_row: list[Any], alias_map: dict[str, list[str]]) -> dict[str, int]:
        normalized_headers = [FeishuSheetsSource.normalize_key(str(item)) for item in header_row]
        index_map: dict[str, int] = {}

        for logical_field, aliases in alias_map.items():
            normalized_aliases = [FeishuSheetsSource.normalize_key(alias) for alias in aliases if alias]
            matched_index = -1

            for idx, header in enumerate(normalized_headers):
                if header and header in normalized_aliases:
                    matched_index = idx
                    break

            if matched_index < 0:
                for idx, header in enumerate(normalized_headers):
                    if not header:
                        continue
                    if any(alias and (alias in header or header in alias) for alias in normalized_aliases):
                        matched_index = idx
                        break

            if matched_index >= 0:
                index_map[logical_field] = matched_index

        return index_map

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
        preferred_titles: list[str] = []
        if prefer_line in {"A", "B"}:
            preferred_tag = f"{prefer_line}线"
            preferred_titles = [title for title in all_titles if preferred_tag in title]
        search_titles = preferred_titles + [title for title in all_titles if title not in preferred_titles]

        alias_map = dict(field_aliases)
        alias_map["批次号"] = field_aliases.get("批次号", ["批次号", "批次", "批号", "出窑批次"])

        for sheet_title in search_titles:
            matrix = matrices.get(sheet_title, [])
            if not matrix:
                continue
            header = matrix[0]
            if not isinstance(header, list):
                continue

            index_map = self._build_field_index_map(header, alias_map)
            batch_idx = index_map.get("批次号", -1)
            if batch_idx < 0:
                continue

            for row in reversed(matrix[1:]):
                if not isinstance(row, list):
                    continue
                if batch_idx >= len(row):
                    continue
                row_batch = self.normalize_batch_core(self.field_to_text(row[batch_idx]))
                if not row_batch or row_batch != normalized_batch:
                    continue

                for field in result_fields:
                    col_idx = index_map.get(field, -1)
                    if col_idx < 0 or col_idx >= len(row):
                        result[field] = placeholder
                    else:
                        value = self.field_to_text(row[col_idx])
                        result[field] = value if value else placeholder
                return result

        return result
