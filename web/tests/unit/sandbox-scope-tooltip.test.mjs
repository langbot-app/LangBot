import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const { load } = createRequire(require.resolve('eslint'))('js-yaml');
const metadata = load(
  fs.readFileSync(
    new URL(
      '../../../src/langbot/templates/metadata/pipeline/ai.yaml',
      import.meta.url,
    ),
    'utf8',
  ),
);
const scope = metadata.stages
  .find((stage) => stage.name === 'local-agent')
  .config.find((item) => item.name === 'box-session-id-template');
const unavailable = '沙箱未启用，请启用 Box 并确认连接正常后再修改作用域。';
const globalForced = '已强制使用全局沙箱，无法修改作用域。';
const customForced = '已强制使用固定沙箱作用域，无法修改作用域。';

function loadSource(relativePath) {
  const filename = new URL(`../../src/${relativePath}`, import.meta.url);
  assert.ok(fs.existsSync(filename), `Missing policy module: ${relativePath}`);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const loaded = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    (name) => {
      if (name === '@/app/infra/entities/form/dynamic')
        return loadSource('app/infra/entities/form/dynamic.ts');
      throw new Error(`Unexpected runtime import: ${name}`);
    },
    loaded,
    loaded.exports,
  );
  return loaded.exports;
}

function policies() {
  return {
    ...loadSource('app/home/components/dynamic-form/DynamicFormConditions.ts'),
    ...loadSource(
      'app/home/pipelines/components/pipeline-form/BoxScopeContext.ts',
    ),
  };
}

function scopeState(available, forcedTemplate) {
  const { getBoxScopeContext, resolveDisabledState } = policies();
  return resolveDisabledState(
    scope,
    {},
    undefined,
    getBoxScopeContext(available, forcedTemplate),
  );
}

test('sandbox default tooltip explains only unavailability', () => {
  assert.equal(scope.disabled_tooltip.zh_Hans, unavailable);
});

for (const [name, available, template, expected] of [
  ['Box disabled', false, '', unavailable],
  ['Box disconnected', false, undefined, unavailable],
  [
    'unavailable takes precedence over forced global',
    false,
    '{global}',
    unavailable,
  ],
  [
    'unavailable takes precedence over forced custom',
    false,
    '{pipeline_id}',
    unavailable,
  ],
  ['available forced global', true, '{global}', globalForced],
  ['available padded forced global', true, ' {global} ', globalForced],
  ['available whitespace-only editable', true, '   ', undefined],
  ['available forced custom', true, '{pipeline_id}', customForced],
  ['available forced literal', true, 'tenant-sandbox', customForced],
  ['available editable', true, '', undefined],
  ['available without limitation', true, undefined, undefined],
]) {
  test(name, () => {
    const state = scopeState(available, template);
    assert.equal(state.isDisabledByCondition, expected !== undefined);
    assert.equal(state.disabledTooltip?.zh_Hans, expected);
  });
}

test('reason follows availability and forced-scope transitions without mutating metadata', () => {
  const snapshot = structuredClone(scope);
  for (const [available, template, expected] of [
    [false, '{global}', unavailable],
    [true, '{global}', globalForced],
    [true, '{pipeline_id}', customForced],
    [true, '', undefined],
    [false, '', unavailable],
    [true, '', undefined],
  ]) {
    assert.equal(
      scopeState(available, template).disabledTooltip?.zh_Hans,
      expected,
    );
  }
  assert.deepEqual(scope, snapshot);
});

