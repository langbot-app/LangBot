import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const m = { exports: {} };
new Function(
  'module',
  'exports',
  ts.transpileModule(
    readFileSync(
      new URL(
        '../../src/app/home/components/workspace-settings/plan-revisions.ts',
        import.meta.url,
      ),
      'utf8',
    ),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText,
)(m, m.exports);
const { revisionRows } = m.exports;
const current = {
  name: 'pro',
  revision: 1,
  limits: { 'bots.max': 2, 'chat_history.retention_days': 30 },
  monthly_bonus_credits: 10,
  entitlement_features: { 'platform.telegram': false, mcp_stdio: false },
};
test('same version and revision-only changes do not duplicate comparisons', () => {
  assert.ok(revisionRows(current, current).every((row) => !row.changed));
  assert.ok(
    revisionRows(current, { ...current, revision: 2 }).every(
      (row) => !row.changed,
    ),
  );
});
test('compares effective quotas, credits, retention, platforms and feature switches', () => {
  const latest = {
    name: 'pro',
    revision: 2,
    limits: { 'bots.max': 5 },
    chat_history_retention_days: 60,
    monthly_bonus_credits: 20,
    entitlement_features: { mcp_stdio: true },
    disabled_adapters: [],
  };
  const changed = revisionRows(current, latest).filter((row) => row.changed);
  assert.deepEqual(
    changed.map((row) => row.key).sort(),
    [
      'feature:mcp_stdio',
      'feature:platform.telegram',
      'limit:bots.max',
      'limit:chat_history.retention_days',
      'monthly_credits',
    ].sort(),
  );
  assert.equal(
    changed.find((row) => row.key === 'feature:platform.telegram').after,
    true,
  );
});
test('catalog representations normalize to snapshot values', () => {
  const latest = {
    name: 'pro',
    revision: 2,
    limits: { 'bots.max': 2 },
    chat_history_retention_days: 30,
    monthly_bonus_credits: 10,
    disabled_adapters: ['telegram'],
  };
  assert.ok(revisionRows(current, latest).every((row) => !row.changed));
});
test('missing latest keeps current values without invented changes', () => {
  const rows = revisionRows(current);
  assert.equal(rows.find((row) => row.key === 'limit:bots.max').before, 2);
  assert.ok(rows.every((row) => !row.changed));
});
