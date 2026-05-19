from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from components.batch import field_to_text, normalize_batch, normalize_key, parse_float


class FeishuBaseSource:
    def __init__(self, api_call):
        self._api_call = api_call
        self._table_cache: dict[str, dict[str, str]] = {}

    @staticmethod
    def split_csv(raw: str) -> list[str]:
        parts = re.split(r"[,\n;，；]+", raw or "")
        return [item.strip() for item in parts if item.strip()]

    async def list_tables(self, app_token: str, headers: dict[str, str]) -> dict[str, str]:
        cached = self._table_cache.get(app_token)
        if cached is not None:
            return cached

        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
        page_token = ""
        result: dict[str, str] = {}
        while True:
            params: dict[str, Any] = {"page_size": 200}
            if page_token:
                params["page_token"] = page_token
            data = await self._api_call("GET", endpoint, headers=headers, params=params)
            for item in data.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                table_id = str(item.get("table_id", "")).strip()
                if name and table_id:
                    result[name] = table_id
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        self._table_cache[app_token] = result
        return result

    async def resolve_table_id(self, app_token: str, headers: dict[str, str], table_name_or_id: str) -> str:
        raw = str(table_name_or_id or "").strip()
        if not raw:
            return ""
        if raw.startswith("tbl"):
            return raw
        tables = await self.list_tables(app_token, headers)
        return tables.get(raw, "")

    async def query_records_by_batch(
        self,
        *,
        app_token: str,
        headers: dict[str, str],
        table_name_or_id: str,
        batch_core: str,
        batch_field: str,
        message_time_field: str,
        scan_limit: int,
    ) -> list[dict[str, Any]]:
        table_id = await self.resolve_table_id(app_token, headers, table_name_or_id)
        if not table_id:
            return []
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        records: list[dict[str, Any]] = []
        page_token = ""
        scanned = 0
        while scanned < scan_limit:
            page_size = min(200, scan_limit - scanned)
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            payload = {
                "automatic_fields": False,
                "filter": {
                    "conjunction": "and",
                    "conditions": [{"field_name": batch_field, "operator": "contains", "value": [batch_core]}],
                },
                "sort": [{"field_name": message_time_field, "desc": True}],
            }
            try:
                data = await self._api_call("POST", endpoint, headers=headers, payload=payload, params=params)
            except Exception:
                return await self._list_records_fallback(
                    app_token=app_token,
                    headers=headers,
                    table_id=table_id,
                    batch_core=batch_core,
                    batch_field=batch_field,
                    scan_limit=scan_limit,
                )
            items = data.get("items", []) or []
            for item in items:
                if isinstance(item, dict):
                    fields = item.get("fields", {})
                    if isinstance(fields, dict) and normalize_batch(fields.get(batch_field)).core == batch_core:
                        records.append(item)
            scanned += len(items)
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        records.sort(
            key=lambda item: field_to_text((item.get("fields") or {}).get(message_time_field)),
            reverse=True,
        )
        return records

    async def _list_records_fallback(
        self,
        *,
        app_token: str,
        headers: dict[str, str],
        table_id: str,
        batch_core: str,
        batch_field: str,
        scan_limit: int,
    ) -> list[dict[str, Any]]:
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        records: list[dict[str, Any]] = []
        page_token = ""
        scanned = 0
        while scanned < scan_limit:
            page_size = min(200, scan_limit - scanned)
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            data = await self._api_call("GET", endpoint, headers=headers, params=params)
            items = data.get("items", []) or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                fields = item.get("fields", {})
                if isinstance(fields, dict) and normalize_batch(fields.get(batch_field)).core == batch_core:
                    records.append(item)
            scanned += len(items)
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return records

    @staticmethod
    def latest_fields(records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            return {}
        fields = records[0].get("fields", {})
        return dict(fields) if isinstance(fields, dict) else {}


class FeishuSheetSource:
    def __init__(self, api_call):
        self._api_call = api_call
        self._sheet_cache: dict[str, list[tuple[str, str]]] = {}

    async def list_sheet_title_id_pairs(self, spreadsheet_token: str, headers: dict[str, str]) -> list[tuple[str, str]]:
        cached = self._sheet_cache.get(spreadsheet_token)
        if cached is not None:
            return cached
        endpoint = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query"
        data = await self._api_call("GET", endpoint, headers=headers)
        pairs: list[tuple[str, str]] = []
        for item in data.get("sheets", []) or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            sheet_id = str(item.get("sheet_id", "") or item.get("sheetId", "")).strip()
            if title and sheet_id:
                pairs.append((title, sheet_id))
        self._sheet_cache[spreadsheet_token] = pairs
        return pairs

    async def get_values(
        self,
        *,
        spreadsheet_token: str,
        headers: dict[str, str],
        sheet_id: str,
        cell_range: str,
        value_render_option: str = "FormattedValue",
    ) -> list[list[Any]]:
        range_expr = f"{sheet_id}!{cell_range}"
        endpoint = (
            f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/"
            f"{quote(range_expr, safe='')}?valueRenderOption={quote(value_render_option, safe='')}"
        )
        data = await self._api_call("GET", endpoint, headers=headers)
        value_range = data.get("valueRange") if isinstance(data.get("valueRange"), dict) else {}
        values = value_range.get("values", []) if isinstance(value_range, dict) else []
        return [row if isinstance(row, list) else [row] for row in values if isinstance(row, list)]

    @staticmethod
    def _make_unique_columns(header_rows: list[list[Any]]) -> list[str]:
        max_len = max((len(row) for row in header_rows), default=0)
        filled: list[list[str]] = []
        for row in header_rows:
            out: list[str] = []
            last = ""
            for idx in range(max_len):
                text = field_to_text(row[idx] if idx < len(row) else "")
                if text:
                    last = text
                out.append(text or last)
            filled.append(out)

        columns: list[str] = []
        seen: dict[str, int] = {}
        for idx in range(max_len):
            parts: list[str] = []
            for row in filled:
                text = row[idx].strip()
                if text and (not parts or parts[-1] != text):
                    parts.append(text)
            name = "_".join(parts).strip("_") or f"COL{idx}"
            count = seen.get(name, 0) + 1
            seen[name] = count
            columns.append(name if count == 1 else f"{name}__{count}")
        return columns

    @classmethod
    def matrix_to_rows(cls, values: list[list[Any]]) -> list[dict[str, Any]]:
        if not values:
            return []
        header_idx = 0
        for idx, row in enumerate(values[:20]):
            if any("批次" in field_to_text(cell) for cell in row):
                header_idx = idx
                break
        data_start = header_idx + 1
        for idx in range(header_idx + 1, min(len(values), header_idx + 8)):
            row_text = "".join(field_to_text(cell) for cell in values[idx])
            if re.search(r"D[A-Z]?\d{4}-\d{3,}", row_text) or re.search(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", row_text):
                data_start = idx
                break
        columns = cls._make_unique_columns(values[header_idx:data_start])
        rows: list[dict[str, Any]] = []
        for raw_row in values[data_start:]:
            if not any(field_to_text(cell) for cell in raw_row):
                continue
            row_map: dict[str, Any] = {}
            for idx, column in enumerate(columns):
                row_map[column] = raw_row[idx] if idx < len(raw_row) else ""
            rows.append(row_map)
        return rows

    @staticmethod
    def find_column(columns: list[str], aliases: list[str]) -> str:
        pairs = [(column, normalize_key(column)) for column in columns]
        alias_keys = [normalize_key(alias) for alias in aliases if normalize_key(alias)]
        for alias in alias_keys:
            for column, key in pairs:
                if key == alias:
                    return column
        for alias in alias_keys:
            for column, key in pairs:
                if alias and key and (alias in key or key in alias):
                    return column
        return ""

    async def query_product_by_batch(
        self,
        *,
        spreadsheet_token: str,
        headers: dict[str, str],
        sheet_patterns: list[str],
        cell_range: str,
        batch_core: str,
        scan_sheet_limit: int,
    ) -> dict[str, Any]:
        pairs = await self.list_sheet_title_id_pairs(spreadsheet_token, headers)
        selected: list[tuple[str, str]] = []
        for title, sheet_id in pairs:
            if not sheet_patterns or any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in sheet_patterns):
                selected.append((title, sheet_id))
            if len(selected) >= scan_sheet_limit:
                break

        for title, sheet_id in selected:
            values = await self.get_values(
                spreadsheet_token=spreadsheet_token,
                headers=headers,
                sheet_id=sheet_id,
                cell_range=cell_range,
            )
            rows = self.matrix_to_rows(values)
            if not rows:
                continue
            columns = list(rows[0].keys())
            batch_col = self.find_column(columns, ["批次", "批次号", "供应商内部批次号"])
            if not batch_col:
                continue
            for row in reversed(rows):
                if normalize_batch(row.get(batch_col)).core == batch_core:
                    return {"sheet": title, "row": row}
        return {}

    async def summarize_product_target(
        self,
        *,
        spreadsheet_token: str,
        headers: dict[str, str],
        target: str,
        date_arg: str,
        sheet_patterns: list[str],
        cell_range: str,
        scan_sheet_limit: int,
        max_rows: int,
    ) -> dict[str, Any]:
        pairs = await self.list_sheet_title_id_pairs(spreadsheet_token, headers)
        target_key = normalize_key(target)
        selected: list[tuple[str, str]] = []
        for title, sheet_id in pairs:
            if target_key and target_key not in normalize_key(title):
                continue
            if sheet_patterns and not any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in sheet_patterns):
                continue
            selected.append((title, sheet_id))
            if len(selected) >= scan_sheet_limit:
                break
        if not selected and target:
            selected = [(title, sid) for title, sid in pairs if target_key in normalize_key(title)][:scan_sheet_limit]
        if not selected:
            selected = [(title, sid) for title, sid in pairs if not sheet_patterns or any(re.search(p, title, flags=re.IGNORECASE) for p in sheet_patterns)][:scan_sheet_limit]

        summaries: list[dict[str, Any]] = []
        for title, sheet_id in selected:
            values = await self.get_values(
                spreadsheet_token=spreadsheet_token,
                headers=headers,
                sheet_id=sheet_id,
                cell_range=cell_range,
            )
            rows = self.matrix_to_rows(values)
            if date_arg:
                rows = [row for row in rows if any(date_arg.replace("-", ".") in field_to_text(v) or date_arg in field_to_text(v) for v in row.values())]
            rows = rows[-max_rows:]
            numeric: dict[str, list[float]] = {}
            missing_count = 0
            for row in rows:
                for key, value in row.items():
                    text = field_to_text(value)
                    if not text:
                        missing_count += 1
                        continue
                    num = parse_float(value)
                    if num is not None and not key.upper().startswith("COL"):
                        numeric.setdefault(key, []).append(num)
            metric_summary: dict[str, dict[str, float]] = {}
            for key, values_num in numeric.items():
                if len(values_num) < 2:
                    continue
                metric_summary[key] = {
                    "count": float(len(values_num)),
                    "min": min(values_num),
                    "max": max(values_num),
                    "mean": sum(values_num) / len(values_num),
                }
            summaries.append(
                {
                    "sheet": title,
                    "row_count": len(rows),
                    "missing_cells": missing_count,
                    "metrics": dict(list(metric_summary.items())[:20]),
                    "latest_rows": rows[-3:],
                }
            )
        return {"target": target, "date": date_arg, "sheets": summaries}

