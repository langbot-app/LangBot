import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
function load(relative) {
  const source = fs.readFileSync(new URL(relative, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', compiled)(module, module.exports);
  return module.exports;
}
const helper =
  '../../src/app/home/pipelines/components/pipeline-form/RunnerConfigPreservation.ts';
test('mount emission is not a persisted edit', () => {
  const { preserveRunnerConfig } = load(helper);
  const raw = {
    'api-key': '  secret  ',
    'agent-id': null,
    'enable-all-tools': false,
  };
  assert.deepEqual(
    preserveRunnerConfig(raw, undefined, {
      'api-key': 'secret',
      'agent-id': '',
      mode: 'chat',
    }),
    raw,
  );
});
test('unrelated edits preserve hidden Host policy, absent/null and credentials', () => {
  const { preserveRunnerConfig } = load(helper);
  const raw = {
    'api-key': '  secret  ',
    'agent-id': null,
    'enable-all-tools': false,
    tools: ['one'],
    'knowledge-bases': ['kb'],
    'mcp-resources': [{ uri: 'private' }],
    'mcp-resource-agent-read-enabled': false,
  };
  const first = {
    'api-key': 'secret',
    'agent-id': '',
    mode: 'chat',
    absent: 'default',
  };
  assert.deepEqual(
    preserveRunnerConfig(raw, first, { ...first, mode: 'agent' }),
    { ...raw, mode: 'agent' },
  );
});
test('intentional edits, removals and nested edits win without normalizing untouched siblings', () => {
  const { preserveRunnerConfig } = load(helper);
  const raw = {
    'api-key': '  secret  ',
    model: {
      primary: 'one',
      fallbacks: ['two'],
      reasoning: { one: 'provider_default', two: 'high' },
    },
  };
  const first = { 'api-key': 'secret', model: raw.model };
  assert.deepEqual(
    preserveRunnerConfig(raw, first, {
      'api-key': 'new',
      model: {
        primary: 'one',
        fallbacks: [],
        reasoning: { one: 'provider_default' },
      },
    }),
    {
      'api-key': 'new',
      model: {
        primary: 'one',
        fallbacks: [],
        reasoning: { one: 'provider_default' },
      },
    },
  );
});
test('save normalization preserves explicit selected per-model provider_default', () => {
  const { normalizeDynamicFormValuesForSave } = load(
    '../../src/app/home/components/dynamic-form/DynamicFormSaveValues.ts',
  );
  const value = {
    primary: 'one',
    fallbacks: ['two'],
    reasoning: { one: 'provider_default', two: 'high', removed: 'high' },
  };
  assert.deepEqual(
    normalizeDynamicFormValuesForSave(
      [{ name: 'model', type: 'model-fallback-selector' }],
      { model: value },
    ).model.reasoning,
    { one: 'provider_default', two: 'high' },
  );
});
