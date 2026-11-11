from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLUGIN_RUNTIME_CONTROL_TOKEN_ENV = "LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN"
PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER = "X-LangBot-Plugin-Runtime-Token"
PLUGIN_DEBUG_KEY_ENV = "PLUGIN_DEBUG_KEY"
PLUGIN_DEBUG_KEY_HEADER = "X-LangBot-Plugin-Debug-Key"
PLUGIN_REGISTRATION_CAPABILITY_ENV = "LANGBOT_PLUGIN_REGISTRATION_CAPABILITY"
PLUGIN_REGISTRATION_CAPABILITY_HEADER = "X-LangBot-Plugin-Registration-Capability"
PLUGIN_RUNTIME_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"
PLUGIN_FILE_STORAGE_DIR_ENV = "LANGBOT_PLUGIN_FILE_STORAGE_DIR"
RUNTIME_SECRET_MIN_LENGTH = 32
WORKSPACE_DEBUG_TOKEN_TTL_SECONDS = int(
    os.environ.get("LANGBOT_WORKSPACE_DEBUG_TOKEN_TTL_SECONDS", 2 * 60 * 60)
)

_SECRET_PATTERN = re.compile(r"^[^\s]{32,}$")


def validate_runtime_secret(value: str, *, name: str) -> str:
    """Validate a control/debug secret without ever returning it in errors."""

    secret = str(value or "").strip()
    if not _SECRET_PATTERN.fullmatch(secret):
        raise ValueError(
            f"{name} must be a non-whitespace secret of at least "
            f"{RUNTIME_SECRET_MIN_LENGTH} characters"
        )
    return secret


@dataclass(frozen=True, slots=True)
class WorkspaceDebugCredential:
    token: str
    expires_at: str


class WorkspaceDebugTokenStore:
    """Issue one random debug credential per Workspace and rotation window."""

    def __init__(
        self,
        *,
        clock=time.time,
        ttl_seconds: int | None = None,
        storage_path: str | Path | None = None,
    ):
        self._clock = clock
        self._ttl_seconds = (
            WORKSPACE_DEBUG_TOKEN_TTL_SECONDS if ttl_seconds is None else ttl_seconds
        )
        self._credentials: dict[str, tuple[str, float, Any]] = {}
        if storage_path is None:
            storage_dir = Path(
                os.environ.get(PLUGIN_FILE_STORAGE_DIR_ENV)
                or Path.home() / ".langbot" / "runtime"
            )
            self._storage_path = storage_dir / "workspace_debug_credentials.json"
        else:
            self._storage_path = Path(storage_path)
        self._load_persisted()

    @staticmethod
    def _format_time(timestamp: float) -> str:
        return (
            datetime.fromtimestamp(timestamp, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _load_persisted(self) -> None:
        if not self._storage_path.is_file():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = float(self._clock())
            from langbot_plugin.entities.io.context import ActionContext

            for workspace_uuid, item in data.items():
                token = str(item.get("token") or "")
                expires = float(item.get("expires") or 0.0)
                binding_dict = item.get("binding")
                if token and isinstance(binding_dict, dict):
                    # In local development, preserve credentials across restarts
                    if expires <= now:
                        expires = now + self._ttl_seconds
                    binding = ActionContext.model_validate(binding_dict)
                    self._credentials[workspace_uuid] = (token, expires, binding)
        except Exception as e:
            logger.warning("Failed to load persisted debug credentials: %s", e)

    def _save_persisted(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for workspace_uuid, (token, expires, binding) in self._credentials.items():
                binding_data = (
                    binding.model_dump()
                    if hasattr(binding, "model_dump")
                    else getattr(binding, "__dict__", {})
                )
                data[workspace_uuid] = {
                    "token": token,
                    "expires": expires,
                    "binding": binding_data,
                }
            temp_path = self._storage_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self._storage_path)
        except Exception as e:
            logger.warning("Failed to persist debug credentials: %s", e)

    def issue(self, binding: Any) -> WorkspaceDebugCredential:
        workspace_uuid = str(getattr(binding, "workspace_uuid", "") or "").strip()
        if not workspace_uuid:
            raise ValueError("Workspace debug credentials require Workspace context")
        now = float(self._clock())
        token, expires, existing_binding = self._credentials.get(
            workspace_uuid, ("", 0.0, None)
        )
        if existing_binding is not None and (
            getattr(existing_binding, "instance_uuid", None)
            != getattr(binding, "instance_uuid", None)
            or getattr(existing_binding, "placement_generation", None)
            != getattr(binding, "placement_generation", None)
        ):
            token, expires = "", 0.0
        if not token or now >= expires:
            env_token = str(os.environ.get(PLUGIN_DEBUG_KEY_ENV) or "").strip()
            if env_token and len(env_token) >= RUNTIME_SECRET_MIN_LENGTH:
                token = env_token
            else:
                token = secrets.token_urlsafe(48)
            expires = now + self._ttl_seconds
        self._credentials[workspace_uuid] = (token, expires, binding)
        self._save_persisted()
        return WorkspaceDebugCredential(
            token=token, expires_at=self._format_time(expires)
        )

    def binding_for_token(self, supplied_token: str) -> Any | None:
        supplied_token = str(supplied_token or "")
        if not supplied_token:
            return None
        now = float(self._clock())
        for workspace_uuid, (token, expires, binding) in tuple(
            self._credentials.items()
        ):
            if now >= expires:
                self._credentials.pop(workspace_uuid, None)
                self._save_persisted()
                continue
            if secrets.compare_digest(token, supplied_token):
                # Sliding expiration: keep active session alive
                self._credentials[workspace_uuid] = (
                    token,
                    now + self._ttl_seconds,
                    binding,
                )
                self._save_persisted()
                return binding
        return None
