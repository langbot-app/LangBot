import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/wizard/utils.ts',
);

function loadWizardUtils() {
  const source = fs.readFileSync(sourcePath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    () => {
      throw new Error('Wizard utils must not have runtime imports');
    },
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports;
}

const {
  configureLocalAgentPrimaryModel,
  ensureHttpBotSigningSecret,
  findDefaultPipeline,
  getErrorMessage,
  isRequiredRunnerConfigComplete,
  isWebhookModeEnabled,
} = loadWizardUtils();

test('generates an HTTP Bot signing secret when signatures are enabled', () => {
  const config = ensureHttpBotSigningSecret('http_bot', {
    signature_required: true,
    inbound_secret: '',
  });

  assert.match(config.inbound_secret, /^[a-f0-9]{64}$/);
});

test('preserves existing or intentionally disabled HTTP Bot signing config', () => {
  const existing = { signature_required: true, inbound_secret: 'keep-me' };
  const disabled = { signature_required: false, inbound_secret: '' };

  assert.equal(ensureHttpBotSigningSecret('http_bot', existing), existing);
  assert.equal(ensureHttpBotSigningSecret('http_bot', disabled), disabled);
});

test('does not add signing config to other adapters', () => {
  const config = {};

  assert.equal(ensureHttpBotSigningSecret('web_page_bot', config), config);
});

test('extracts the backend message from structured API errors', () => {
  assert.equal(
    getErrorMessage({ code: 400, msg: 'Signing secret is required' }),
    'Signing secret is required',
  );
  assert.equal(getErrorMessage(new Error('Network failed')), 'Network failed');
});

test('selects only a usable Workspace default pipeline', () => {
  const pipelines = [
    { uuid: 'recent-pipeline', is_default: false },
    { uuid: '', is_default: true },
    { uuid: 'default-pipeline', is_default: true },
  ];

  assert.equal(findDefaultPipeline(pipelines)?.uuid, 'default-pipeline');
});

test('configures the selected model as the Local Agent primary model', () => {
  const config = {
    trigger: { prefix: '!' },
    ai: {
      runner: { runner: 'plugin:external', timeout: 30 },
      'local-agent': {
        model: { primary: 'old-model', fallbacks: ['fallback-model'] },
        tools: { enabled: true },
      },
    },
  };

  const updated = configureLocalAgentPrimaryModel(config, 'selected-model');

  assert.equal(updated.ai.runner.runner, 'local-agent');
  assert.equal(updated.ai.runner.timeout, 30);
  assert.equal(updated.ai['local-agent'].model.primary, 'selected-model');
  assert.deepEqual(updated.ai['local-agent'].model.fallbacks, [
    'fallback-model',
  ]);
  assert.deepEqual(updated.ai['local-agent'].tools, { enabled: true });
  assert.deepEqual(updated.trigger, { prefix: '!' });
});

test('shows webhook guidance only when the adapter webhook mode is active', () => {
  const dualModeFields = [
    {
      name: 'webhook_url',
      show_if: { field: 'enable-webhook', operator: 'eq', value: true },
    },
  ];

  assert.equal(
    isWebhookModeEnabled(dualModeFields, { 'enable-webhook': false }),
    false,
  );
  assert.equal(
    isWebhookModeEnabled(dualModeFields, { 'enable-webhook': true }),
    true,
  );
  assert.equal(isWebhookModeEnabled([{ name: 'webhook_url' }], {}), true);
  assert.equal(isWebhookModeEnabled([], {}), false);
});

test('requires real values for required external runner configuration', () => {
  const fields = [
    { name: 'base-url', required: true, default: 'https://api.dify.ai/v1' },
    { name: 'api-key', required: true, default: 'your-api-key' },
    { name: 'optional', required: false, default: '' },
  ];

  assert.equal(
    isRequiredRunnerConfigComplete(fields, {
      'base-url': 'https://api.dify.ai/v1',
      'api-key': 'your-api-key',
    }),
    false,
  );
  assert.equal(
    isRequiredRunnerConfigComplete(fields, {
      'base-url': 'https://api.dify.ai/v1',
      'api-key': 'app-real-key',
    }),
    true,
  );
});
