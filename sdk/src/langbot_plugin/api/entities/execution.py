from __future__ import annotations

from typing import Any

import pydantic


class WorkspaceExecutionScope(pydantic.BaseModel):
    """Workspace identity carried by plugin-facing execution entities.

    The fields are optional so entities serialized by pre-multi-tenant LangBot
    versions remain valid.  A trusted runtime boundary must use
    ``ActionContext`` instead; these fields are for propagation and
    observability, not authorization.
    """

    instance_uuid: str | None = None
    workspace_uuid: str | None = None
    placement_generation: int | None = None

    def inherit_execution_scope(
        self,
        source: Any,
        *,
        reject_mismatch: bool = True,
    ) -> None:
        """Fill missing scope fields from another entity.

        When both entities carry a value, a mismatch is rejected by default so
        a nested Session or Event cannot silently cross a Workspace boundary.
        """

        if source is None:
            return

        for field_name in (
            "instance_uuid",
            "workspace_uuid",
            "placement_generation",
        ):
            source_value = getattr(source, field_name, None)
            if source_value is None:
                continue

            current_value = getattr(self, field_name, None)
            if current_value is None:
                setattr(self, field_name, source_value)
            elif reject_mismatch and current_value != source_value:
                raise ValueError(
                    f"Execution scope mismatch for {field_name}: "
                    f"{current_value!r} != {source_value!r}"
                )

    def execution_scope_dump(self) -> dict[str, str | int]:
        """Return populated execution fields for custom serializers."""

        result: dict[str, str | int] = {}
        if self.instance_uuid is not None:
            result["instance_uuid"] = self.instance_uuid
        if self.workspace_uuid is not None:
            result["workspace_uuid"] = self.workspace_uuid
        if self.placement_generation is not None:
            result["placement_generation"] = self.placement_generation
        return result
