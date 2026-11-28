"""Read and update workflow memory under the executing Workspace."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..entity.persistence.workflow import WorkflowMemory
from ..storage.media import MediaCache


def apply_items(values, items):
    changed = {}
    for item in items:
        key = item['key']
        path = key.split('.')
        if not all(path):
            raise ValueError('Memory keys must be non-empty')
        parent = values
        for segment in path[:-1]:
            parent = parent.setdefault(segment, {})
            if not isinstance(parent, dict):
                raise ValueError(f'Memory key {key} is not a map')
        leaf = path[-1]
        value = item.get('value', '')
        op = item.get('op', 'set')
        if op == 'increment':
            value = float(parent.get(leaf, 0)) + float(value)
            value = int(value) if value.is_integer() else value
        elif op in ('append', 'remove'):
            existing = parent.get(leaf, [])
            if not isinstance(existing, list):
                raise ValueError(f'Memory key {key} is not a list')
            value = [*existing, value] if op == 'append' else [part for part in existing if part != value]
        elif op != 'set':
            raise ValueError(f'Unknown memory operation: {op}')
        parent[leaf] = value
        changed[key] = value
    return changed


class RunMemory:
    def __init__(self, manager, workspace, workflow, user_id, group_id, *, test=False):
        self.manager = manager
        self.workspace = workspace
        self.workflow = workflow
        self.test = test
        self.ids = {'user': user_id, 'group': group_id, 'workflow': workflow}
        self.values = {scope: {} for scope in ('run', *self.ids)}

    def query(self, scope):
        return sa.select(WorkflowMemory.key, WorkflowMemory.value).where(
            WorkflowMemory.workspace_uuid == self.workspace,
            WorkflowMemory.workflow_uuid == self.workflow,
            WorkflowMemory.scope == scope,
            WorkflowMemory.scope_id == self.ids[scope],
        )

    async def load(self):
        if self.test:
            return
        for scope, ident in self.ids.items():
            if ident:
                rows = await self.manager.execute_async(self.query(scope))
                self.values[scope] = {row.key: json.loads(row.value) for row in rows}

    async def write(self, scope, items):
        if scope == 'run':
            return apply_items(self.values[scope], items)
        if not self.ids.get(scope):
            raise ValueError(f'No {scope} memory for this trigger')
        if self.test:
            return apply_items(self.values[scope], items)
        roots = sorted({item['key'].split('.')[0] for item in items})
        insert = pg_insert if self.manager.get_db_engine().dialect.name == 'postgresql' else sqlite_insert
        identity = dict(
            workspace_uuid=self.workspace, workflow_uuid=self.workflow, scope=scope, scope_id=self.ids[scope]
        )
        async with self.manager.tenant_write_uow(self.workspace, operation='workflow.remember') as transaction:
            for root in roots:
                await transaction.execute(
                    insert(WorkflowMemory).values(**identity, key=root, value='{}').on_conflict_do_nothing()
                )
            rows = await transaction.execute(
                self.query(scope).where(WorkflowMemory.key.in_(roots)).order_by(WorkflowMemory.key).with_for_update()
            )
            values = {row.key: json.loads(row.value) for row in rows}
            for item in items:
                key = item['key']
                if '.' not in key and values.get(key) == {} and item.get('op') in ('increment', 'append', 'remove'):
                    values.pop(key)
            changed = apply_items(values, items)
            for root in roots:
                await transaction.execute(
                    sa.update(WorkflowMemory)
                    .filter_by(**identity, key=root)
                    .values(value=json.dumps(MediaCache.redact_inline_images(values[root]), ensure_ascii=False))
                )
        self.values[scope].update(values)
        return changed
