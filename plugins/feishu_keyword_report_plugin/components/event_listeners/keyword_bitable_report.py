from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from components.command_parser import parse_report_command, parse_touch_material_command
from components.data_sources import FeishuBitableSource, FeishuSheetsSource
from components.report_core import day_metrics


def _default_touch_recipe_field_aliases() -> dict[str, list[str]]:
    return {
        "批次号": ["批次号", "批次", "批号", "出窑批次"],
        "铁磷比": ["铁磷比", "铁锂比", "铁磷"],
        "锂量": ["锂量", "碳酸锂量", "锂源量"],
        "酸量": ["酸量", "磷酸量"],
        "钛量": ["钛量", "二氧化钛量", "钛源量"],
        "糖量": ["糖量", "葡萄糖量", "蔗糖量"],
        "peg量": ["peg量", "PEG量", "peg", "PEG"],
        "窑炉温度": ["窑炉温度", "窑温", "烧结温度", "温度"],
    }


def _default_touch_infer_rules() -> dict[str, dict[str, Any]]:
    return {
        "low": {
            "max": 2.32,
            "text": "出窑物料偏松散，结块较少，整体硬度偏低。",
        },
        "medium": {
            "max": 2.40,
            "text": "出窑物料有结块，结块较小，有脆感.个别坩埚紧实度偏弱，整体物料硬度适中",
        },
        "high": {
            "text": "出窑物料结块偏大且较紧实，整体硬度偏高，需关注后续粉碎稳定性。",
        },
    }


class KeywordBitableReportListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

        self._bitable_source = FeishuBitableSource(self._call_feishu_json_api)
        self._sheets_source = FeishuSheetsSource(self._call_feishu_json_api)

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def _on_person_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        @self.handler(events.GroupMessageReceived)
        async def _on_group_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        # Keep compatibility with old runtimes.
        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

    # ===== Config =====

    def _get_timeout_seconds(self) -> float:
        raw = str(self.plugin.get_config().get("timeout_seconds", "20")).strip()
        try:
            timeout = float(raw)
        except ValueError:
            timeout = 20.0
        return max(1.0, min(120.0, timeout))

    def _get_str_config(self, key: str, default: str = "") -> str:
        return str(self.plugin.get_config().get(key, default)).strip()

    def _get_bool_config(self, key: str, default: bool) -> bool:
        value = self.plugin.get_config().get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_int_config(self, key: str, default: int, min_value: int, max_value: int) -> int:
        raw = self.plugin.get_config().get(key, default)
        try:
            if isinstance(raw, str):
                value = int(raw.strip())
            else:
                value = int(raw)
        except Exception:
            value = default
        return max(min_value, min(max_value, value))

    def _get_json_config(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        fallback = dict(default) if isinstance(default, dict) else {}
        raw = self.plugin.get_config().get(key, None)
        if raw is None:
            return fallback
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return fallback

        text = raw.strip()
        if not text:
            return fallback
        try:
            loaded = json.loads(text)
        except Exception:
            return fallback
        return loaded if isinstance(loaded, dict) else fallback

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        if not raw:
            return []
        parts = re.split(r"[,\n;，；]+", raw)
        return [item.strip() for item in parts if item.strip()]

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        normalized = re.sub(r"\s+", "", text.strip())
        normalized = normalized.strip("，,。.!！？?；;：:")
        return normalized

    def _resolve_commands(self) -> set[str]:
        raw = self._get_str_config("keyword_commands", "日报")
        commands = self._split_csv(raw)
        if not commands:
            commands = ["日报"]
        return {self._normalize_command_text(item) for item in commands if self._normalize_command_text(item)}

    def _resolve_touch_material_commands(self) -> set[str]:
        raw = self._get_str_config("touch_material_commands", "摸料")
        commands = self._split_csv(raw)
        if not commands:
            commands = ["摸料"]
        return {self._normalize_command_text(item) for item in commands if self._normalize_command_text(item)}

    def _resolve_data_source_mode(self) -> str:
        mode = self._get_str_config("data_source_mode", "auto").lower()
        if mode not in {"auto", "sheets", "bitable"}:
            return "auto"
        return mode

    def _resolve_target_sheets(self, command_sheets: list[str]) -> list[str]:
        if command_sheets:
            return command_sheets
        configured = self._split_csv(self._get_str_config("sheets_sheet_names", ""))
        return configured

    def _resolve_touch_recipe_field_aliases(self) -> dict[str, list[str]]:
        defaults = _default_touch_recipe_field_aliases()
        configured = self._get_json_config("touch_recipe_field_aliases_json", {})
        if not configured:
            return defaults

        merged: dict[str, list[str]] = {}
        for logical_field, default_aliases in defaults.items():
            merged[logical_field] = list(default_aliases)

        for key, raw_aliases in configured.items():
            logical_key = str(key).strip()
            if not logical_key:
                continue
            alias_list: list[str] = []
            if isinstance(raw_aliases, list):
                alias_list = [str(item).strip() for item in raw_aliases if str(item).strip()]
            elif isinstance(raw_aliases, str):
                alias_list = [x for x in self._split_csv(raw_aliases) if x]
            if not alias_list:
                continue

            current = merged.get(logical_key, [])
            seen: set[str] = set()
            out: list[str] = []
            for alias in alias_list + current:
                if alias in seen:
                    continue
                seen.add(alias)
                out.append(alias)
            merged[logical_key] = out

        return merged

    def _resolve_touch_infer_rules(self) -> dict[str, dict[str, Any]]:
        defaults = _default_touch_infer_rules()
        configured = self._get_json_config("touch_material_infer_rules_json", {})
        if not configured:
            return defaults

        out: dict[str, dict[str, Any]] = {}
        for level in ("low", "medium", "high"):
            base = dict(defaults.get(level, {}))
            raw_level = configured.get(level)
            if isinstance(raw_level, dict):
                if "text" in raw_level:
                    base["text"] = str(raw_level.get("text", "")).strip() or base.get("text", "")
                if "max" in raw_level:
                    try:
                        base["max"] = float(raw_level.get("max"))
                    except Exception:
                        pass
            out[level] = base
        return out

    def _resolve_touch_no_data_text(self) -> str:
        return self._get_str_config("touch_material_no_data_text", "未查到当前出窑批次或压实数据。")

    @staticmethod
    def _resolve_touch_prefer_line(segment: str) -> str:
        segment_text = str(segment).strip().upper()
        if segment_text.startswith("A"):
            return "A"
        if segment_text.startswith("B"):
            return "B"
        return ""

    @staticmethod
    def _strip_trend_sections(text: str, show_process_trend: bool, show_product_trend: bool) -> str:
        if not text or (show_process_trend and show_product_trend):
            return text

        section_markers: list[str] = []
        if not show_process_trend:
            section_markers.append("制程趋势（")
        if not show_product_trend:
            section_markers.append("成品趋势（")

        lines = text.splitlines()
        result: list[str] = []
        skipping = False

        for line in lines:
            stripped = line.strip()
            if not skipping and any(marker in stripped for marker in section_markers):
                skipping = True
                continue

            if skipping:
                if line.startswith("    "):
                    continue
                skipping = False

            result.append(line)

        return "\n".join(result).strip()

    # ===== Message helpers =====

    @staticmethod
    def _extract_plain_text(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                text = str(component.text).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _is_group_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "group"

    @staticmethod
    def _is_person_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "person"

    @staticmethod
    def _event_supports_reply_chain(event_ctx: context.EventContext) -> bool:
        model_fields = getattr(type(event_ctx.event), "model_fields", {})
        return isinstance(model_fields, dict) and "reply_message_chain" in model_fields

    async def _resolve_bot_uuid(self, event_ctx: context.EventContext) -> str:
        try:
            if hasattr(event_ctx, "get_bot_uuid"):
                bot_uuid = await event_ctx.get_bot_uuid()  # type: ignore[attr-defined]
                if bot_uuid:
                    return str(bot_uuid).strip()
        except Exception:
            pass
        query = getattr(event_ctx.event, "query", None)
        if query is not None:
            return str(getattr(query, "bot_uuid", "")).strip()
        return ""

    async def _send_origin_message(self, event_ctx: context.EventContext, text: str) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        if launcher_type not in {"group", "person"}:
            return False

        launcher_id = str(getattr(event_ctx.event, "launcher_id", "")).strip()
        if not launcher_id:
            return False

        bot_uuid = await self._resolve_bot_uuid(event_ctx)
        if not bot_uuid:
            return False

        await self.plugin.send_message(
            bot_uuid=bot_uuid,
            target_type=launcher_type,
            target_id=launcher_id,
            message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
        )
        return True

    async def _reply_text(self, event_ctx: context.EventContext, text: str) -> None:
        if not text:
            return
        if self._event_supports_reply_chain(event_ctx):
            event_ctx.event.reply_message_chain = platform_message.MessageChain([platform_message.Plain(text=text)])
            return
        await self._send_origin_message(event_ctx, text)

    # ===== Feishu API =====

    async def _request_tenant_access_token(self) -> str:
        app_id = self._get_str_config("app_id", "")
        app_secret = self._get_str_config("app_secret", "")
        token_endpoint = self._get_str_config(
            "token_endpoint", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        )
        if not app_id or not app_secret:
            raise ValueError("插件配置 app_id/app_secret 必填。")

        payload = {"app_id": app_id, "app_secret": app_secret}
        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_endpoint, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Token 获取失败，HTTP {response.status_code}: {response.text[:300]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("Token 接口返回非 JSON。") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"Token 获取失败，code={code}，msg={body.get('msg', '')}")

        token = str(body.get("tenant_access_token", "")).strip()
        if not token:
            raise RuntimeError("tenant_access_token 为空。")

        expire = int(body.get("expire", 7200))
        self._tenant_access_token = token
        self._tenant_access_token_expire_at = time.time() + max(60, expire - 300)
        return token

    async def _get_tenant_access_token(self) -> str:
        if self._tenant_access_token and time.time() < self._tenant_access_token_expire_at:
            return self._tenant_access_token
        async with self._token_lock:
            if self._tenant_access_token and time.time() < self._tenant_access_token_expire_at:
                return self._tenant_access_token
            return await self._request_tenant_access_token()

    async def _build_auth_headers(self) -> dict[str, str]:
        token = await self._get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def _call_feishu_json_api(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method=method, url=endpoint, headers=headers, json=payload, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("飞书接口返回非 JSON。") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"code={code}, msg={body.get('msg', '')}")

        data = body.get("data", {}) or {}
        if not isinstance(data, dict):
            return {}
        return data

    # ===== Data source orchestration =====

    async def _run_sheets_report(self, date_arg: str | None, command_sheets: list[str]) -> str:
        spreadsheet_token = self._get_str_config("sheets_spreadsheet_token", "")
        if not spreadsheet_token:
            raise ValueError("未配置 sheets_spreadsheet_token。")

        target_sheets = self._resolve_target_sheets(command_sheets)
        cell_range = self._get_str_config("sheets_range", "A1:ZZ2000") or "A1:ZZ2000"
        headers = await self._build_auth_headers()

        matrices, available_titles, missing = await self._sheets_source.fetch_line_matrices(
            spreadsheet_token=spreadsheet_token,
            headers=headers,
            target_sheet_names=target_sheets,
            cell_range=cell_range,
        )

        if command_sheets and missing:
            available = "、".join(available_titles) if available_titles else "无"
            raise ValueError(f"指定线别不存在：{'、'.join(missing)}；可选：{available}")

        selected_sheets = target_sheets if target_sheets else available_titles
        report = day_metrics.build_standard_report_from_matrices(
            sheet_matrices=matrices,
            selected_sheets=selected_sheets,
            date_arg=date_arg,
            date_mode=self._get_str_config("date_mode", "global"),
            lookback_days=self._get_int_config("lookback_days", 7, 0, 60),
            trend_days=self._get_int_config("trend_days", 7, 0, 30),
            stale_threshold_process=self._get_int_config("stale_threshold_process", 2, 0, 30),
            stale_threshold_product=self._get_int_config("stale_threshold_product", 3, 0, 30),
            stale_threshold_electrochem=self._get_int_config("stale_threshold_electrochem", 5, 0, 30),
            report_show_placeholder_sections=self._get_bool_config("report_show_placeholder_sections", False),
            spec_registry_json=self._get_str_config("spec_registry_json", ""),
            auto_fix_quality=False,
        )
        text = str(report.get("text", "")).strip()
        text = self._strip_trend_sections(
            text=text,
            show_process_trend=self._get_bool_config("report_show_process_trend", True),
            show_product_trend=self._get_bool_config("report_show_product_trend", True),
        )
        line_errors = report.get("line_errors", [])
        if isinstance(line_errors, list) and line_errors:
            text = f"{text}\n\n提示：以下线别未纳入日报：{'；'.join(str(x) for x in line_errors)}"
        return text

    async def _run_bitable_brief_report(self, title_text: str) -> str:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token:
            raise ValueError("未配置 bitable_app_token。")

        headers = await self._build_auth_headers()
        return await self._bitable_source.query_latest_brief(
            app_token=app_token,
            headers=headers,
            table_ids_raw=self._get_str_config("sintering_table_ids", ""),
            table_names_raw=self._get_str_config("sintering_table_names", "A线烧结汇总,B线烧结汇总"),
            route_field=self._get_str_config("route_field", "路由"),
            batch_field=self._get_str_config("batch_field", "批次号"),
            message_time_field=self._get_str_config("message_time_field", "消息时间"),
            scan_limit=self._get_int_config("scan_limit", 1000, min_value=50, max_value=5000),
            detail_max_fields=self._get_int_config("detail_max_fields", 4, min_value=1, max_value=10),
            no_data_text=self._get_str_config("no_data_text", "未查到出窑批次或烧结压实数据。"),
            title_text=title_text,
        )

    async def _dispatch_report(self, date_arg: str | None, command_sheets: list[str]) -> str:
        mode = self._resolve_data_source_mode()
        if mode == "sheets":
            return await self._run_sheets_report(date_arg=date_arg, command_sheets=command_sheets)

        if mode == "bitable":
            return await self._run_bitable_brief_report(title_text="当前出窑批次及烧结压实（多维表模式）：")

        # auto: 在线表格优先，失败回退多维表。
        try:
            return await self._run_sheets_report(date_arg=date_arg, command_sheets=command_sheets)
        except Exception as sheets_exc:
            try:
                fallback = await self._run_bitable_brief_report(title_text="当前出窑批次及烧结压实（多维表回退）：")
            except Exception as bitable_exc:
                raise RuntimeError(f"在线表格失败：{sheets_exc}；多维表回退失败：{bitable_exc}") from bitable_exc
            return f"【在线表格查询失败，已回退多维表】{sheets_exc}\n{fallback}"

    @staticmethod
    def _safe_recipe_value(recipe: dict[str, str], field: str) -> str:
        value = str(recipe.get(field, "")).strip()
        return value or "--"

    def _infer_material_property(self, avg_compaction: float | None) -> str:
        if avg_compaction is None:
            return ""
        rules = self._resolve_touch_infer_rules()

        low = rules.get("low", {})
        medium = rules.get("medium", {})
        high = rules.get("high", {})
        low_max = float(low.get("max", 2.32))
        medium_max = float(medium.get("max", 2.40))

        if avg_compaction <= low_max:
            return str(low.get("text", "")).strip()
        if avg_compaction <= medium_max:
            return str(medium.get("text", "")).strip()
        return str(high.get("text", "")).strip()

    async def _run_touch_material_report(self, segment: str) -> str:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token:
            raise ValueError("未配置 bitable_app_token。")

        headers = await self._build_auth_headers()
        scan_limit = self._get_int_config("scan_limit", 1000, min_value=50, max_value=5000)

        kiln_info = await self._bitable_source.query_latest_kiln_batch_by_segment(
            app_token=app_token,
            headers=headers,
            segment=segment,
            table_ids_raw=self._get_str_config("kiln_batch_table_ids", ""),
            table_names_raw=self._get_str_config("kiln_batch_table_names", "窑炉批次进窑出窑表"),
            batch_field=self._get_str_config("batch_field", "批次号"),
            scan_limit=scan_limit,
        )
        if kiln_info is None:
            return self._resolve_touch_no_data_text()

        batch_raw = str(kiln_info.get("batch_raw", "")).strip()
        batch_core = str(kiln_info.get("batch_core", "")).strip()
        batch_display = batch_raw or batch_core
        if not batch_display:
            return self._resolve_touch_no_data_text()

        slots_raw = kiln_info.get("slots", [])
        slots: list[str] = []
        if isinstance(slots_raw, list):
            for item in slots_raw:
                slot_text = str(item).strip()
                if slot_text:
                    slots.append(slot_text)
        slot_list_text = "/".join(slots) if slots else "--"

        sintering = await self._bitable_source.query_sintering_detail_by_batch_segment(
            app_token=app_token,
            headers=headers,
            batch_core=batch_core or batch_display,
            segment=segment,
            table_ids_raw=self._get_str_config("sintering_table_ids", ""),
            table_names_raw=self._get_str_config("sintering_table_names", "A线烧结汇总,B线烧结汇总"),
            route_field=self._get_str_config("route_field", "路由"),
            batch_field=self._get_str_config("batch_field", "批次号"),
            message_time_field=self._get_str_config("message_time_field", "消息时间"),
            scan_limit=scan_limit,
        )
        detail_lines = sintering.get("details", [])
        if not isinstance(detail_lines, list):
            detail_lines = []
        detail_lines = [str(item).strip() for item in detail_lines if str(item).strip()]

        avg_compaction: float | None = None
        avg_raw = sintering.get("avg")
        if isinstance(avg_raw, (int, float)):
            avg_compaction = float(avg_raw)

        recipe = {
            "铁磷比": "--",
            "锂量": "--",
            "酸量": "--",
            "钛量": "--",
            "糖量": "--",
            "peg量": "--",
            "窑炉温度": "--",
        }
        spreadsheet_token = self._get_str_config("sheets_spreadsheet_token", "")
        if spreadsheet_token:
            try:
                recipe = await self._sheets_source.query_recipe_by_batch(
                    spreadsheet_token=spreadsheet_token,
                    headers=headers,
                    target_sheet_names=self._resolve_target_sheets([]),
                    cell_range=self._get_str_config("sheets_range", "A1:ZZ2000") or "A1:ZZ2000",
                    batch_core=batch_core or batch_display,
                    prefer_line=self._resolve_touch_prefer_line(segment),
                    field_aliases=self._resolve_touch_recipe_field_aliases(),
                    placeholder="--",
                )
            except Exception:
                # 触发降级，保留占位符，不影响摸料主链路回复。
                pass

        recipe_pack = "+".join(
            [
                self._safe_recipe_value(recipe, "铁磷比"),
                self._safe_recipe_value(recipe, "锂量"),
                self._safe_recipe_value(recipe, "酸量"),
                self._safe_recipe_value(recipe, "钛量"),
                self._safe_recipe_value(recipe, "糖量"),
                self._safe_recipe_value(recipe, "peg量"),
            ]
        )
        kiln_temperature = self._safe_recipe_value(recipe, "窑炉温度")
        material_text = self._infer_material_property(avg_compaction)
        main_line = f"{batch_display}（{recipe_pack}）{segment}-{slot_list_text}-{kiln_temperature}{material_text}"

        if detail_lines:
            return "\n".join([main_line, "压实", *detail_lines])
        return "\n".join([main_line, "压实未出"])

    # ===== Entry =====

    async def _handle_command(self, event_ctx: context.EventContext) -> None:
        plain_text = self._extract_plain_text(event_ctx.event.message_chain)
        if not plain_text:
            return

        in_group = self._is_group_event(event_ctx)
        in_person = self._is_person_event(event_ctx)
        allow_group = self._get_bool_config("reply_in_group", True)
        allow_person = self._get_bool_config("reply_in_person", True)
        if (in_group and not allow_group) or (in_person and not allow_person):
            return

        touch_parse = parse_touch_material_command(plain_text, self._resolve_touch_material_commands())
        if touch_parse.triggered:
            event_ctx.prevent_default()
            event_ctx.prevent_postorder()

            if touch_parse.error:
                await self._reply_text(event_ctx, touch_parse.error)
                return

            touch_command = touch_parse.value
            if touch_command is None:
                return
            try:
                text = await self._run_touch_material_report(segment=touch_command.segment)
                await self._reply_text(event_ctx, text)
            except Exception as exc:
                await self._reply_text(event_ctx, f"摸料查询失败：{exc}")
            return

        parse_result = parse_report_command(plain_text, self._resolve_commands())
        if not parse_result.triggered:
            return

        event_ctx.prevent_default()
        event_ctx.prevent_postorder()

        if parse_result.error:
            await self._reply_text(event_ctx, parse_result.error)
            return

        command = parse_result.value
        if command is None:
            return

        try:
            text = await self._dispatch_report(
                date_arg=command.date_arg,
                command_sheets=command.sheet_names,
            )
            await self._reply_text(event_ctx, text)
        except Exception as exc:
            await self._reply_text(event_ctx, f"日报查询失败：{exc}")
