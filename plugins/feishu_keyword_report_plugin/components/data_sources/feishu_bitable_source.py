from __future__ import annotations

import datetime
import json
import re
from typing import Any


class FeishuBitableSource:
    def __init__(self, api_call):
        self._api_call = api_call

    @staticmethod
    def split_csv(raw: str) -> list[str]:
        if not raw:
            return []
        parts = re.split(r"[,\n;，；]+", raw)
        return [item.strip() for item in parts if item.strip()]

    @staticmethod
    def dedupe_keep_order(items: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    @staticmethod
    def field_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value).strip()
        return str(value).strip()

    @staticmethod
    def normalize_batch_core(batch_text: str) -> str:
        normalized = re.sub(r"\s*-\s*", "-", FeishuBitableSource.field_to_text(batch_text).upper())
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
    def _normalize_segment(segment: str) -> str:
        return FeishuBitableSource.field_to_text(segment).upper()

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        text = FeishuBitableSource.field_to_text(value).replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None

    @staticmethod
    def _format_float(value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def is_sintering_record(fields: dict[str, Any], route_field: str, batch_field: str) -> bool:
        route = FeishuBitableSource.field_to_text(fields.get(route_field)).lower()
        batch = FeishuBitableSource.field_to_text(fields.get(batch_field)).upper()
        return ("sintering" in route) or ("-SC-" in batch)

    @staticmethod
    def infer_line(fields: dict[str, Any], route_field: str, batch_field: str) -> str:
        route = FeishuBitableSource.field_to_text(fields.get(route_field)).lower()
        if route.endswith(".a"):
            return "A"
        if route.endswith(".b"):
            return "B"

        batch = FeishuBitableSource.field_to_text(fields.get(batch_field)).upper()
        if "-DA" in batch:
            return "A"
        if "-DB" in batch:
            return "B"
        return ""

    @staticmethod
    def time_to_sort_key(raw: str) -> float:
        text = raw.strip()
        if not text:
            return 0.0
        try:
            value = float(text)
            if value > 1e12:
                value = value / 1000.0
            return value
        except Exception:
            pass

        iso = text.replace("Z", "+00:00")
        try:
            dt_value = datetime.datetime.fromisoformat(iso)
            if dt_value.tzinfo is None:
                dt_value = dt_value.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
            return dt_value.timestamp()
        except Exception:
            pass

        fmts = ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S")
        for fmt in fmts:
            try:
                dt_value = datetime.datetime.strptime(text, fmt)
                dt_value = dt_value.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
                return dt_value.timestamp()
            except Exception:
                continue
        return 0.0

    async def list_all_tables(self, app_token: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        if not app_token:
            return []
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"

        page_token = ""
        tables: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {"page_size": 200}
            if page_token:
                params["page_token"] = page_token
            data = await self._api_call("GET", endpoint, headers=headers, params=params)
            items = data.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        tables.append(item)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return tables

    async def resolve_table_ids(
        self,
        app_token: str,
        headers: dict[str, str],
        explicit_ids_raw: str,
        table_names_raw: str,
    ) -> list[str]:
        explicit_ids = self.split_csv(explicit_ids_raw)
        if explicit_ids:
            return self.dedupe_keep_order(explicit_ids)

        target_names = self.split_csv(table_names_raw)
        if not target_names:
            return []

        tables = await self.list_all_tables(app_token, headers)
        name_to_id: dict[str, str] = {}
        for table in tables:
            name = str(table.get("name", "")).strip()
            table_id = str(table.get("table_id", "")).strip()
            if name and table_id:
                name_to_id[name] = table_id

        resolved: list[str] = []
        for name in target_names:
            table_id = name_to_id.get(name, "")
            if table_id:
                resolved.append(table_id)
        return self.dedupe_keep_order(resolved)

    async def list_table_records(
        self,
        app_token: str,
        headers: dict[str, str],
        table_id: str,
        scan_limit: int,
    ) -> list[dict[str, Any]]:
        if not app_token or not table_id:
            return []

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

            items = data.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        records.append(item)
                scanned += len(items)

            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return records

    @staticmethod
    def build_detail_text(fields: dict[str, Any], detail_max_fields: int) -> str:
        ignore_keys = {"消息时间", "原始文本", "OCR文本", "路由", "批次号", "业务类型", "产线"}

        def _value_text(v: Any) -> str:
            if isinstance(v, float):
                return f"{v:.3f}".rstrip("0").rstrip(".")
            return FeishuBitableSource.field_to_text(v)

        avg_items = [(k, v) for k, v in fields.items() if "均值" in str(k)]
        if not avg_items:
            avg_items = [(k, v) for k, v in fields.items() if ("压实" in str(k) and str(k) not in ignore_keys)]
        if not avg_items:
            avg_items = [(k, v) for k, v in fields.items() if str(k) not in ignore_keys]

        parts: list[str] = []
        for key, value in avg_items:
            k = str(key).strip()
            if not k:
                continue
            vt = _value_text(value)
            if not vt:
                continue
            parts.append(f"{k}={vt}")
            if len(parts) >= detail_max_fields:
                break
        return ", ".join(parts)

    @staticmethod
    def build_reply_text(
        latest_by_line: dict[str, dict[str, Any]],
        batch_field: str,
        message_time_field: str,
        detail_max_fields: int,
        no_data_text: str,
        title_text: str = "当前出窑批次及烧结压实：",
    ) -> str:
        if not latest_by_line:
            return no_data_text

        lines = [title_text]
        for line_code in ("A", "B"):
            item = latest_by_line.get(line_code)
            if item is None:
                lines.append(f"{line_code}线：暂无数据")
                continue
            fields = item.get("fields", {})
            if not isinstance(fields, dict):
                lines.append(f"{line_code}线：暂无数据")
                continue

            batch_id = FeishuBitableSource.field_to_text(fields.get(batch_field))
            msg_time = FeishuBitableSource.field_to_text(fields.get(message_time_field))
            detail = FeishuBitableSource.build_detail_text(fields, detail_max_fields)

            line_text = f"{line_code}线：{batch_id or '暂无批次'}"
            if detail:
                line_text = f"{line_text} | {detail}"
            if msg_time:
                line_text = f"{line_text} | 时间 {msg_time}"
            lines.append(line_text)
        return "\n".join(lines)

    @staticmethod
    def _slot_sort_key(slot: str) -> tuple[int, str]:
        if slot.isdigit():
            return int(slot), slot
        return 9999, slot

    def _extract_kiln_candidate(
        self,
        fields: dict[str, Any],
        segment: str,
        batch_field: str,
    ) -> dict[str, Any] | None:
        segment_value = self._normalize_segment(self.field_to_text(fields.get("窑炉段")))
        target_segment = self._normalize_segment(segment)
        if not target_segment or segment_value != target_segment:
            return None

        batch_raw = self.field_to_text(fields.get(batch_field))
        batch_core = self.normalize_batch_core(batch_raw)
        if not batch_core:
            return None

        start_slot_sorts: dict[str, float] = {}
        end_slot_sorts: dict[str, float] = {}

        for key, value in fields.items():
            key_text = self.field_to_text(key)
            value_text = self.field_to_text(value)
            if not key_text or not value_text:
                continue

            start_match = re.match(r"^\s*(\d+)\s*号出窑开始时间\s*$", key_text)
            if start_match:
                slot = str(start_match.group(1))
                start_slot_sorts[slot] = self.time_to_sort_key(value_text)
                continue

            end_match = re.match(r"^\s*(\d+)\s*号出窑结束时间\s*$", key_text)
            if end_match:
                slot = str(end_match.group(1))
                end_slot_sorts[slot] = self.time_to_sort_key(value_text)

        slot_value = self.field_to_text(fields.get("窑位"))
        start_single = self.field_to_text(fields.get("出窑开始时间"))
        end_single = self.field_to_text(fields.get("出窑结束时间"))
        if slot_value and start_single:
            start_slot_sorts[slot_value] = self.time_to_sort_key(start_single)
        if slot_value and end_single:
            end_slot_sorts[slot_value] = self.time_to_sort_key(end_single)

        return {
            "batch_raw": batch_raw,
            "batch_core": batch_core,
            "start_slot_sorts": start_slot_sorts,
            "end_slot_sorts": end_slot_sorts,
        }

    async def query_latest_kiln_batch_by_segment(
        self,
        app_token: str,
        headers: dict[str, str],
        segment: str,
        table_ids_raw: str,
        table_names_raw: str,
        batch_field: str,
        scan_limit: int,
    ) -> dict[str, Any] | None:
        table_ids = await self.resolve_table_ids(
            app_token=app_token,
            headers=headers,
            explicit_ids_raw=table_ids_raw,
            table_names_raw=table_names_raw,
        )
        if not table_ids:
            return None

        by_batch: dict[str, dict[str, Any]] = {}
        for table_id in table_ids:
            records = await self.list_table_records(
                app_token=app_token,
                headers=headers,
                table_id=table_id,
                scan_limit=scan_limit,
            )
            for item in records:
                fields = item.get("fields", {})
                if not isinstance(fields, dict):
                    continue
                candidate = self._extract_kiln_candidate(fields, segment=segment, batch_field=batch_field)
                if candidate is None:
                    continue

                batch_core = str(candidate.get("batch_core", "")).strip()
                if not batch_core:
                    continue

                agg = by_batch.get(batch_core)
                if agg is None:
                    agg = {
                        "batch_raw": str(candidate.get("batch_raw", "")).strip(),
                        "batch_core": batch_core,
                        "start_slot_sorts": {},
                        "end_slot_sorts": {},
                    }
                    by_batch[batch_core] = agg
                elif not agg.get("batch_raw"):
                    agg["batch_raw"] = str(candidate.get("batch_raw", "")).strip()

                start_map = candidate.get("start_slot_sorts", {})
                if isinstance(start_map, dict):
                    for slot, sort_key in start_map.items():
                        slot_text = self.field_to_text(slot)
                        if not slot_text:
                            continue
                        sort_value = float(sort_key)
                        old = agg["start_slot_sorts"].get(slot_text)
                        if old is None or sort_value >= float(old):
                            agg["start_slot_sorts"][slot_text] = sort_value

                end_map = candidate.get("end_slot_sorts", {})
                if isinstance(end_map, dict):
                    for slot, sort_key in end_map.items():
                        slot_text = self.field_to_text(slot)
                        if not slot_text:
                            continue
                        sort_value = float(sort_key)
                        old = agg["end_slot_sorts"].get(slot_text)
                        if old is None or sort_value >= float(old):
                            agg["end_slot_sorts"][slot_text] = sort_value

        if not by_batch:
            return None

        def _pick_best(prefer_start: bool) -> dict[str, Any] | None:
            best: dict[str, Any] | None = None
            for item in by_batch.values():
                slot_map = item["start_slot_sorts"] if prefer_start else item["end_slot_sorts"]
                if not slot_map:
                    continue
                time_sort = max(float(x) for x in slot_map.values())
                if best is None or time_sort >= float(best.get("time_sort", 0.0)):
                    slots = sorted(slot_map.keys(), key=self._slot_sort_key)
                    best = {
                        "batch_raw": item.get("batch_raw", ""),
                        "batch_core": item.get("batch_core", ""),
                        "slots": slots,
                        "time_sort": time_sort,
                    }
            return best

        return _pick_best(prefer_start=True) or _pick_best(prefer_start=False)

    def _extract_sintering_details_for_segment(
        self,
        fields: dict[str, Any],
        segment: str,
    ) -> tuple[dict[str, dict[str, Any]], float | None]:
        target_segment = self._normalize_segment(segment)
        details: dict[str, dict[str, Any]] = {}
        avg_value: float | None = None

        for key, value in fields.items():
            key_text = self.field_to_text(key)
            if not key_text:
                continue
            numeric_value = self._parse_float(value)
            if numeric_value is None:
                continue

            key_upper = key_text.upper()
            if key_upper == f"{target_segment}-均值":
                avg_value = numeric_value
                continue

            full_match = re.search(
                rf"([A-Z0-9]+-SC-D[AB]\d{{4}}-\d+-{target_segment}-(\d+)-(\d+)\s*MIN)",
                key_upper,
            )
            if full_match:
                slot = str(full_match.group(2))
                label = str(full_match.group(1)).replace("MIN", "min")
                priority = 3
            else:
                with_min_match = re.match(rf"^{target_segment}-(\d+)-(\d+)\s*MIN$", key_upper)
                if with_min_match:
                    slot = str(with_min_match.group(1))
                    label = f"{target_segment}-{slot}-{with_min_match.group(2)}min"
                    priority = 2
                else:
                    short_match = re.match(rf"^{target_segment}-(\d+)$", key_upper)
                    if not short_match:
                        continue
                    slot = str(short_match.group(1))
                    label = f"{target_segment}-{slot}"
                    priority = 1

            existing = details.get(slot)
            if existing is None or priority > int(existing.get("priority", 0)):
                details[slot] = {
                    "label": label,
                    "value": numeric_value,
                    "priority": priority,
                }

        return details, avg_value

    async def query_sintering_detail_by_batch_segment(
        self,
        app_token: str,
        headers: dict[str, str],
        batch_core: str,
        segment: str,
        table_ids_raw: str,
        table_names_raw: str,
        route_field: str,
        batch_field: str,
        message_time_field: str,
        scan_limit: int,
    ) -> dict[str, Any]:
        result = {"details": [], "avg": None}
        normalized_target = self.normalize_batch_core(batch_core)
        if not normalized_target:
            return result

        table_ids = await self.resolve_table_ids(
            app_token=app_token,
            headers=headers,
            explicit_ids_raw=table_ids_raw,
            table_names_raw=table_names_raw,
        )
        if not table_ids:
            return result

        best: dict[str, Any] | None = None
        for table_id in table_ids:
            records = await self.list_table_records(
                app_token=app_token,
                headers=headers,
                table_id=table_id,
                scan_limit=scan_limit,
            )
            for item in records:
                fields = item.get("fields", {})
                if not isinstance(fields, dict):
                    continue
                if not self.is_sintering_record(fields, route_field=route_field, batch_field=batch_field):
                    continue

                row_batch = self.field_to_text(fields.get(batch_field))
                row_batch_core = self.normalize_batch_core(row_batch)
                if not row_batch_core or row_batch_core != normalized_target:
                    continue

                details_map, avg_fallback = self._extract_sintering_details_for_segment(fields, segment=segment)
                if not details_map and avg_fallback is None:
                    continue

                sort_key = self.time_to_sort_key(self.field_to_text(fields.get(message_time_field)))
                if best is None or sort_key >= float(best.get("sort", 0.0)):
                    best = {
                        "sort": sort_key,
                        "details_map": details_map,
                        "avg_fallback": avg_fallback,
                    }

        if best is None:
            return result

        details_map = best.get("details_map", {})
        if not isinstance(details_map, dict):
            details_map = {}

        detail_lines: list[str] = []
        numeric_values: list[float] = []
        for slot in sorted(details_map.keys(), key=self._slot_sort_key):
            item = details_map.get(slot, {})
            if not isinstance(item, dict):
                continue
            label = self.field_to_text(item.get("label"))
            value_raw = item.get("value")
            value = self._parse_float(value_raw)
            if not label or value is None:
                continue
            numeric_values.append(value)
            detail_lines.append(f"{label}：{self._format_float(value)}")

        avg_value: float | None
        if numeric_values:
            avg_value = round(sum(numeric_values) / len(numeric_values), 3)
        else:
            avg_value = self._parse_float(best.get("avg_fallback"))

        return {"details": detail_lines, "avg": avg_value}

    async def query_latest_brief(
        self,
        app_token: str,
        headers: dict[str, str],
        table_ids_raw: str,
        table_names_raw: str,
        route_field: str,
        batch_field: str,
        message_time_field: str,
        scan_limit: int,
        detail_max_fields: int,
        no_data_text: str,
        title_text: str = "当前出窑批次及烧结压实：",
    ) -> str:
        table_ids = await self.resolve_table_ids(
            app_token=app_token,
            headers=headers,
            explicit_ids_raw=table_ids_raw,
            table_names_raw=table_names_raw,
        )
        if not table_ids:
            return no_data_text

        latest_by_line: dict[str, dict[str, Any]] = {}
        for table_id in table_ids:
            records = await self.list_table_records(
                app_token=app_token,
                headers=headers,
                table_id=table_id,
                scan_limit=scan_limit,
            )
            for item in records:
                fields = item.get("fields", {})
                if not isinstance(fields, dict):
                    continue
                if not self.is_sintering_record(fields, route_field=route_field, batch_field=batch_field):
                    continue

                line = self.infer_line(fields, route_field=route_field, batch_field=batch_field)
                if line not in {"A", "B"}:
                    continue

                current_time_text = self.field_to_text(fields.get(message_time_field))
                current_sort = self.time_to_sort_key(current_time_text)
                existing = latest_by_line.get(line)
                if existing is None or current_sort >= float(existing.get("sort", 0.0)):
                    latest_by_line[line] = {"sort": current_sort, "fields": fields}

        return self.build_reply_text(
            latest_by_line=latest_by_line,
            batch_field=batch_field,
            message_time_field=message_time_field,
            detail_max_fields=detail_max_fields,
            no_data_text=no_data_text,
            title_text=title_text,
        )
