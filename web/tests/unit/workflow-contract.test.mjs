import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

function workflowLocale(language) {
  const source = fs.readFileSync(
    new URL(`../../src/i18n/locales/${language}.ts`, import.meta.url),
    'utf8',
  );
  const start = source.indexOf('  workflows: {') + '  workflows: '.length;
  // Take the balanced object literal; other sections may follow it.
  let depth = 0;
  let end = start;
  for (; end < source.length; end += 1) {
    if (source[end] === '{') depth += 1;
    if (source[end] === '}' && --depth === 0) break;
  }
  const body = source.slice(start, end + 1);
  return Function(`return (${body})`)();
}

function keys(value, prefix = '') {
  return Object.entries(value)
    .flatMap(([key, child]) =>
      typeof child === 'object'
        ? keys(child, `${prefix}${key}.`)
        : `${prefix}${key}`,
    )
    .sort();
}

test('workflow translations expose identical keys in all eight languages', () => {
  const expected = keys(workflowLocale('en-US'));
  for (const language of [
    'zh-Hans',
    'zh-Hant',
    'ja-JP',
    'es-ES',
    'ru-RU',
    'th-TH',
    'vi-VN',
  ]) {
    assert.deepEqual(keys(workflowLocale(language)), expected, language);
  }
});

test('workflow client tests drafts and does not expose obsolete endpoints', () => {
  const source = fs.readFileSync(
    new URL('../../src/app/infra/http/BackendClient.ts', import.meta.url),
    'utf8',
  );
  assert.match(source, /testWorkflow\(/);
  assert.match(source, /\/api\/v1\/workflows\/\$\{uuid\}\/test/);
  for (const method of [
    'runWorkflow',
    'getWorkflowVersions',
    'rollbackWorkflow',
    'toggleWorkflow',
    'publishWorkflow',
    'cancelWorkflowExecution',
    'rerunWorkflowExecution',
    'startWorkflowDebug',
    'getWorkflowExecutionLogs',
  ]) {
    assert.doesNotMatch(source, new RegExp(method + '\\('));
  }
});

test('workflow quota is separate from pipeline quota', () => {
  const source = fs.readFileSync(
    new URL(
      '../../src/app/home/components/workspace-quota/useWorkspaceQuotaStatus.ts',
      import.meta.url,
    ),
    'utf8',
  );
  assert.match(source, /filter\(\(item\) => item.kind !== 'workflow'\)/);
  assert.match(source, /filter\(\(item\) => item.kind === 'workflow'\)/);
  assert.match(source, /limitation\?\.max_workflows/);
});

test('monitoring names workflow-handled messages instead of "unhandled"', () => {
  const source = fs.readFileSync(
    new URL(
      '../../src/app/home/monitoring/components/executions/ExecutionTable.tsx',
      import.meta.url,
    ),
    'utf8',
  );
  assert.match(source, /handledBy\.startsWith\('workflow:'\)/);
  assert.match(
    source,
    /workflowName\?\.\(workflow\) \|\| t\('workflows\.title'\)/,
  );
  assert.match(source, /data-testid="execution-kind-workflow"/);
});

test('workflow tree helpers keep the graph a tree', async () => {
  const source = fs.readFileSync(
    new URL('../../src/app/home/workflows/lib/tree.ts', import.meta.url),
    'utf8',
  );
  // A step inserted into an occupied slot adopts the existing step.
  assert.match(source, /edges\.push\(\{\s*from: id,\s*to: existing/);
  // Removing a branching step removes its branches, a linear step is spliced.
  assert.match(source, /export function removalImpact/);
  assert.match(source, /export function pruneBranches/);
});
