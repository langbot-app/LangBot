from __future__ import annotations

import asyncio
import base64
import datetime
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class AutoOcrOnImageListener(EventListener):
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

    def _load_rules(self) -> dict[str, Any]:
        raw = self.plugin.get_config().get("rules_json", {})
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

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
                    raise ValueError(
                        f"Failed to download image from url, HTTP {response.status_code}."
                    )
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
            cfg.get(
                "token_endpoint",
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            )
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
            raise RuntimeError(
                f"Token endpoint failed, code={code}, msg={body.get('msg', '')}"
            )

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
        cfg = self.plugin.get_config()
        ocr_endpoint = str(
            cfg.get(
                "ocr_endpoint",
                "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize",
            )
        ).strip()

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
            raise RuntimeError(
                f"OCR endpoint returned error, code={code}, msg={body.get('msg', '')}"
            )

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

    def _extract_fields_by_rules(self, full_text: str, rules: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        fields: dict[str, Any] = {}
        matched_by_rule = False

        constant_fields = rules.get("constant_fields", {})
        if isinstance(constant_fields, dict):
            for k, v in constant_fields.items():
                key = str(k).strip()
                if key:
                    fields[key] = v
                    matched_by_rule = True

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
                        matched_by_rule = True
                        break

        regex_rules = rules.get("regex_extractors", [])
        if isinstance(regex_rules, list):
            regex_fields = self._extract_regex_fields(full_text, regex_rules)
            if regex_fields:
                fields.update(regex_fields)
                matched_by_rule = True

        return fields, matched_by_rule

    def _apply_builtin_fields(
        self,
        fields: dict[str, Any],
        event_ctx: context.EventContext,
        plain_text: str,
        ocr_text: str,
        matched_by_rule: bool,
    ) -> None:
        write_raw_when_no_match = self._get_bool_config("write_raw_text_when_no_match", True)
        raw_field = self._get_str_config("raw_text_field", "Raw Text")
        ocr_field = self._get_str_config("ocr_text_field", "OCR Text")
        sender_field = self._get_str_config("sender_id_field", "Sender ID")
        launcher_field = self._get_str_config("launcher_id_field", "Launcher ID")
        launcher_type_field = self._get_str_config("launcher_type_field", "Launcher Type")
        timestamp_field = self._get_str_config("message_time_field", "Message Time")

        if raw_field and (matched_by_rule or write_raw_when_no_match):
            raw_value = self._truncate_text(plain_text)
            if raw_value:
                fields[raw_field] = raw_value

        if ocr_field and ocr_text:
            fields[ocr_field] = self._truncate_text(ocr_text)

        if sender_field:
            fields[sender_field] = str(event_ctx.event.sender_id)
        if launcher_field:
            fields[launcher_field] = str(event_ctx.event.launcher_id)
        if launcher_type_field:
            fields[launcher_type_field] = str(event_ctx.event.launcher_type)
        if timestamp_field:
            fields[timestamp_field] = datetime.datetime.now(
                datetime.timezone.utc
            ).astimezone().isoformat(timespec="seconds")

    async def _write_record_to_bitable(self, fields: dict[str, Any]) -> tuple[bool, str]:
        app_token = self._get_str_config("bitable_app_token", "")
        table_id = self._get_str_config("bitable_table_id", "")
        if not app_token or not table_id:
            return False, "bitable_app_token/bitable_table_id is empty"

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

        record_id = ""
        data = body.get("data", {}) or {}
        record = data.get("record", {}) or {}
        if isinstance(record, dict):
            record_id = str(record.get("record_id", "")).strip()

        return True, record_id

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

        rules = self._load_rules()
        fields, matched_by_rule = self._extract_fields_by_rules(full_text, rules)
        write_raw_when_no_match = self._get_bool_config("write_raw_text_when_no_match", True)
        if not matched_by_rule and not write_raw_when_no_match:
            return

        self._apply_builtin_fields(fields, event_ctx, plain_text, ocr_text, matched_by_rule)

        if not fields:
            return

        success, detail = await self._write_record_to_bitable(fields)

        if success:
            if self._get_bool_config("reply_on_write", False):
                reply_text = self._get_str_config("reply_text_template", "Recorded to Bitable")
                if reply_text:
                    event_ctx.event.reply_message_chain = platform_message.MessageChain(
                        [platform_message.Plain(text=reply_text)]
                    )

            if self._get_bool_config("prevent_default_on_write", True):
                event_ctx.prevent_default()
                event_ctx.prevent_postorder()
            return

        if self._get_bool_config("reply_on_error", False):
            error_text = f"Bitable write failed: {detail}"
            event_ctx.event.reply_message_chain = platform_message.MessageChain(
                [platform_message.Plain(text=self._truncate_text(error_text, 1000))]
            )
