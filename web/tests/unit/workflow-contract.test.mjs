import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

function workflowLocale(language) {
  const source = fs.readFileSync(
    new URL(`../../src/i18n/locales/${language}.ts`, import.meta.url),
    'utf8',
  );
  const start = source.indexOf('  workflows: {');
  const body = source
    .slice(start + '  workflows: '.length, source.lastIndexOf('\n};'))
    .replace(/,\s*$/, '');
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

test('workflow client uses synchronous run and does not expose obsolete endpoints', () => {
  const source = fs.readFileSync(
    new URL('../../src/app/infra/http/BackendClient.ts', import.meta.url),
    'utf8',
  );
  assert.match(source, /runWorkflow\(/);
  for (const method of [
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