test('all sandbox reason variants preserve the eight metadata locales', () => {
  const locales = [
    'en_US',
    'zh_Hans',
    'zh_Hant',
    'ja_JP',
    'vi_VN',
    'th_TH',
    'es_ES',
    'ru_RU',
  ].sort();
  assert.equal(scope.disabled_tooltip_overrides?.length, 2);
  const messages = [
    scope.disabled_tooltip,
    ...scope.disabled_tooltip_overrides.map((entry) => entry.tooltip),
  ];
  for (const message of messages) {
    assert.deepEqual(Object.keys(message).sort(), locales);
    for (const locale of locales) assert.ok(message[locale].trim(), locale);
  }
  for (const locale of locales) {
    assert.equal(
      new Set(messages.map((message) => message[locale])).size,
      3,
      locale,
    );
    assert.equal(
      scopeState(false, '{global}').disabledTooltip[locale],
      messages[0][locale],
    );
    assert.equal(
      scopeState(true, '{global}').disabledTooltip[locale],
      messages[1][locale],
    );
    assert.equal(
      scopeState(true, '{pipeline_id}').disabledTooltip[locale],
      messages[2][locale],
    );
  }
});

test('ordinary static disabled tooltip remains compatible', () => {
  const { resolveDisabledState } = policies();
  const tooltip = { en_US: 'Read only' };
  const config = {
    disable_if: { field: 'locked', operator: 'eq', value: true },
    disabled_tooltip: tooltip,
  };
  assert.deepEqual(resolveDisabledState(config, { locked: true }), {
    isDisabledByCondition: true,
    disabledTooltip: tooltip,
  });
  assert.deepEqual(resolveDisabledState(config, { locked: false }), {
    isDisabledByCondition: false,
    disabledTooltip: undefined,
  });
  assert.equal(
    resolveDisabledState({ disabled_tooltip: tooltip }, {}).disabledTooltip,
    undefined,
  );
  assert.equal(
    resolveDisabledState({ disable_if: config.disable_if }, { locked: true })
      .disabledTooltip,
    undefined,
  );
});

test('conditional overrides reuse eq, neq, in and live/external/system resolution', () => {
  const { matchesFormCondition, resolveDisabledState } = policies();
  const watched = { mode: 'live', empty: null, '__system.locked': false };
  const external = { mode: 'external', fallback: 3, empty: 'external' };
  const system = { locked: true };
  for (const [condition, expected] of [
    [{ field: 'mode', operator: 'eq', value: 'live' }, true],
    [{ field: 'mode', operator: 'eq', value: 'external' }, false],
    [{ field: 'fallback', operator: 'neq', value: 4 }, true],
    [{ field: 'fallback', operator: 'in', value: [2, 3] }, true],
    [{ field: 'fallback', operator: 'in', value: '3' }, false],
    [{ field: 'fallback', operator: 'eq', value: '3' }, false],
    [{ field: 'empty', operator: 'eq', value: null }, true],
    [{ field: '__system.locked', operator: 'eq', value: true }, true],
    [{ field: 'absent', operator: 'eq', value: true }, false],
  ])
    assert.equal(
      matchesFormCondition(condition, watched, external, system),
      expected,
    );
  const config = {
    disable_if: { field: '__system.locked', operator: 'eq', value: true },
    disabled_tooltip: { en_US: 'Default' },
    disabled_tooltip_overrides: [
      {
        when: { field: 'mode', operator: 'eq', value: 'external' },
        tooltip: { en_US: 'Wrong' },
      },
      {
        when: { field: 'fallback', operator: 'in', value: [3] },
        tooltip: { en_US: 'First match' },
      },
      {
        when: { field: 'mode', operator: 'neq', value: 'external' },
        tooltip: { en_US: 'Later match' },
      },
    ],
  };
  assert.equal(
    resolveDisabledState(config, watched, external, system).disabledTooltip
      .en_US,
    'First match',
  );
  assert.equal(
    resolveDisabledState(config, {}, {}, system).disabledTooltip.en_US,
    'Later match',
  );
  assert.equal(
    resolveDisabledState(config, watched, external, { locked: false })
      .disabledTooltip,
    undefined,
  );
  assert.equal(
    resolveDisabledState(
      { ...config, disabled_tooltip_overrides: [] },
      watched,
      external,
      system,
    ).disabledTooltip.en_US,
    'Default',
  );
  const unmatched = {
    ...config,
    disabled_tooltip_overrides: [config.disabled_tooltip_overrides[0]],
  };
  assert.equal(
    resolveDisabledState(unmatched, watched, external, system).disabledTooltip
      .en_US,
    'Default',
  );
});
