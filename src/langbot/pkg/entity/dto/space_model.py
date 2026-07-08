# [
#   {
#     "uuid": "7652ebdb-54dc-412c-a830-e9268ac88471",
#     "model_id": "claude-opus-4-5-20251101",
#     "display_name": {
#       "en_US": "claude-opus-4-5-20251101",
#       "zh_Hans": "claude-opus-4-5-20251101"
#     },
#     "description": {},
#     "provider": "anthropic",
#     "category": "chat",
#     "icon_url": "Claude.Color",
#     "tags": {},
#     "is_featured": true,
#     "featured_order": 999,
#     "model_ratio": 2.5,
#     "completion_ratio": 5,
#     "quota_type": 0,
#     "model_price": 0,
#     "input_credits": 500,
#     "output_credits": 2500,
#     "vendor_id": 1,
#     "vendor_name": "Anthropic",
#     "vendor_icon": "Claude.Color",
#     "supported_endpoints": [
#       "anthropic",
#       "openai"
#     ],
#     "status": "active",
#     "metadata": null,
#     "created_at": "2025-12-30T22:23:38.337207+08:00",
#     "updated_at": "2025-12-30T22:23:38.337207+08:00"
#   }
# ]

import pydantic


class SpaceModel(pydantic.BaseModel):
    uuid: str
    model_id: str
    provider: str
    category: str  # chat / embedding
    llm_abilities: list[str] | None = None
    is_featured: bool = False
    featured_order: int = 0
    status: str
    created_at: str | None = None
    updated_at: str | None = None
