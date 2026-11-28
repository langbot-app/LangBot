import datetime
import json

import sqlalchemy as sa


REPORT_PREFIX = 'message_policy_upgrade:'


def report_value(changes):
    return json.dumps({'migrated_at': datetime.datetime.now(datetime.UTC).isoformat(), **changes}, ensure_ascii=False)


def write_report(bind, stage, reports):
    if not reports or not sa.inspect(bind).has_table('workspace_metadata'):
        return
    table = sa.table('workspace_metadata', sa.column('workspace_uuid'), sa.column('key'), sa.column('value'))
    for workspace, changes in reports.items():
        if workspace:
            key = REPORT_PREFIX + stage
            scoped = (table.c.workspace_uuid == workspace, table.c.key == key)
            if bind.execute(sa.select(table.c.key).where(*scoped)).first() is None:
                bind.execute(table.insert().values(workspace_uuid=workspace, key=key, value=report_value(changes)))
