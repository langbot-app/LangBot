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

const { ensureHttpBotSigningSecret, getErrorMessage } = loadWizardUtils();

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
