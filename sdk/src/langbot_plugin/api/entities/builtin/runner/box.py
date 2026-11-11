"""Box resource and invocation contracts. No runtime credentials or host paths."""

from typing import Any
import pydantic


class BoxStatus(pydantic.BaseModel):
    available: bool
    enabled: bool
    limit: int | None = None
    used: int | None = None
    remaining: int | None = None
    required_reuse_key: str | None = None
    reason: str | None = None


class BoxSession(pydantic.BaseModel):
    id: str
    status: str


class BoxBinding(pydantic.BaseModel):
    box_id: str
    outbox: str


class BoxFile(pydantic.BaseModel):
    id: str
    name: str
    type: str
    size: int
    path: str | None = None
    warning: str | None = None


class BoxAcquireRequest(pydantic.BaseModel):
    reuse_key: str = pydantic.Field(min_length=1, max_length=1024)
    options: dict[str, Any] = pydantic.Field(default_factory=dict)
    model_config = pydantic.ConfigDict(extra="forbid")
