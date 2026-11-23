import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(
  'src/app/home/pipelines/pipeline-config-safety.ts',
  'utf8',
);
const context = { exports: {} };
vm.runInNewContext(
  ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText,
  context,
);
const { isCurrentPipelineConfig } = context.exports;
const plugin = 'plugin:langbot-team/LocalAgent/default';

test('canonical current empty runner remains editable', () => {
  const config = JSON.parse(
    readFileSync(
      '../src/langbot/templates/default-pipeline-config.json',
      'utf8',
    ),
  );
  assert.equal(isCurrentPipelineConfig(config), true);
});

test('configured current binding remains editable', () => {
  assert.equal(
    isCurrentPipelineConfig({
      ai: { runner: { id: plugin }, runner_config: {} },
    }),
    true,
  );
});

for (const [name, ai] of Object.entries({
  legacy: { runner: { runner: 'local-agent' } },
  mixedSelector: { runner: { id: plugin, runner: 'local-agent' } },
  mixedLegacySection: {
    runner: { id: plugin },
    runner_config: {},
    'local-agent': {},
  },
  emptyMixedLegacySection: {
    runner: { id: '' },
    runner_config: {},
    'dify-service-api': {},
  },
  emptyMissingContainer: { runner: { id: '' } },
  emptyMalformedContainer: { runner: { id: '' }, runner_config: [] },
  emptyAmbiguousContainer: {
    runner: { id: '' },
    runner_config: { orphan: {} },
  },
  emptyAmbiguousSelector: {
    runner: { id: '', legacy: 'local-agent' },
    runner_config: {},
  },
  missingId: { runner: {}, runner_config: {} },
  nonPlugin: { runner: { id: 'local-agent' }, runner_config: {} },
})) {
  test(`${name} does not hydrate current editor defaults`, () => {
    assert.equal(isCurrentPipelineConfig({ ai }), false);
  });
}
