"""Typed, installation-owned Artifacts over the existing Workspace API.

No method accepts a tenant, owner, installation, internal storage key or Box path.
Independent older Hosts fail explicitly; there is no legacy storage fallback.
"""

from __future__ import annotations

import base64
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .invocation import current_api, invocation_capability
from .workspace import WorkspaceOperationsProxy

MAX_ARTIFACT_RPC_BYTES = 256 * 1024


class ArtifactMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    mime_type: str
    size: int
    digest: str
    source: str
    lifecycle: str


class ArtifactData(BaseModel):
    metadata: ArtifactMetadata
    content: bytes


class ArtifactOperationError(RuntimeError):
    """Preserve the Host's authorization, expiry and integrity error code."""

    def __init__(self, error: dict[str, Any]):
        self.code = str(error.get("code", "artifact_operation_failed"))
        self.details = error.get("details")
        super().__init__(str(error.get("message", self.code)))


class ArtifactsProxy:
    def __init__(self, handler, run_id: str | None = None):
        self._handler = handler
        self._run_id = run_id
        self._invocation = invocation_capability(handler)

    async def _call(self, name: str, **arguments: Any) -> Any:
        if self._invocation is not None:
            self._invocation.require_active()
        api = current_api(self._handler)
        run_id = self._run_id
        if api is not None and getattr(api, "run_id", None) is not None:
            active = api.run_id
            if run_id is not None and active != run_id:
                raise RuntimeError("Artifact proxy belongs to another run")
            run_id = active
        response = await WorkspaceOperationsProxy(self._handler, run_id).call(
            "artifact." + name, **arguments
        )
        if not response.get("ok"):
            raise ArtifactOperationError(response.get("error") or {})
        return response["result"]

    async def create(
        self,
        filename: str,
        content: bytes,
        *,
        mime_type: str = "application/octet-stream",
        ttl_seconds: int = 86400,
    ) -> ArtifactMetadata:
        if not isinstance(content, bytes) or len(content) > MAX_ARTIFACT_RPC_BYTES:
            raise ValueError("Artifact RPC content must be bytes within 262144 bytes")
        result = await self._call(
            "create",
            filename=filename,
            content_base64=base64.b64encode(content).decode("ascii"),
            mime_type=mime_type,
            ttl_seconds=ttl_seconds,
        )
        return ArtifactMetadata.model_validate(result)

    async def get(self, artifact_id: str) -> ArtifactMetadata:
        return ArtifactMetadata.model_validate(
            await self._call("get", artifact_id=artifact_id)
        )

    async def read(
        self, artifact_id: str, *, max_bytes: int = MAX_ARTIFACT_RPC_BYTES
    ) -> ArtifactData:
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_ARTIFACT_RPC_BYTES:
            raise ValueError(
                "Artifact RPC read limit must be between 1 and 262144 bytes"
            )
        result = await self._call("read", artifact_id=artifact_id, max_bytes=max_bytes)
        encoded = result["content_base64"]
        if not isinstance(encoded, str) or len(encoded) > 4 * ((max_bytes + 2) // 3):
            raise ValueError("Artifact response exceeds the requested bound")
        content = base64.b64decode(encoded, validate=True)
        if len(content) > max_bytes:
            raise ValueError("Artifact response exceeds the requested bound")
        return ArtifactData(
            metadata=ArtifactMetadata.model_validate(result["metadata"]),
            content=content,
        )

    async def read_content(
        self,
        artifact_id: str,
        *,
        mode: Literal["auto", "text", "native", "pages"] = "auto",
        offset: int = 0,
        max_chars: int = 8192,
        page_start: int = 1,
        page_end: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self._call(
            "read_content",
            artifact_id=artifact_id,
            mode=mode,
            offset=offset,
            max_chars=max_chars,
            page_start=page_start,
            page_end=page_end,
        )

    async def retain(self, artifact_id: str) -> ArtifactMetadata:
        return ArtifactMetadata.model_validate(
            await self._call("retain", artifact_id=artifact_id)
        )

    async def release(self, artifact_id: str) -> ArtifactMetadata:
        return ArtifactMetadata.model_validate(
            await self._call("release", artifact_id=artifact_id)
        )

    async def delete(self, artifact_id: str) -> dict[str, Any]:
        return await self._call("delete", artifact_id=artifact_id)
