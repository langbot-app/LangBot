from __future__ import annotations

import pydantic
from typing import Any, Literal

from langbot_plugin.entities.io.context import (
    ActionContext,
    ActionEnvelopeContext,
    InstallationBinding,
    parse_action_envelope_context,
)


class ActionRequest(pydantic.BaseModel):
    seq_id: int = pydantic.Field(..., description="The sequence id of the request")
    action: str
    data: dict[str, Any]
    # Keep InstallationBinding first: it must retain its revision/digest fields
    # instead of being reduced to the legacy Workspace envelope.
    context: InstallationBinding | ActionContext | None = None
    stream_flow_control: Literal[1] | None = None

    @classmethod
    def make_request(
        cls,
        seq_id: int,
        action: str,
        data: dict[str, Any],
        context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> ActionRequest:
        parsed_context = (
            parse_action_envelope_context(context) if context is not None else None
        )
        return cls(
            seq_id=seq_id,
            action=action,
            data=data,
            context=parsed_context,
        )

    def model_dump(self, **kwargs):
        # Preserve the exact legacy wire shape when no Workspace context is
        # present, while serializing the context envelope for new peers.
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)
