"""Dify Agent default runner implementation (Phase 1).

Real Dify Service API integration supporting chat, agent, and workflow app types.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
import typing
import uuid
from contextlib import aclosing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    InteractionAction,
    InteractionField,
    InteractionOption,
    InteractionRequest,
    RunnerContext,
    RunnerResult,
)
from langbot_plugin.entities.io.errors import ActionCallError
from pkg.asset_gateway import register_assets
from pkg.dify_client import (
    AsyncDifyClient,
    DifyAPIError,
    DifyConfigError,
    extract_text_from_output,
    process_thinking_content,
)
from pkg.scoped_identity import scoped_identity

logger = logging.getLogger(__name__)

DEFAULT_LANGBOT_ASSET_TOKEN_INPUT = "langbot_asset_run_token"
INTERACTION_STORAGE_PREFIX = "dify.interactions."


def _to_bool(value: typing.Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _to_int(value: typing.Any, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: typing.Any, default: float) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_adapter_params(ctx: RunnerContext) -> dict[str, typing.Any]:
    """Read single-run business params from adapter.extra.params."""
    if ctx.adapter is None:
        return {}
    params = (ctx.adapter.extra or {}).get("params")
    return dict(params) if isinstance(params, dict) else {}


def _is_uuid_string(value: typing.Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _attachment_get(attachment: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(attachment, dict):
        return attachment.get(key, default)
    return getattr(attachment, key, default)


def _content_get(content: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    if isinstance(content, dict):
        return content.get(key, default)
    return getattr(content, key, default)


def _content_type_from_base64(value: typing.Any, default: str) -> str:
    if isinstance(value, str) and value.startswith("data:") and ";base64," in value:
        return value[5 : value.find(";base64,")] or default
    return default


def _decode_content(value: typing.Any) -> bytes | None:
    max_bytes = 10 * 1024 * 1024

    def check_size(size: int) -> None:
        if size > max_bytes:
            raise DifyAPIError("Input attachment exceeds the 10 MiB size limit", code="dify.input_error")

    if isinstance(value, (bytes, bytearray)):
        check_size(len(value))
        return bytes(value)
    if isinstance(value, str):
        start = value.find(",") + 1 if value.startswith("data:") else 0
        # Check before slicing or decoding: decoding itself allocates memory.
        if len(value) - start > 4 * ((max_bytes + 2) // 3) + 4:
            check_size(max_bytes + 1)
        payload = value[start:]
        try:
            decoded = base64.b64decode(payload, validate=True)
        except (ValueError, base64.binascii.Error):
            # Retain the existing plain-text attachment fallback, also bounded.
            check_size(len(value))
            decoded = value.encode("utf-8")
        check_size(len(decoded))
        return decoded
    return None


def _attachments_from_contents(contents: list[typing.Any]) -> list[dict[str, typing.Any]]:
    attachments: list[dict[str, typing.Any]] = []
    for item in contents or []:
        item_type = _content_get(item, "type")
        if item_type == "image_base64":
            content = _content_get(item, "image_base64")
            attachments.append(
                {
                    "type": "image",
                    "name": "image",
                    "content": content,
                    "content_type": _content_type_from_base64(content, "image/jpeg"),
                }
            )
        elif item_type == "file_url":
            attachments.append(
                {
                    "type": "file",
                    "name": _content_get(item, "file_name") or "file",
                    "url": _content_get(item, "file_url"),
                }
            )
        elif item_type == "file_base64":
            content = _content_get(item, "file_base64")
            attachments.append(
                {
                    "type": "file",
                    "name": _content_get(item, "file_name") or "file",
                    "content": content,
                    "content_type": _content_type_from_base64(content, "application/octet-stream"),
                }
            )
    return attachments


def _int_or_none(value: typing.Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(mapping: dict[str, typing.Any], *keys: str) -> int | None:
    for key in keys:
        value = _int_or_none(mapping.get(key))
        if value is not None:
            return value
    return None


def _usage_from_payload(payload: typing.Any) -> dict[str, typing.Any] | None:
    if not isinstance(payload, dict):
        return None

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            usage = metadata.get("usage")
    if not isinstance(usage, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            usage = data.get("usage")
            if not isinstance(usage, dict):
                token_keys = {
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "input_tokens",
                    "output_tokens",
                    "input_count",
                    "output_count",
                    "token_count",
                    "total_count",
                }
                if token_keys.intersection(data):
                    usage = data
    token_keys = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "input_count",
        "output_count",
        "token_count",
        "total_count",
    }
    if not isinstance(usage, dict) and token_keys.intersection(payload):
        usage = payload
    if not isinstance(usage, dict):
        return None

    normalized = dict(usage)
    prompt_tokens = _first_int(usage, "prompt_tokens", "input_tokens", "input_count")
    completion_tokens = _first_int(usage, "completion_tokens", "output_tokens", "output_count")
    total_tokens = _first_int(usage, "total_tokens", "token_count", "total_count")

    if prompt_tokens is not None:
        normalized["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        normalized["completion_tokens"] = completion_tokens
    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens

    return normalized or None


def _form_field_name(field: dict[str, typing.Any]) -> str:
    return str(
        field.get("output_variable_name") or field.get("variable") or field.get("name") or field.get("id") or ""
    ).strip()


def _form_field_options(field: dict[str, typing.Any]) -> list[str]:
    source = field.get("option_source")
    raw_options = source.get("value") if isinstance(source, dict) else None
    if raw_options is None:
        raw_options = field.get("options")
    if isinstance(raw_options, str):
        raw_options = [line.strip() for line in raw_options.splitlines() if line.strip()]
    if not isinstance(raw_options, list):
        return []

    options: list[str] = []
    for option in raw_options:
        if isinstance(option, dict):
            value = option.get("value") or option.get("label") or option.get("name")
        else:
            value = option
        if value is not None and str(value).strip():
            options.append(str(value).strip())
    return options


def _form_field_default(field: dict[str, typing.Any]) -> typing.Any:
    default = field.get("default")
    if isinstance(default, dict) and default.get("type") == "constant":
        return default.get("value")
    return default


def _strip_form_placeholders(content: str) -> str:
    cleaned = re.sub(r"^\s*\{\{#\$output\.[^#{}]+#\}\}\s*$", "", content, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _form_step_descriptions(
    content: str,
    provider_names: list[str],
) -> tuple[dict[str, str], str | None]:
    placeholder_pattern = re.compile(
        r"^[ \t]*\{\{#\$output\.([^#{}\r\n]+)#\}\}[ \t]*$",
        flags=re.MULTILINE,
    )
    matches = list(placeholder_pattern.finditer(content))
    if not matches:
        description = _strip_form_placeholders(content)
        return ({provider_names[0]: description} if provider_names and description else {}), None

    descriptions: dict[str, str] = {}
    segment_start = 0
    known_names = set(provider_names)
    for match in matches:
        provider_name = match.group(1).strip()
        description = content[segment_start : match.start()].strip()
        if provider_name in known_names and description:
            descriptions[provider_name] = description
        segment_start = match.end()

    action_description = content[segment_start:].strip() or None
    return descriptions, action_description


def _interaction_storage_key(interaction_id: str) -> str:
    return f"{INTERACTION_STORAGE_PREFIX}{interaction_id}.json"


class DefaultRunner(Runner):
    """Real Runner for Dify Service API.

    Supports three app types:
    - chat: Chat assistant (including Chatflow)
    - agent: Agent with tool calls
    - workflow: Workflow execution

    Configuration (static, from ctx.config):
    - base-url: Dify API base URL (default: https://api.dify.ai/v1)
    - app-type: Application type (chat/agent/workflow)
    - api-key: Dify API key
    - base-prompt: Default prompt when input is empty
    - timeout: Request timeout in seconds
    - remove-think: Whether to remove thinking tags from output

    Runtime state (from ctx.state):
    - external.conversation_id: Dify conversation ID for stateful sessions

    Runtime params (from ctx.adapter.extra.params):
    - Workflow inputs passed to Dify workflow endpoint
    - Custom variables passed to Dify chat-messages inputs
    """

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Validate and return static configuration.

        Raises DifyConfigError on missing required fields.
        """
        config = ctx.config or {}
        self._get_user_tag(ctx)  # Validate identity before constructing any upstream client.

        base_url = config.get("base-url", "https://api.dify.ai/v1")
        if not base_url:
            raise DifyConfigError("base-url is required", code="dify.config_invalid")

        api_key = config.get("api-key", "")
        if not api_key:
            raise DifyConfigError("api-key is required", code="dify.config_invalid")

        app_type = config.get("app-type", "chat")
        valid_types = ["chat", "chatflow", "agent", "workflow"]
        if app_type not in valid_types:
            raise DifyConfigError(
                f"Invalid app-type: {app_type}. Must be one of {valid_types}",
                code="dify.config_invalid",
            )

        remove_think = config.get("remove-think", False)
        if not isinstance(remove_think, bool):
            raise DifyConfigError("remove-think must be a boolean", code="dify.config_invalid")

        return {
            "base_url": base_url,
            "api_key": api_key,
            "app_type": app_type,
            "base_prompt": config.get("base-prompt", ""),
            "timeout": float(config.get("timeout", 30)),
            "remove_think": remove_think,
            "langbot_assets_enabled": _to_bool(config.get("langbot-assets-enabled"), False),
            "asset_gateway_host": str(config.get("langbot-assets-gateway-host") or "0.0.0.0"),
            "asset_gateway_port": _to_int(config.get("langbot-assets-gateway-port"), 8765),
            "asset_gateway_request_timeout": _to_float(config.get("langbot-assets-gateway-request-timeout"), 60.0),
            "asset_gateway_token_ttl": _to_float(config.get("langbot-assets-token-ttl"), 3600.0),
            "asset_gateway_input_name": str(
                config.get("langbot-assets-input-name") or DEFAULT_LANGBOT_ASSET_TOKEN_INPUT
            ),
        }

    def _get_user_tag(self, ctx: RunnerContext) -> str:
        """Get user identifier for Dify API."""
        source = ctx.config.get("user-id-source", "sender")
        if source not in ("sender", "legacy-session"):
            raise DifyConfigError("user-id-source is invalid", code="dify.config_invalid")
        if source == "legacy-session":
            conversation = ctx.conversation
            if conversation and conversation.launcher_type in ("group", "person"):
                launcher_id = conversation.launcher_id
                if isinstance(launcher_id, str) and launcher_id:
                    return scoped_identity(self, ctx, f"{conversation.launcher_type}_{launcher_id}")
            raise DifyConfigError("user-id-source requires trusted Host identity", code="dify.identity_unavailable")
        actor = ctx.actor
        if actor and actor.actor_id:
            return scoped_identity(self, ctx, f"{actor.actor_type}_{actor.actor_id}")
        raise DifyConfigError(
            "user-id-source=sender requires a trusted Host actor identity",
            code="dify.identity_unavailable",
        )

    def _get_external_conversation_id(self, ctx: RunnerContext) -> str:
        """Get external conversation ID from state or context.

        Priority:
        1. ctx.state.conversation["external.conversation_id"]
        2. Empty string (start new conversation)
        """
        # Priority 1: State (persistent external conversation ID)
        external_conv_id = ctx.state.conversation.get("external.conversation_id")
        if _is_uuid_string(external_conv_id):
            return external_conv_id

        # Host conversation ids are LangBot-local and are not guaranteed to be
        # Dify UUIDs. Passing them to Dify makes first-turn Debug Chat fail.
        return ""

    def _get_or_create_state_id(
        self,
        ctx: RunnerContext,
        key: str,
        prefix: str,
    ) -> tuple[str, bool]:
        """Return a runner-owned external id stored under conversation state."""
        state_value = ctx.state.conversation.get(key)
        if state_value:
            return str(state_value), False
        return f"{prefix}_{uuid.uuid4().hex}", True

    def _get_dify_inputs(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        """Get inputs for Dify API from adapter params.

        Does NOT modify adapter params.
        """
        return _get_adapter_params(ctx)

    async def _create_asset_gateway_registration(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
    ):
        return await register_assets(self, self.get_run_api(ctx), ctx, config)

    async def _prepare_dify_inputs(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
    ):
        inputs = self._get_dify_inputs(ctx)
        if not config["langbot_assets_enabled"]:
            return None, inputs

        registration = await self._create_asset_gateway_registration(ctx, config)
        inputs = dict(inputs)
        inputs[config["asset_gateway_input_name"]] = registration.token
        return registration, inputs

    async def _upload_input_files(
        self,
        ctx: RunnerContext,
        client: AsyncDifyClient,
        user: str,
    ) -> list[dict[str, typing.Any]]:
        """Upload files from input attachments to Dify.

        Returns list of Dify file references.
        """
        uploaded_files: list[dict[str, typing.Any]] = []

        attachments = list(ctx.input.attachments or [])
        if not any(_attachment_get(attachment, "content") for attachment in attachments):
            attachments.extend(_attachments_from_contents(ctx.input.contents))

        for attachment in attachments:
            try:
                file_bytes = _decode_content(_attachment_get(attachment, "content"))
                downloaded_type = None
                if file_bytes is None and _attachment_get(attachment, "url"):
                    file_bytes, downloaded_type = await client.download_file(_attachment_get(attachment, "url"))
                if not file_bytes:
                    raise DifyAPIError(
                        f"Input attachment {_attachment_get(attachment, 'name', 'file')} has no uploadable content",
                        code="dify.input_error",
                    )

                file_name = _attachment_get(attachment, "name") or "file"
                content_type = (
                    _attachment_get(attachment, "content_type")
                    or _attachment_get(attachment, "mime_type")
                    or downloaded_type
                    or "application/octet-stream"
                )

                # Determine Dify file type from content type
                if content_type.startswith("image/"):
                    file_type = "image"
                elif content_type.startswith("audio/"):
                    file_type = "audio"
                elif content_type.startswith("video/"):
                    file_type = "video"
                else:
                    file_type = "document"

                result = await client.upload_file(file_name, file_bytes, content_type, user)
                file_id = result.get("id")

                if file_id:
                    uploaded_files.append(
                        {
                            "type": file_type,
                            "transfer_method": "local_file",
                            "upload_file_id": file_id,
                        }
                    )
                else:
                    raise DifyAPIError(
                        f"Dify file upload response missing file id for {file_name}",
                        code="dify.input_error",
                    )
            except DifyAPIError as e:
                if e.code == "dify.input_error":
                    raise
                raise DifyAPIError(
                    f"Failed to upload input attachment {_attachment_get(attachment, 'name', 'file')}: {e.message}",
                    code="dify.input_error",
                ) from None
            except Exception as e:
                raise DifyAPIError(
                    f"Failed to upload input attachment {_attachment_get(attachment, 'name', 'file')}: {e}",
                    code="dify.input_error",
                ) from None

        return uploaded_files

    def _get_input_text(self, ctx: RunnerContext, base_prompt: str) -> str:
        """Get text input, fallback to base_prompt if empty."""
        text = ctx.input.to_text()
        if not text:
            return base_prompt
        return text

    async def _store_interaction_continuation(
        self,
        ctx: RunnerContext,
        continuation: dict[str, typing.Any],
    ) -> None:
        interaction_id = str(continuation["interaction_id"])
        continuation = dict(continuation, owner=self._continuation_owner(ctx))
        continuation.setdefault("expires_at", time.time() + 3600)
        payload = json.dumps(continuation, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await self.get_run_api(ctx).set_plugin_storage(_interaction_storage_key(interaction_id), payload)

    async def _load_interaction_continuation(
        self,
        ctx: RunnerContext,
        interaction_id: str,
    ) -> dict[str, typing.Any]:
        key = _interaction_storage_key(interaction_id)
        try:
            payload = await self.get_run_api(ctx).get_plugin_storage(key)
        except (KeyError, ActionCallError) as exc:
            if isinstance(exc, ActionCallError):
                message = str(exc)
                while message.startswith("ActionCallError: "):
                    message = message.removeprefix("ActionCallError: ")
                if message != f"Storage with key {key} not found":
                    raise
            raise DifyAPIError(
                "The Dify human-input request is no longer pending",
                code="dify.interaction_not_found",
            ) from exc
        continuation = json.loads(payload.decode("utf-8"))
        if not isinstance(continuation, dict) or continuation.get("interaction_id") != interaction_id:
            raise DifyAPIError(
                "The Dify human-input continuation is invalid",
                code="dify.interaction_invalid",
            )
        if continuation.get("version") != 1:
            raise DifyAPIError(
                "The Dify human-input continuation version is unsupported",
                code="dify.interaction_invalid",
            )
        if continuation.get("consumed") or continuation.get("expires_at", 0) < time.time():
            raise DifyAPIError("Dify continuation expired or already consumed", code="dify.interaction_not_found")
        owner = self._continuation_owner(ctx)
        stored_owner = continuation.get("owner")
        if stored_owner != owner:
            if stored_owner != self._legacy_continuation_owner(ctx):
                raise DifyAPIError("Dify continuation belongs to another context", code="dify.interaction_invalid")
            # One-time migration: a continuation stored before identity resolution moved
            # to task-local bindings is accepted and re-written with the current owner.
            # No long-term dual-rule compatibility branch beyond this upgrade path.
            continuation = dict(continuation, owner=owner)
        return continuation

    def _continuation_subject(self, ctx):
        conversation = ctx.conversation
        return json.dumps(
            [
                getattr(conversation, "conversation_id", None),
                getattr(conversation, "launcher_type", None),
                getattr(conversation, "launcher_id", None),
                getattr(ctx.actor, "actor_id", None),
                (ctx.config or {}).get("base-url"),
            ],
            separators=(",", ":"),
        )

    def _continuation_owner(self, ctx):
        return scoped_identity(self, ctx, self._continuation_subject(ctx))

    def _legacy_continuation_owner(self, ctx):
        """Owner computed before identity resolution moved to task-local bindings.

        Used only to accept continuations persisted by the previous release so an
        in-flight human-input request survives the upgrade; the record is re-written
        with the current owner on the next store.
        """
        binding = getattr(getattr(self, "_plugin_runtime_handler", None), "bound_action_context", None)
        subject = self._continuation_subject(ctx)
        if binding is not None:
            scope = [binding.instance_uuid, binding.workspace_uuid, binding.installation_uuid]
        else:
            workspace = getattr(ctx.conversation, "workspace_id", None)
            if not workspace:
                return subject
            scope = [workspace]
        encoded = json.dumps([scope, subject], ensure_ascii=False, separators=(",", ":")).encode()
        return "lb_" + hashlib.sha256(encoded).hexdigest()

    async def _delete_interaction_continuation(self, ctx: RunnerContext, interaction_id: str) -> None:
        await self.get_run_api(ctx).delete_plugin_storage(_interaction_storage_key(interaction_id))

    @staticmethod
    def _request_from_continuation(continuation: dict[str, typing.Any]) -> InteractionRequest:
        fields = [InteractionField.model_validate(item) for item in continuation.get("current_fields") or []]
        actions = [InteractionAction.model_validate(item) for item in continuation.get("interaction_actions") or []]
        if continuation.get("phase") == "field":
            actions = []
        kind = (
            "confirmation" if actions and not fields else "choice" if fields and fields[0].type == "select" else "form"
        )
        if "field_descriptions" in continuation:
            field_descriptions = (
                continuation.get("field_descriptions")
                if isinstance(continuation.get("field_descriptions"), dict)
                else {}
            )
            description = (
                field_descriptions.get(fields[0].id)
                if continuation.get("phase") == "field" and fields
                else continuation.get("action_description")
            )
        else:
            description = continuation.get("description")
        fallback_text = str(continuation.get("fallback_text") or "Human input is required.")
        if fields:
            field = fields[0]
            field_lines = [str(continuation.get("title") or "Human input required"), field.label]
            if description:
                field_lines.insert(1, str(description))
            if field.options:
                field_lines.append("Options: " + ", ".join(option.label for option in field.options))
            fallback_text = "\n".join(field_lines)
        return InteractionRequest(
            interaction_id=str(continuation["interaction_id"]),
            kind=kind,
            title=str(continuation.get("title") or "Human input required"),
            description=description,
            fields=fields,
            actions=actions,
            fallback_text=fallback_text,
        )

    async def _advance_field_interaction(
        self,
        ctx: RunnerContext,
        continuation: dict[str, typing.Any],
        submission: typing.Any,
    ) -> RunnerResult:
        field_map = continuation.get("field_map") if isinstance(continuation.get("field_map"), dict) else {}
        inputs = dict(continuation.get("default_inputs") or {})
        current_fields = [InteractionField.model_validate(item) for item in continuation.get("current_fields") or []]
        for field_id, value in submission.values.items():
            provider_name = field_map.get(field_id)
            if provider_name:
                inputs[str(provider_name)] = value
        for field in current_fields:
            provider_name = field_map.get(field.id)
            if field.required and provider_name and inputs.get(str(provider_name)) in (None, "", []):
                raise DifyAPIError(
                    f"Dify human-input field is required: {field.label}",
                    code="dify.interaction_invalid",
                )

        old_interaction_id = str(continuation["interaction_id"])
        remaining_fields = list(continuation.get("remaining_fields") or [])
        continuation = dict(continuation)
        continuation["interaction_id"] = f"dify-{uuid.uuid4().hex}"
        continuation["default_inputs"] = inputs
        if remaining_fields:
            continuation["phase"] = "field"
            continuation["current_fields"] = [remaining_fields.pop(0)]
            continuation["remaining_fields"] = remaining_fields
        else:
            continuation["phase"] = "action"
            continuation["current_fields"] = []
            continuation["remaining_fields"] = []

        request = self._request_from_continuation(continuation)
        await self._store_interaction_continuation(ctx, continuation)
        await self._delete_interaction_continuation(ctx, old_interaction_id)
        return RunnerResult.interaction_requested(ctx.run_id, request)

    def _build_interaction_request(
        self,
        reason: dict[str, typing.Any],
        workflow_run_id: str,
        user: str,
    ) -> tuple[InteractionRequest, dict[str, typing.Any]]:
        form_token = str(reason.get("form_token") or "").strip()
        if not form_token or not workflow_run_id:
            raise DifyAPIError(
                "Dify human-input event is missing continuation identifiers",
                code="dify.response_invalid",
            )

        interaction_id = f"dify-{uuid.uuid4().hex}"
        fields: list[InteractionField] = []
        field_map: dict[str, str] = {}
        resolved_defaults = reason.get("resolved_default_values")
        default_inputs = dict(resolved_defaults) if isinstance(resolved_defaults, dict) else {}
        raw_fields = reason.get("inputs") if isinstance(reason.get("inputs"), list) else []
        for index, raw_field in enumerate(raw_fields):
            if not isinstance(raw_field, dict):
                continue
            provider_name = _form_field_name(raw_field)
            if not provider_name:
                continue
            field_id = f"field_{index + 1}"
            field_map[field_id] = provider_name
            provider_type = str(raw_field.get("type") or "text").lower()
            field_type = {
                "paragraph": "textarea",
                "textarea": "textarea",
                "select": "select",
                "number": "number",
                "checkbox": "boolean",
                "boolean": "boolean",
                "file": "file",
                "file-list": "file",
            }.get(provider_type, "text")
            option_values = _form_field_options(raw_field) if field_type == "select" else []
            if field_type == "select" and not option_values:
                field_type = "text"
            default = default_inputs.get(provider_name, _form_field_default(raw_field))
            if default not in (None, ""):
                default_inputs[provider_name] = default
            fields.append(
                InteractionField(
                    id=field_id,
                    label=str(raw_field.get("label") or raw_field.get("title") or provider_name),
                    type=field_type,
                    required=bool(raw_field.get("required", True)),
                    options=[InteractionOption(value=value, label=value) for value in option_values],
                    placeholder=raw_field.get("placeholder"),
                    default=default,
                )
            )

        actions: list[InteractionAction] = []
        action_map: dict[str, str] = {}
        raw_actions = reason.get("actions") if isinstance(reason.get("actions"), list) else []
        for index, raw_action in enumerate(raw_actions):
            if not isinstance(raw_action, dict):
                continue
            provider_action_id = str(raw_action.get("id") or "").strip()
            if not provider_action_id:
                continue
            action_id = f"action_{index + 1}"
            action_map[action_id] = provider_action_id
            actions.append(
                InteractionAction(
                    id=action_id,
                    label=str(raw_action.get("title") or raw_action.get("label") or provider_action_id),
                )
            )
        if not actions:
            action_map["continue"] = ""
            actions.append(InteractionAction(id="continue", label="Continue", style="primary"))

        node_title = str(reason.get("node_title") or "Human input required")
        form_content = str(reason.get("form_content") or "")
        provider_names = [field_map[field.id] for field in fields if field.id in field_map]
        provider_descriptions, action_description = _form_step_descriptions(form_content, provider_names)
        field_descriptions = {
            field_id: provider_descriptions[provider_name]
            for field_id, provider_name in field_map.items()
            if provider_name in provider_descriptions
        }
        description = _strip_form_placeholders(form_content)
        fallback_lines = [f"[Human Input Required] {node_title}"]
        if description:
            fallback_lines.extend(["", description])
        for field in fields:
            if field.options:
                choices = ", ".join(option.label for option in field.options)
                fallback_lines.append(f"{field.label}: {choices}")
            else:
                fallback_lines.append(f"{field.label}: required input")
        if actions:
            fallback_lines.append("Actions: " + ", ".join(action.label for action in actions))

        continuation = {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": form_token,
            "workflow_run_id": workflow_run_id,
            "user": user,
            "field_map": field_map,
            "action_map": action_map,
            "default_inputs": default_inputs,
            "title": node_title,
            "description": description or None,
            "field_descriptions": field_descriptions,
            "action_description": action_description,
            "fallback_text": "\n".join(fallback_lines),
            "phase": "field" if fields else "action",
            "current_fields": [fields[0].model_dump(mode="json")] if fields else [],
            "remaining_fields": [field.model_dump(mode="json") for field in fields[1:]],
            "interaction_actions": [action.model_dump(mode="json") for action in actions],
        }
        request = self._request_from_continuation(continuation)
        return request, continuation

    async def _interaction_result_for_pause(
        self,
        ctx: RunnerContext,
        event: dict[str, typing.Any],
        user: str,
    ) -> RunnerResult | None:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        workflow_run_id = str(data.get("workflow_run_id") or "").strip()
        reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
        reason = next(
            (item for item in reasons if isinstance(item, dict) and item.get("TYPE") == "human_input_required"),
            None,
        )
        if reason is None:
            return None
        request, continuation = self._build_interaction_request(reason, workflow_run_id, user)
        await self._store_interaction_continuation(ctx, continuation)
        return RunnerResult.interaction_requested(ctx.run_id, request)

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run the Dify agent.

        Streams RunnerResult.message_delta chunks and final run_completed.
        """
        try:
            config = self._validate_config(ctx)
        except DifyConfigError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return

        client = AsyncDifyClient(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=config["timeout"],
        )

        user = self._get_user_tag(ctx)
        input_text = self._get_input_text(ctx, config["base_prompt"])
        remove_think = config["remove_think"]

        asset_registration = None
        try:
            if ctx.event.event_type == "interaction.submitted":
                if ctx.input.interaction is None:
                    raise DifyAPIError(
                        "interaction.submitted event is missing its validated submission",
                        code="dify.interaction_invalid",
                    )
                async for result in self._resume_workflow(ctx, client, ctx.input.interaction, remove_think):
                    yield result
                return
            if ctx.input.interaction is not None:
                raise DifyAPIError(
                    "Interaction submission is only valid for interaction.submitted events",
                    code="dify.interaction_invalid",
                )

            # Upload files if present. Multimodal inputs must not silently
            # degrade to text-only when the provider upload path fails.
            files = await self._upload_input_files(ctx, client, user)

            # Get inputs from params (read-only, do not modify), optionally adding
            # the run-scoped LangBot asset token expected by Dify MCP tools.
            asset_registration, inputs = await self._prepare_dify_inputs(ctx, config)

            # Get conversation_id from state (not from config!)
            conversation_id = self._get_external_conversation_id(ctx)

            app_type = config["app_type"]

            if app_type == "workflow":
                # Workflow mode - uses different endpoint
                async for result in self._run_workflow(ctx, client, inputs, input_text, user, files, remove_think):
                    yield result
            else:
                # Chat or Agent mode - uses chat-messages endpoint
                async for result in self._run_chat_or_agent(
                    ctx, client, inputs, input_text, user, conversation_id, files, app_type, remove_think
                ):
                    yield result
        except DifyAPIError as e:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=e.message,
                code=e.code,
            )
            return
        except Exception as e:
            logger.exception(f"Dify runner unexpected error: {e}")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Dify runner error: {e}",
                code="dify.unexpected_error",
            )
            return
        finally:
            if asset_registration is not None:
                await asset_registration.stop()

    async def _run_chat_or_agent(
        self,
        ctx: RunnerContext,
        client: AsyncDifyClient,
        inputs: dict[str, typing.Any],
        input_text: str,
        user: str,
        conversation_id: str,
        files: list[dict[str, typing.Any]],
        app_type: str,
        remove_think: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run chat or agent mode.

        Streams message_delta chunks and handles agent-specific events.
        """
        pending_content = ""
        mode = "basic"  # basic or workflow mode in chat
        message_count = 0
        has_response = False
        final_conversation_id = conversation_id
        usage: dict[str, typing.Any] | None = None
        workflow_run_id = ""

        async for event in client.chat_messages(
            inputs=inputs,
            query=input_text,
            user=user,
            conversation_id=conversation_id,
            files=files,
        ):
            event_type = event.get("event", "")
            logger.debug(f"Dify {app_type} event: {event_type}")
            usage = _usage_from_payload(event) or usage

            if event_type in {
                "workflow_started",
                "node_started",
                "node_finished",
                "workflow_finished",
                "workflow_paused",
            }:
                mode = "workflow"
            if event_type == "workflow_started":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                workflow_run_id = str(data.get("workflow_run_id") or workflow_run_id)

            if event_type == "error":
                raise DifyAPIError(
                    f"Dify API error: {event.get('message', 'Unknown error')}",
                    code="dify.api_error",
                )

            # Track conversation_id for stateful session
            if event.get("conversation_id"):
                final_conversation_id = event["conversation_id"]

            # Handle different event types based on app_type and mode
            if mode == "workflow" and event_type == "node_finished":
                if event.get("data", {}).get("node_type") == "answer":
                    answer = extract_text_from_output(event.get("data", {}).get("outputs", {}).get("answer"))
                    pending_content = answer
                    content, _ = process_thinking_content(answer, remove_think)
                    if content:
                        has_response = True
                        yield RunnerResult.message_delta(ctx.run_id, MessageChunk(role="assistant", content=content))

            elif mode == "workflow" and event_type == "workflow_paused":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                if workflow_run_id and not data.get("workflow_run_id"):
                    event = dict(event)
                    event["data"] = {**data, "workflow_run_id": workflow_run_id}
                if pending_content:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    if content:
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=content, is_final=True),
                        )
                if final_conversation_id:
                    yield RunnerResult.state_updated(
                        ctx.run_id,
                        "external.conversation_id",
                        final_conversation_id,
                        scope="conversation",
                    )
                interaction_result = await self._interaction_result_for_pause(ctx, event, user)
                if interaction_result is None:
                    raise DifyAPIError(
                        "Dify paused the workflow without a supported reason",
                        code="dify.response_invalid",
                    )
                yield interaction_result
                return

            elif event_type == "message" or event_type == "agent_message":
                # Accumulate text chunks
                answer = event.get("answer", "")
                # Dify deployments send either deltas or cumulative snapshots.
                if pending_content and len(answer) > len(pending_content) and answer.startswith(pending_content):
                    pending_content = answer
                else:
                    pending_content += answer
                message_count += 1
                if message_count % 8 == 0:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    if content:
                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id, MessageChunk(role="assistant", content=content, is_final=False)
                        )

            elif event_type == "message_end":
                # Final message for chat mode
                if pending_content:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    has_response = True
                    yield RunnerResult.message_delta(
                        ctx.run_id, MessageChunk(role="assistant", content=content, is_final=True)
                    )
                pending_content = ""

            elif event_type == "agent_thought" and app_type == "agent":
                # Agent thought events - handle tool calls
                tool = event.get("tool", "")
                observation = event.get("observation", "")

                # Skip tool result observations
                if tool and observation:
                    continue

                # Yield accumulated content before tool call
                if pending_content:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    if content:
                        has_response = True
                        yield RunnerResult.message_delta(ctx.run_id, MessageChunk(role="assistant", content=content))
                    pending_content = ""

                # Report tool call as message_delta with tool_calls
                if tool:
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content="",
                            tool_calls=[
                                {
                                    "id": event.get("id", str(uuid.uuid4())),
                                    "type": "function",
                                    "function": {
                                        "name": tool,
                                        "arguments": json.dumps({}),
                                    },
                                }
                            ],
                        ),
                    )

            elif event_type == "message_file":
                # Handle image/file output from agent
                if event.get("type") == "image" and event.get("belongs_to") == "assistant":
                    image_url = event.get("url", "")
                    if image_url:
                        # Handle relative URLs
                        if not image_url.startswith("http"):
                            base_url = client.base_url
                            if base_url.endswith("/v1"):
                                base_url = base_url[:-3]
                            image_url = base_url + image_url

                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(
                                role="assistant",
                                content=[{"type": "image_url", "image_url": {"url": image_url}}],
                            ),
                        )

            elif event_type == "workflow_finished":
                mode = "workflow"
                data = event.get("data", {})
                if data.get("error"):
                    raise DifyAPIError(f"Dify workflow error: {data['error']}", code="dify.api_error")

        # Handle any remaining pending content
        if pending_content:
            content, _ = process_thinking_content(pending_content, remove_think)
            if content:
                has_response = True
                yield RunnerResult.message_delta(
                    ctx.run_id, MessageChunk(role="assistant", content=content, is_final=True)
                )

        if not has_response:
            raise DifyAPIError(
                "Dify API returned no response",
                code="dify.api_error",
            )

        # Update state with conversation_id for next run (scoped state)
        if final_conversation_id:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.conversation_id",
                final_conversation_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)

    async def _run_workflow(
        self,
        ctx: RunnerContext,
        client: AsyncDifyClient,
        inputs: dict[str, typing.Any],
        input_text: str,
        user: str,
        files: list[dict[str, typing.Any]],
        remove_think: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run workflow mode.

        Streams message_delta chunks and handles workflow-specific events.

        Workflow legacy inputs are derived from context:
        - langbot_user_message_text: input_text
        - langbot_session_id: ctx.conversation.session_id or ctx.run_id
        - langbot_conversation_id: from state or ctx.conversation
        - langbot_msg_create_time: adapter params msg_create_time
        """
        # Derive Dify workflow compatibility variables from runner-owned state,
        # not LangBot's conversation/session ids.
        session_id, session_created = self._get_or_create_state_id(
            ctx,
            "external.workflow_session_id",
            "dify_session",
        )
        external_conv_id, conversation_created = self._get_or_create_state_id(
            ctx,
            "external.workflow_conversation_id",
            "dify_conversation",
        )

        msg_create_time = inputs.get("msg_create_time")

        workflow_inputs = {
            "langbot_user_message_text": input_text,
            "langbot_session_id": session_id,
            "langbot_conversation_id": external_conv_id,
        }
        if msg_create_time:
            workflow_inputs["langbot_msg_create_time"] = msg_create_time

        # Merge with user params (user params take precedence)
        workflow_inputs.update(inputs)

        pending_content = ""
        has_response = False
        ignored_events = ["workflow_started"]
        usage: dict[str, typing.Any] | None = None
        workflow_run_id = ""

        async for event in client.workflow_run(
            inputs=workflow_inputs,
            user=user,
            files=files,
        ):
            event_type = event.get("event", "")
            logger.debug(f"Dify workflow event: {event_type}")
            usage = _usage_from_payload(event) or usage

            if event_type == "workflow_started":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                workflow_run_id = str(data.get("workflow_run_id") or workflow_run_id)

            if event_type == "error":
                raise DifyAPIError(
                    f"Dify workflow error: {event.get('message', 'Unknown error')}",
                    code="dify.api_error",
                )

            if event_type in ignored_events:
                continue

            if event_type == "node_started":
                data = event.get("data", {})
                node_type = data.get("node_type", "")
                if node_type in ["start", "end"]:
                    continue

                # Node progress is telemetry, not user-visible message content.
                yield RunnerResult.tool_call_started(
                    ctx.run_id,
                    tool_call_id=str(data.get("node_id") or uuid.uuid4()),
                    tool_name=str(data.get("title") or node_type),
                    parameters={},
                )

            elif event_type == "text_chunk":
                # Streaming text output from workflow
                text = event.get("data", {}).get("text", "")
                pending_content += text

            elif event_type == "node_finished":
                data = event.get("data", {})
                if data.get("node_type") == "answer":
                    answer = extract_text_from_output(data.get("outputs", {}).get("answer"))
                    if answer:
                        content, _ = process_thinking_content(answer, remove_think)
                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=content, is_final=True),
                        )

            elif event_type == "workflow_paused":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                if workflow_run_id and not data.get("workflow_run_id"):
                    event = dict(event)
                    event["data"] = {**data, "workflow_run_id": workflow_run_id}
                if pending_content:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    if content:
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=content, is_final=True),
                        )
                if session_created:
                    yield RunnerResult.state_updated(
                        ctx.run_id,
                        "external.workflow_session_id",
                        session_id,
                        scope="conversation",
                    )
                if conversation_created:
                    yield RunnerResult.state_updated(
                        ctx.run_id,
                        "external.workflow_conversation_id",
                        external_conv_id,
                        scope="conversation",
                    )
                interaction_result = await self._interaction_result_for_pause(ctx, event, user)
                if interaction_result is None:
                    raise DifyAPIError(
                        "Dify paused the workflow without a supported reason",
                        code="dify.response_invalid",
                    )
                yield interaction_result
                return

            elif event_type == "workflow_finished":
                data = event.get("data", {})
                if data.get("error"):
                    raise DifyAPIError(f"Dify workflow error: {data['error']}", code="dify.api_error")

                # Get final output
                summary = extract_text_from_output(data.get("outputs", {}).get("summary", ""))
                if summary:
                    content, _ = process_thinking_content(summary, remove_think)
                    has_response = True
                    yield RunnerResult.message_delta(
                        ctx.run_id, MessageChunk(role="assistant", content=content, is_final=True)
                    )

        # Handle remaining pending content
        if pending_content:
            content, _ = process_thinking_content(pending_content, remove_think)
            if content:
                has_response = True
                yield RunnerResult.message_delta(
                    ctx.run_id, MessageChunk(role="assistant", content=content, is_final=True)
                )

        if not has_response:
            raise DifyAPIError(
                "Dify workflow returned no response",
                code="dify.api_error",
            )

        if session_created:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.workflow_session_id",
                session_id,
                scope="conversation",
            )
        if conversation_created:
            yield RunnerResult.state_updated(
                ctx.run_id,
                "external.workflow_conversation_id",
                external_conv_id,
                scope="conversation",
            )

        yield RunnerResult.run_completed(ctx.run_id, usage=usage)

    async def _resume_workflow(self, ctx, client, submission, remove_think):
        active = getattr(self, "_active_resumes", None)
        if active is None:
            active = self._active_resumes = set()
        from langbot_plugin.api.proxies.invocation import current_binding

        handler = getattr(self, "_plugin_runtime_handler", None)
        # Same binding chain as scoped_identity, so the owner and the concurrency
        # key can never disagree within one invocation.
        binding = current_binding(handler) if handler is not None else None
        if binding is None:
            binding = getattr(handler, "bound_action_context", None)
        key = (binding, self._continuation_owner(ctx), str(submission.interaction_id))
        if key in active:
            raise DifyAPIError("Dify continuation is already being resumed", code="dify.interaction_invalid")
        active.add(key)
        try:
            async with aclosing(self._resume_workflow_once(ctx, client, submission, remove_think)) as stream:
                async for result in stream:
                    yield result
        finally:
            active.remove(key)

    async def _resume_workflow_once(
        self,
        ctx: RunnerContext,
        client: AsyncDifyClient,
        submission: typing.Any,
        remove_think: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        interaction_id = str(submission.interaction_id)
        continuation = await self._load_interaction_continuation(ctx, interaction_id)
        if continuation.get("phase") == "field":
            yield await self._advance_field_interaction(ctx, continuation, submission)
            return
        field_map = continuation.get("field_map") if isinstance(continuation.get("field_map"), dict) else {}
        action_map = continuation.get("action_map") if isinstance(continuation.get("action_map"), dict) else {}
        inputs = dict(continuation.get("default_inputs") or {})
        for field_id, value in submission.values.items():
            provider_name = field_map.get(field_id)
            if provider_name:
                inputs[str(provider_name)] = value
        action_id = submission.action_id or ""
        if action_id not in action_map:
            raise DifyAPIError(
                "Dify human-input action is missing or invalid",
                code="dify.interaction_invalid",
            )
        action = action_map[action_id]
        # Persist consumption BEFORE the external effect. An ambiguous failure
        # remains consumed, never silently retries an approval at the vendor.
        continuation["consumed"] = True
        await self._store_interaction_continuation(ctx, continuation)

        pending_content = ""
        has_response = False
        terminal = False
        usage: dict[str, typing.Any] | None = None
        async for event in client.workflow_submit(
            form_token=str(continuation["form_token"]),
            workflow_run_id=str(continuation["workflow_run_id"]),
            inputs=inputs,
            user=str(continuation["user"]),
            action=str(action),
        ):
            event_type = event.get("event", "")
            usage = _usage_from_payload(event) or usage
            if event_type == "error":
                raise DifyAPIError(
                    f"Dify workflow error: {event.get('message', 'Unknown error')}",
                    code="dify.api_error",
                )
            if event_type in {"message", "agent_message", "text_chunk"}:
                chunk = (
                    str(event.get("answer") or "")
                    if event_type != "text_chunk"
                    else str(event.get("data", {}).get("text") or "")
                )
                if len(pending_content) + len(chunk) > 1024 * 1024:
                    raise DifyAPIError("Dify response exceeds the runtime limit", code="dify.response_limit")
                pending_content += chunk
            elif event_type == "node_finished":
                data = event.get("data", {})
                if data.get("node_type") == "answer":
                    answer = extract_text_from_output(data.get("outputs", {}).get("answer"))
                    if answer:
                        content, _ = process_thinking_content(answer, remove_think)
                        has_response = True
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=content, is_final=True),
                        )
            elif event_type == "workflow_paused":
                if pending_content:
                    content, _ = process_thinking_content(pending_content, remove_think)
                    if content:
                        yield RunnerResult.message_delta(
                            ctx.run_id,
                            MessageChunk(role="assistant", content=content, is_final=True),
                        )
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                if not data.get("workflow_run_id"):
                    event = dict(event)
                    event["data"] = {
                        **data,
                        "workflow_run_id": str(continuation["workflow_run_id"]),
                    }
                interaction_result = await self._interaction_result_for_pause(
                    ctx,
                    event,
                    str(continuation["user"]),
                )
                if interaction_result is None:
                    raise DifyAPIError(
                        "Dify paused the workflow without a supported reason",
                        code="dify.response_invalid",
                    )
                await self._delete_interaction_continuation(ctx, interaction_id)
                yield interaction_result
                return
            elif event_type == "workflow_finished":
                data = event.get("data", {})
                if data.get("error"):
                    raise DifyAPIError(f"Dify workflow error: {data['error']}", code="dify.api_error")
                summary = extract_text_from_output(data.get("outputs", {}).get("summary", ""))
                if summary:
                    content, _ = process_thinking_content(summary, remove_think)
                    has_response = True
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(role="assistant", content=content, is_final=True),
                    )
                terminal = True

        if pending_content and not has_response:
            content, _ = process_thinking_content(pending_content, remove_think)
            if content:
                has_response = True
                yield RunnerResult.message_delta(
                    ctx.run_id,
                    MessageChunk(role="assistant", content=content, is_final=True),
                )
        if not terminal:
            raise DifyAPIError(
                "Dify workflow resume ended before a terminal event",
                code="dify.response_invalid",
            )
        if not has_response:
            raise DifyAPIError(
                "Dify workflow returned no response after human input",
                code="dify.api_error",
            )
        await self._delete_interaction_continuation(ctx, interaction_id)
        yield RunnerResult.run_completed(ctx.run_id, usage=usage)
