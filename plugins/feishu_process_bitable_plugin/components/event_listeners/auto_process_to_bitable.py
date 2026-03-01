from __future__ import annotations

import asyncio
import base64
import datetime
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


@dataclass
class ParsedRecord:
    scenario: str
    line: str
    batch_id: str
    route_key: str
    fields: dict[str, Any]


class AutoProcessToBitableListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

    # ===== Common utils =====

    def _get_timeout_seconds(self) -> float:
        raw = str(self.plugin.get_config().get("timeout_seconds", "20")).strip()
        try:
            timeout = float(raw)
        except ValueError:
            timeout = 20.0
        return max(1.0, min(120.0, timeout))

    def _get_bool_config(self, key: str, default: bool) -> bool:
        value = self.plugin.get_config().get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_str_config(self, key: str, default: str = "") -> str:
        return str(self.plugin.get_config().get(key, default)).strip()

    def _get_json_config(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if default is None:
            default = {}
        raw = self.plugin.get_config().get(key, default)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return default
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return default
        return default

    @staticmethod
    def _strip_data_url_prefix(data: str) -> str:
        if data.startswith("data:") and "," in data:
            return data.split(",", 1)[1]
        return data

    @staticmethod
    def _truncate_text(text: str, limit: int = 5000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit]

    @staticmethod
    def _normalize_dash(value: str) -> str:
        return re.sub(r"[-–—]+", "-", value)

    @staticmethod
    def _extract_plain_text(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                txt = str(component.text).strip()
                if txt:
                    parts.append(txt)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_images(message_chain: platform_message.MessageChain) -> list[platform_message.Image]:
        return [component for component in message_chain if isinstance(component, platform_message.Image)]

    def _resolve_message_time(self, event_ctx: context.EventContext) -> str:
        candidate = None
        message_event = getattr(event_ctx.event, "message_event", None)
        if message_event is not None:
            candidate = getattr(message_event, "time", None)

        if candidate is None:
            return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")

        try:
            ts = float(candidate)
            if ts > 1e12:
                ts = ts / 1000.0
            if ts > 0:
                return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).astimezone().isoformat(
                    timespec="seconds"
                )
        except Exception:
            pass

        return str(candidate)

    # ===== OCR =====

    async def _get_image_bytes(self, image: platform_message.Image) -> bytes:
        if image.base64:
            try:
                normalized = self._strip_data_url_prefix(str(image.base64))
                return base64.b64decode(normalized)
            except Exception as exc:
                raise ValueError(f"Invalid image base64: {exc}") from exc

        if image.url:
            timeout = self._get_timeout_seconds()
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(str(image.url))
                if response.status_code != 200:
                    raise ValueError(f"Failed to download image from url, HTTP {response.status_code}.")
                return response.content

        if image.path:
            try:
                return Path(image.path).read_bytes()
            except Exception as exc:
                raise ValueError(f"Failed to read image from path: {exc}") from exc

        raise ValueError("Image component has no base64/url/path content.")

    async def _request_tenant_access_token(self) -> str:
        cfg = self.plugin.get_config()
        app_id = str(cfg.get("app_id", "")).strip()
        app_secret = str(cfg.get("app_secret", "")).strip()
        token_endpoint = str(
            cfg.get("token_endpoint", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal")
        ).strip()

        if not app_id or not app_secret:
            raise ValueError("Plugin config app_id/app_secret is required.")

        timeout = self._get_timeout_seconds()
        payload = {"app_id": app_id, "app_secret": app_secret}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_endpoint, json=payload)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to get tenant_access_token, HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("Token endpoint returned non-JSON response.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"Token endpoint failed, code={code}, msg={body.get('msg', '')}")

        token = body.get("tenant_access_token")
        if not token:
            raise RuntimeError("Token endpoint returned empty tenant_access_token.")

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

    async def _recognize_image_bytes(self, image_bytes: bytes) -> str:
        ocr_endpoint = self._get_str_config(
            "ocr_endpoint", "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize"
        )
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        token = await self._get_tenant_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"image": image_base64}

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(ocr_endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            raise RuntimeError(f"OCR request failed, HTTP {response.status_code}: {response.text[:200]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("OCR response is not JSON.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"OCR endpoint returned error, code={code}, msg={body.get('msg', '')}")

        data = body.get("data", {}) or {}
        text_list = data.get("text_list", []) or []
        lines: list[str] = []
        for item in text_list:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    lines.append(text.strip())
            elif isinstance(item, str) and item.strip():
                lines.append(item.strip())

        return "\n".join(lines).strip()

    # ===== Built-in parsers =====

    def _process_switch(self, key: str, default: bool = True) -> bool:
        switch = self._get_json_config(
            "process_switch_json",
            {
                "spray": True,
                "feeding": True,
                "sintering": True,
                "crushing": True,
                "pure_water": True,
            },
        )
        value = switch.get(key, default)
        if isinstance(value, bool):
            return value
        return bool(value)

    def _parse_spray(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("spray", True):
            return []

        normalized_text = self._normalize_dash(text)
        main_regex = re.compile(
            r"([AB])\s*线\s*喷雾\s*批次(?:号)?\s*[:：]?\s*"
            r"(S\d+(?:-[A-Z]{2})?-D[AB]\d{4}-\d+(?:-?[AB]\d)?)",
            re.IGNORECASE,
        )
        params_regex = re.compile(r"([\u4e00-\u9fa5]+)\s*[:：]?\s*(\d+\.?\d*)")
        required_params = {"开度", "进口温度", "出口温度", "雾化轮转速", "水分"}

        records: list[ParsedRecord] = []
        for match in main_regex.finditer(normalized_text):
            line = str(match.group(1)).upper()
            batch_id = self._normalize_dash(str(match.group(2))).upper().strip()
            fields: dict[str, Any] = {}
            for key, value in params_regex.findall(normalized_text):
                if key in required_params:
                    try:
                        fields[key] = float(value)
                    except Exception:
                        fields[key] = value
            fields["消息时间"] = message_time
            records.append(
                ParsedRecord(
                    scenario="spray",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"spray.{line}",
                    fields=fields,
                )
            )
        return records

    def _parse_feeding(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("feeding", True):
            return []

        normalized_text = self._normalize_dash(text)
        batch_regex = re.compile(
            r"批次(?:号)?\s*[:：]?\s*"
            r"(S\d+(?:-[A-Z]{2})?-D[AB]\d{4}-\d+(?:-?[AB]\d)?)",
            re.IGNORECASE,
        )
        value_regexes: list[tuple[str, re.Pattern[str]]] = [
            ("磷酸铁需补(kg)", re.compile(r"磷酸铁需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("碳酸锂需补(kg)", re.compile(r"碳酸锂需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("D5总量(kg)", re.compile(r"D5(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("BL总量(kg)", re.compile(r"BL(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
        ]

        extracted_values: dict[str, Any] = {}
        for field, pattern in value_regexes:
            match = pattern.search(normalized_text)
            if match:
                try:
                    extracted_values[field] = float(match.group(1))
                except Exception:
                    extracted_values[field] = match.group(1)

        if not extracted_values:
            return []

        records: list[ParsedRecord] = []
        for match in batch_regex.finditer(normalized_text):
            batch_id = self._normalize_dash(str(match.group(1))).upper().strip()
            line = "A" if "-DA" in batch_id else "B" if "-DB" in batch_id else "UNKNOWN"
            fields = dict(extracted_values)
            fields["消息时间"] = message_time
            route_key = f"feeding.{line}" if line in {"A", "B"} else "feeding"
            records.append(
                ParsedRecord(
                    scenario="feeding",
                    line=line,
                    batch_id=batch_id,
                    route_key=route_key,
                    fields=fields,
                )
            )

        return records

    def _parse_sintering(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("sintering", True):
            return []

        normalized_text = self._normalize_dash(text)
        regex = re.compile(
            r"(S\d+-SC-[A-Z]{2}\d{4}-\d+)-([AB]\d+-\d+)-\d+\s*min\s*[:：]\s*([\d\.]+)",
            re.IGNORECASE,
        )

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = base_id.upper().strip()
            sample_id = sample_id.upper().strip()
            line = "A" if sample_id.startswith("A") else "B" if sample_id.startswith("B") else "UNKNOWN"
            if line not in {"A", "B"}:
                continue

            key = (base_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            grouped[key][sample_id] = float(value)

        records: list[ParsedRecord] = []
        for (batch_id, line), fields in grouped.items():
            average_map: dict[str, list[float]] = {}
            for sample_id, value in list(fields.items()):
                if sample_id == "消息时间":
                    continue
                if not isinstance(value, (int, float)):
                    continue
                prefix = sample_id.split("-")[0]
                average_map.setdefault(prefix, []).append(float(value))

            for prefix, values in average_map.items():
                if values:
                    fields[f"{prefix}-均值"] = round(sum(values) / len(values), 3)

            records.append(
                ParsedRecord(
                    scenario="sintering",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"sintering.{line}",
                    fields=fields,
                )
            )

        return records

    def _split_sample_id(self, sample_id: str) -> tuple[str, str | None]:
        sample_id = sample_id.strip()
        freq_match = re.search(r"(?i)(?:-|\s*)(\d+(?:\.\d+)?)\s*HZ[\s\)\]）】]*$", sample_id)
        if freq_match:
            base = sample_id[: freq_match.start()].rstrip().rstrip("-").rstrip()
            if base:
                return base, f"{freq_match.group(1).upper()}HZ"

        parts = sample_id.split("-")
        if len(parts) >= 2 and re.fullmatch(r"\d+(?:\.\d+)?HZ", parts[-1].strip(), re.IGNORECASE):
            return "-".join(parts[:-1]), parts[-1].upper().strip()

        return sample_id, None

    def _parse_crushing(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("crushing", True):
            return []

        normalized_text = self._normalize_dash(text)
        regex = re.compile(r"(S\d+-FS-[A-Z]{2}\d{4}-\d+)-([AB]\d-[^：:\n]+)[：:]\s*([\d\.]+)", re.IGNORECASE)

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = base_id.upper().strip()
            sample_id = sample_id.upper().strip()
            sample_key, freq = self._split_sample_id(sample_id)

            if "-DA" in base_id:
                line = "A"
            elif "-DB" in base_id:
                line = "B"
            elif sample_key.startswith("A"):
                line = "A"
            elif sample_key.startswith("B"):
                line = "B"
            else:
                line = "UNKNOWN"

            if line not in {"A", "B"}:
                continue

            key = (base_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            grouped[key][sample_key] = float(value)
            if freq:
                grouped[key][f"{sample_key}_频率"] = freq

        records: list[ParsedRecord] = []
        for (batch_id, line), fields in grouped.items():
            records.append(
                ParsedRecord(
                    scenario="crushing",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"crushing.{line}",
                    fields=fields,
                )
            )

        return records

    def _parse_pure_water(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("pure_water", True):
            return []

        normalized_text = self._normalize_dash(text)
        ph_match = re.search(r"车间[A/B]*线?纯水\s*PH\s*[:：]\s*(\d+\.?\d*)", normalized_text, re.IGNORECASE)
        if not ph_match:
            return []

        batch_regex = re.compile(r"(S\d+-TL-D[AB]\d{4}-\d+)", re.IGNORECASE)
        batch_matches = [self._normalize_dash(m.group(1)).upper().strip() for m in batch_regex.finditer(normalized_text)]
        if not batch_matches:
            return []

        batch_id = "\n".join(batch_matches)
        ph_value = float(ph_match.group(1))

        if all("-DA" in bid for bid in batch_matches):
            line = "A"
        elif all("-DB" in bid for bid in batch_matches):
            line = "B"
        else:
            line = "MIXED"

        route_key = f"pure_water.{line}" if line in {"A", "B"} else "pure_water"
        fields = {
            "PH值": ph_value,
            "消息时间": message_time,
        }
        return [
            ParsedRecord(
                scenario="pure_water",
                line=line,
                batch_id=batch_id,
                route_key=route_key,
                fields=fields,
            )
        ]

    # ===== Extra rule parser (optional) =====

    @staticmethod
    def _extract_kv_pairs(text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for sep in ("：", ":", "="):
                if sep in line:
                    key, val = line.split(sep, 1)
                    key = key.strip()
                    val = val.strip()
                    if key and val:
                        result[key.lower()] = val
                    break
        return result

    @staticmethod
    def _extract_regex_fields(text: str, rules: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            field = str(rule.get("field", "")).strip()
            pattern = str(rule.get("pattern", "")).strip()
            group = rule.get("group", None)
            if not field or not pattern:
                continue

            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            except re.error:
                continue
            if not match:
                continue

            extracted: str | None = None
            if group is not None:
                try:
                    extracted = str(match.group(group)).strip()
                except Exception:
                    extracted = None
            else:
                named = match.groupdict()
                if named:
                    for _, value in named.items():
                        if value is not None and str(value).strip():
                            extracted = str(value).strip()
                            break
                if extracted is None and match.groups():
                    extracted = str(match.group(1)).strip()
                if extracted is None:
                    extracted = str(match.group(0)).strip()

            if extracted:
                result[field] = extracted
        return result

    def _extract_extra_fields(self, full_text: str) -> tuple[dict[str, Any], bool]:
        rules = self._get_json_config("rules_json", {})
        fields: dict[str, Any] = {}
        matched = False

        constant_fields = rules.get("constant_fields", {})
        if isinstance(constant_fields, dict):
            for k, v in constant_fields.items():
                key = str(k).strip()
                if key:
                    fields[key] = v
                    matched = True

        kv_aliases = rules.get("kv_aliases", {})
        if isinstance(kv_aliases, dict):
            kv_pairs = self._extract_kv_pairs(full_text)
            for target_field, aliases_value in kv_aliases.items():
                tf = str(target_field).strip()
                if not tf:
                    continue
                aliases: list[str] = []
                if isinstance(aliases_value, str):
                    aliases = [aliases_value]
                elif isinstance(aliases_value, list):
                    aliases = [str(item) for item in aliases_value]

                for alias in aliases:
                    normalized = alias.strip().lower()
                    if normalized and normalized in kv_pairs:
                        fields[tf] = kv_pairs[normalized]
                        matched = True
                        break

        regex_rules = rules.get("regex_extractors", [])
        if isinstance(regex_rules, list):
            regex_fields = self._extract_regex_fields(full_text, regex_rules)
            if regex_fields:
                fields.update(regex_fields)
                matched = True

        return fields, matched

    # ===== Bitable write =====

    def _resolve_table_id(self, route_key: str) -> str:
        routing = self._get_json_config("table_routing_json", {})
        if route_key in routing and str(routing.get(route_key, "")).strip():
            return str(routing[route_key]).strip()

        prefix = route_key.split(".", 1)[0]
        if prefix in routing and str(routing.get(prefix, "")).strip():
            return str(routing[prefix]).strip()

        return self._get_str_config("bitable_default_table_id", "")

    async def _write_record_to_bitable(self, table_id: str, fields: dict[str, Any]) -> tuple[bool, str]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id:
            return False, "bitable_app_token or table_id is empty"

        endpoint_template = self._get_str_config(
            "bitable_endpoint_template",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
        )
        endpoint = endpoint_template.format(app_token=app_token, table_id=table_id)

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"fields": fields}

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            return False, f"bitable write failed, HTTP {response.status_code}: {response.text[:300]}"

        try:
            body = response.json()
        except Exception:
            return False, f"bitable write failed, non-JSON response: {response.text[:300]}"

        code = int(body.get("code", 0))
        if code != 0:
            return False, f"bitable write failed, code={code}, msg={body.get('msg', '')}"

        data = body.get("data", {}) or {}
        record = data.get("record", {}) or {}
        record_id = ""
        if isinstance(record, dict):
            record_id = str(record.get("record_id", "")).strip()

        return True, record_id

    def _apply_builtin_fields(
        self,
        target_fields: dict[str, Any],
        record: ParsedRecord,
        event_ctx: context.EventContext,
        plain_text: str,
        ocr_text: str,
        message_time: str,
    ) -> None:
        scenario_field = self._get_str_config("scenario_field", "业务类型")
        line_field = self._get_str_config("line_field", "产线")
        batch_field = self._get_str_config("batch_field", "批次号")
        route_field = self._get_str_config("route_field", "路由")

        raw_text_field = self._get_str_config("raw_text_field", "原始文本")
        ocr_text_field = self._get_str_config("ocr_text_field", "OCR文本")

        sender_field = self._get_str_config("sender_id_field", "发送者ID")
        launcher_field = self._get_str_config("launcher_id_field", "会话ID")
        launcher_type_field = self._get_str_config("launcher_type_field", "会话类型")
        timestamp_field = self._get_str_config("message_time_field", "消息时间")

        if scenario_field:
            target_fields[scenario_field] = record.scenario
        if line_field:
            target_fields[line_field] = record.line
        if batch_field and record.batch_id:
            target_fields[batch_field] = record.batch_id
        if route_field:
            target_fields[route_field] = record.route_key

        if raw_text_field and plain_text:
            target_fields[raw_text_field] = self._truncate_text(plain_text)
        if ocr_text_field and ocr_text:
            target_fields[ocr_text_field] = self._truncate_text(ocr_text)

        if sender_field:
            target_fields[sender_field] = str(getattr(event_ctx.event, "sender_id", ""))
        if launcher_field:
            target_fields[launcher_field] = str(getattr(event_ctx.event, "launcher_id", ""))
        if launcher_type_field:
            target_fields[launcher_type_field] = str(getattr(event_ctx.event, "launcher_type", ""))
        if timestamp_field:
            target_fields[timestamp_field] = message_time

    def _parse_records(self, full_text: str, message_time: str) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        records.extend(self._parse_spray(full_text, message_time))
        records.extend(self._parse_feeding(full_text, message_time))
        records.extend(self._parse_sintering(full_text, message_time))
        records.extend(self._parse_crushing(full_text, message_time))
        records.extend(self._parse_pure_water(full_text, message_time))
        return records

    async def _handle_normal_message(self, event_ctx: context.EventContext) -> None:
        message_chain = event_ctx.event.message_chain
        plain_text = self._extract_plain_text(message_chain)
        images = self._extract_images(message_chain)

        if not plain_text and not images:
            return

        ocr_text = ""
        if images and self._get_bool_config("enable_ocr_for_images", True):
            ocr_texts: list[str] = []
            for image in images:
                try:
                    image_bytes = await self._get_image_bytes(image)
                    text = await self._recognize_image_bytes(image_bytes)
                    if text:
                        ocr_texts.append(text)
                except Exception:
                    continue
            if ocr_texts:
                ocr_text = "\n\n".join(ocr_texts).strip()

        full_text_parts = [plain_text.strip(), ocr_text.strip()]
        full_text = "\n".join([part for part in full_text_parts if part]).strip()
        if not full_text:
            return

        message_time = self._resolve_message_time(event_ctx)
        records = self._parse_records(full_text, message_time)

        # Fallback using extra rules_json if built-in parsers found nothing.
        if not records:
            extra_fields, matched = self._extract_extra_fields(full_text)
            if matched:
                records.append(
                    ParsedRecord(
                        scenario="custom",
                        line="",
                        batch_id="",
                        route_key="custom",
                        fields=extra_fields,
                    )
                )

        if not records and self._get_bool_config("write_raw_when_no_match", False):
            records.append(
                ParsedRecord(
                    scenario="raw",
                    line="",
                    batch_id="",
                    route_key="raw",
                    fields={},
                )
            )

        if not records:
            return

        success_count = 0
        errors: list[str] = []

        for record in records:
            table_id = self._resolve_table_id(record.route_key)
            if not table_id:
                errors.append(f"route={record.route_key}, table_id not configured")
                continue

            write_fields = dict(record.fields)
            self._apply_builtin_fields(write_fields, record, event_ctx, plain_text, ocr_text, message_time)

            ok, detail = await self._write_record_to_bitable(table_id, write_fields)
            if ok:
                success_count += 1
            else:
                errors.append(f"route={record.route_key}, {detail}")

        if success_count > 0:
            if self._get_bool_config("reply_on_write", False):
                template = self._get_str_config("reply_text_template", "已写入飞书表格。")
                reply_text = template.replace("{count}", str(success_count))
                event_ctx.event.reply_message_chain = platform_message.MessageChain(
                    [platform_message.Plain(text=reply_text)]
                )

            if self._get_bool_config("prevent_default_on_write", False):
                event_ctx.prevent_default()
                event_ctx.prevent_postorder()

        if errors and self._get_bool_config("reply_on_error", True):
            err = self._truncate_text("; ".join(errors), 1000)
            event_ctx.event.reply_message_chain = platform_message.MessageChain(
                [platform_message.Plain(text=f"写入飞书表格失败: {err}")]
            )


