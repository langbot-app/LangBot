"""Structured interaction entities for Runner Protocol v1."""

from __future__ import annotations

import typing
import uuid

import pydantic


InteractionFieldType = typing.Literal[
    "text",
    "textarea",
    "select",
    "multiselect",
    "number",
    "boolean",
    "file",
]
InteractionActionStyle = typing.Literal["default", "primary", "danger"]
JSONValue = pydantic.JsonValue


class InteractionOption(pydantic.BaseModel):
    """One selectable value in an interaction field."""

    value: str = pydantic.Field(min_length=1, max_length=512)
    label: str = pydantic.Field(min_length=1, max_length=512)
    description: str | None = pydantic.Field(default=None, max_length=2000)

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionField(pydantic.BaseModel):
    """A Host-renderable field in an interaction request."""

    id: str = pydantic.Field(min_length=1, max_length=128)
    label: str = pydantic.Field(min_length=1, max_length=512)
    type: InteractionFieldType
    required: bool = False
    options: list[InteractionOption] = pydantic.Field(
        default_factory=list, max_length=100
    )
    placeholder: str | None = pydantic.Field(default=None, max_length=1000)
    default: JSONValue = None

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionAction(pydantic.BaseModel):
    """A submit action rendered by the Host."""

    id: str = pydantic.Field(min_length=1, max_length=128)
    label: str = pydantic.Field(min_length=1, max_length=512)
    style: InteractionActionStyle = "default"

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionRequest(pydantic.BaseModel):
    """A runner request for Host-owned structured user interaction."""

    interaction_id: str = pydantic.Field(
        default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=255
    )
    kind: typing.Literal["form", "confirmation", "choice"] = "form"
    title: str = pydantic.Field(min_length=1, max_length=1000)
    description: str | None = pydantic.Field(default=None, max_length=10000)
    fields: list[InteractionField] = pydantic.Field(default_factory=list, max_length=50)
    actions: list[InteractionAction] = pydantic.Field(
        default_factory=list, max_length=20
    )
    expires_at: int | None = None
    fallback_text: str | None = pydantic.Field(
        default=None, min_length=1, max_length=20000
    )

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionSubmission(pydantic.BaseModel):
    """Host-validated user input for a previous interaction request."""

    interaction_id: str = pydantic.Field(min_length=1, max_length=255)
    action_id: str | None = pydantic.Field(default=None, max_length=128)
    values: dict[str, JSONValue] = pydantic.Field(default_factory=dict)
    submitted_at: int | None = None
    label: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionDeliveryCapabilities(pydantic.BaseModel):
    """Structured interaction features supported by a delivery surface."""

    field_types: list[InteractionFieldType] = pydantic.Field(default_factory=list)
    action_styles: list[InteractionActionStyle] = pydantic.Field(default_factory=list)
    supports_updates: bool = False
    max_fields: int | None = pydantic.Field(default=None, ge=0)
    max_options: int | None = pydantic.Field(default=None, ge=0)
    max_actions: int | None = pydantic.Field(default=None, ge=0)
    supports_markdown: bool = False
    text_fallback: bool = True

    @property
    def supports_update(self) -> bool:
        return self.supports_updates

    model_config = pydantic.ConfigDict(extra="forbid")


class InteractionHandle(pydantic.BaseModel):
    """Opaque adapter delivery handle retained by the Host."""

    message_id: str | int | None = None
    card_id: str | None = None
    context: dict[str, JSONValue] = pydantic.Field(default_factory=dict)

    model_config = pydantic.ConfigDict(extra="allow")


class InteractionDegradation(pydantic.BaseModel):
    path: str
    reason: str
    applied: str


class InteractionResult(pydantic.BaseModel):
    status: typing.Literal["submitted", "timeout", "cancelled"]
    submission: InteractionSubmission | None = None
    degraded: list[InteractionDegradation] = pydantic.Field(default_factory=list)
    deadline_at: float | None = None


class InteractionNotSupportedError(Exception):
    def __init__(self, issues: list[dict[str, str]]):
        self.issues = issues
        super().__init__(
            "Interaction is not supported: "
            + ", ".join(f"{issue['path']}: {issue['reason']}" for issue in issues)
        )


__all__ = [
    "InteractionAction",
    "InteractionActionStyle",
    "InteractionDeliveryCapabilities",
    "InteractionDegradation",
    "InteractionField",
    "InteractionFieldType",
    "InteractionOption",
    "InteractionHandle",
    "InteractionNotSupportedError",
    "InteractionRequest",
    "InteractionResult",
    "InteractionSubmission",
    "JSONValue",
]
