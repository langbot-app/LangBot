import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8');

test('dynamic form combines manifest normalization and shared condition helpers', () => {
  const source = read(
    '../../src/app/home/components/dynamic-form/DynamicFormComponent.tsx',
  );
  const parsed = ts.createSourceFile(
    'DynamicFormComponent.tsx',
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  assert.equal(
    parsed.parseDiagnostics.length,
    0,
    'Dynamic form must parse after the merge',
  );
  const imports = parsed.statements.filter(ts.isImportDeclaration);
  const importedNames = (module) =>
    imports
      .filter((item) => item.moduleSpecifier.text === module)
      .flatMap(
        (item) =>
          item.importClause?.namedBindings?.elements?.map(
            (entry) => entry.name.text,
          ) ?? [],
      );
  assert.ok(
    importedNames('./DynamicFormItemConfig').includes(
      'parseDynamicFormItemType',
    ),
  );
  assert.deepEqual(importedNames('./DynamicFormConditions').sort(), [
    'resolveDisabledState',
    'resolveShowIfValue',
  ]);
  assert.equal(
    parsed.statements.filter(
      (item) =>
        ts.isFunctionDeclaration(item) &&
        item.name?.text === 'resolveShowIfValue',
    ).length,
    0,
  );
});

test('pipeline defaults retain plugin runner containers, not retired Core runners', () => {
  const config = JSON.parse(
    read('../../../src/langbot/templates/default-pipeline-config.json'),
  );
  assert.deepEqual(config.ai, {
    runner: { id: '', 'expire-time': 0 },
    runner_config: {},
  });
  const metadata = read(
    '../../../src/langbot/templates/metadata/pipeline/ai.yaml',
  );
  assert.doesNotMatch(
    metadata,
    /^\s+- name: (?:local-agent|n8n-service-api|langflow-api)$/m,
  );
  assert.match(metadata, /RunnerRegistry/);
});

test('pipeline UI does not restore host-owned Box scope as local-agent config', () => {
  const source = read(
    '../../src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx',
  );
  assert.doesNotMatch(
    source,
    /getBoxScopeContext|force_box_session_id_template|N8nAuthFormComponent/,
  );
  assert.match(source, /ai\.runner_config/);
  assert.match(source, /systemContext=\{dynamicFormSystemContext\}/);
});

test('backend client preserves complementary Codex and runner debug API imports', () => {
  const source = read('../../src/app/infra/http/BackendClient.ts');
  const parsed = ts.createSourceFile(
    'BackendClient.ts',
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  assert.equal(
    parsed.parseDiagnostics.length,
    0,
    'API client must parse after the merge',
  );
  const imports = parsed.statements
    .filter(ts.isImportDeclaration)
    .flatMap(
      (item) =>
        item.importClause?.namedBindings?.elements?.map(
          (entry) => entry.name.text,
        ) ?? [],
    );
  for (const name of [
    'CodexAuthStatus',
    'CodexDeviceAuthorization',
    'CodexDevicePoll',
    'DebugExecutionEvent',
  ]) {
    assert.ok(imports.includes(name), name);
  }
});
