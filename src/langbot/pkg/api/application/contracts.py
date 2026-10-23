"""Versioned, transport-independent application operation contracts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter

from ..authz import Permission
from ..context import PrincipalType, RequestContext


class Input(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', revalidate_instances='always')


@dataclass(frozen=True, slots=True)
class ApplicationAPIError:
    code: str
    message: str
    status_code: int = 400
    details: dict | None = None


class ApplicationAPIException(Exception):
    def __init__(self, error: ApplicationAPIError):
        self.error = error
        super().__init__(error.message)


@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    permission: Permission
    handler: Callable[[Any, RequestContext, Input], Awaitable[Any]]
    input_type: type[Input]
    output_type: Any
    side_effect: bool = False
    version: str = '1'
    principals: frozenset[PrincipalType] | None = None
    streaming: bool = False

    def as_dict(self) -> dict:
        return {
            'id': self.operation_id,
            'version': self.version,
            'scope': 'workspace',
            'permission': self.permission.value,
            'side_effect': self.side_effect,
            'streaming': self.streaming,
            'principals': sorted(self.principals) if self.principals is not None else None,
            'input_schema': self.input_type.model_json_schema(),
            'output_schema': TypeAdapter(self.output_type).json_schema(),
        }
