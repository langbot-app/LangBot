from __future__ import annotations

import pydantic
from typing import Any, Optional
import enum


class ChunkStatus(enum.Enum):
    """The status of the chunk."""

    CONTINUE = "continue"
    """Continue the chunk."""

    END = "end"
    """End the chunk."""


class ActionResponse(pydantic.BaseModel):
    stream_index: int | None = None

    def model_dump(self, **kwargs):
        result = super().model_dump(**kwargs)
        if self.stream_index is None:
            result.pop("stream_index", None)
        return result

    seq_id: Optional[int] = None
    code: int = pydantic.Field(..., description="The code of the response")
    message: str = pydantic.Field(..., description="The message of the response")
    data: dict[str, Any] = pydantic.Field(..., description="The data of the response")
    chunk_status: Optional[ChunkStatus] = pydantic.Field(
        default=ChunkStatus.CONTINUE,
        description="The status of the chunk, only used in chunked response",
    )

    @classmethod
    def success(cls, data: dict[str, Any]) -> ActionResponse:
        return cls(seq_id=0, code=0, message="success", data=data)

    @classmethod
    def error(cls, message: str, data: dict[str, Any] | None = None) -> ActionResponse:
        return cls(code=1, message=message, data=data or {})

    @pydantic.field_serializer("chunk_status")
    def serialize_chunk_status(
        self, chunk_status: ChunkStatus, _info: pydantic.FieldSerializationInfo
    ) -> str:
        return chunk_status.value

    @pydantic.field_validator("chunk_status")
    def validate_chunk_status(cls, v: ChunkStatus) -> ChunkStatus:
        if v is None:
            return ChunkStatus.CONTINUE
        return v
