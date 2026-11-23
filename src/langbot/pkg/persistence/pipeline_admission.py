"""Transaction-held, tenant/pipeline-scoped admission for form producers.

Every pending producer must hold this row until its INSERT commits. Migration
holds the same row for both CAS and activation. No table/process/advisory lock.
The no-op UPDATE also acquires SQLite's write reservation before any reads.
"""

import sqlalchemy as sa
from ..entity.persistence.pipeline import LegacyPipeline


async def lock_pipeline_admission(session, workspace_uuid: str, pipeline_uuid: str):
    if not workspace_uuid or not pipeline_uuid:
        raise ValueError('Pipeline admission requires exact ownership')
    t = LegacyPipeline.__table__
    result = await session.execute(
        sa.update(t)
        .where(t.c.workspace_uuid == workspace_uuid, t.c.uuid == pipeline_uuid)
        .values(updated_at=t.c.updated_at)
    )
    if result.rowcount != 1:
        raise ValueError('Pipeline admission authority unavailable')
    return (
        await session.execute(
            sa.select(t.c.config).where(t.c.workspace_uuid == workspace_uuid, t.c.uuid == pipeline_uuid)
        )
    ).scalar_one()
