from __future__ import annotations

import pydantic

from typing import Any


class RetrieveResultEntry(pydantic.BaseModel):
    id: str

    metadata: dict[str, Any]

    distance: float
