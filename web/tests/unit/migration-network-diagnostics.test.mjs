import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import jsxRuntime from 'react/jsx-runtime';
import icons from 'lucide-react';
import { loadLocale, locales, loadTs } from './load-ts.mjs';

const diagnosticKeys = [
  'timeout',
  'connection',
  'incomplete',
  'http',
  'network',
];
const en = loadLocale('en-US');

test('every runtime catalog provides translated diagnostics without a URL or raw diagnostic interpolation', () => {
  for (const locale of locales) {
    const diagnostics = loadLocale(locale).pipelineMigration.networkDiagnostics;
    for (const key of diagnosticKeys) {
      const message = diagnostics[key];
      assert.equal(typeof message, 'string', `${locale}.${key}`);
      assert.ok(message.trim(), `${locale}.${key}`);
      assert.doesNotMatch(
        message,
        /https?:\/\/|\{\{kind\}\}/,
        `${locale}.${key}`,
      );
    }
  }
});

// Render the real component while leaving only presentation wrappers and
// optional marketplace transport out of this server-side unit test.
const wrapper = ({ children }) => React.createElement('div', null, children);
const { default: MigrationInstallProgress } = loadTs(
  new URL(
    '../../src/app/home/pipelines/MigrationInstallProgress.tsx',
    import.meta.url,
  ),
  {
    react: React,
    'react/jsx-runtime': jsxRuntime,
    'react-i18next': {
      useTranslation: () => ({
        t: (key, options) =>
          key.split('.').reduce((node, part) => node?.[part], en) ??
          options?.defaultValue ??
          key,
      }),
    },
    'lucide-react': icons,
    '@/app/infra/http': {
      getCloudServiceClientSync: () => ({
        resolveMarketplaceIconURL: () => undefined,
      }),
    },
    '@/i18n/I18nProvider': { extractI18nObject: () => undefined },
    '@/components/ui/button': { Button: wrapper },
    '@/components/ui/badge': { Badge: wrapper },
    '@/components/ui/progress': { Progress: wrapper },
    '@/components/ui/avatar': {
      Avatar: wrapper,
      AvatarImage: wrapper,
      AvatarFallback: wrapper,
    },
    '@/components/ui/collapsible': {
      Collapsible: wrapper,
      CollapsibleContent: wrapper,
      CollapsibleTrigger: wrapper,
    },
  },
);

function renderDiagnostic(kind, httpStatus, status = 'failed') {
  return renderToStaticMarkup(
    React.createElement(MigrationInstallProgress, {
      installations: [
        {
          author: 'example',
          name: 'demo',
          version: '1.0',
          stage: 'downloading',
          status,
          started_at: 1,
          updated_at: 2,
          steps: [],
          diagnostic: { kind, http_status: httpStatus },
        },
      ],
    }),
  );
}

test('renders the translated network failure reason rather than the internal code', () => {
  for (const [kind, key] of [
    ['connect_timeout', 'timeout'],
    ['read_timeout', 'timeout'],
    ['write_timeout', 'timeout'],
    ['pool_timeout', 'timeout'],
    ['connect_error', 'connection'],
    ['incomplete_response', 'incomplete'],
    ['http_status', 'http'],
    ['unknown_network_diagnostic', 'network'],
  ]) {
    const markup = renderDiagnostic(kind);
    assert.ok(
      markup.includes(en.pipelineMigration.networkDiagnostics[key]),
      kind,
    );
    assert.ok(!markup.includes(kind), kind);
  }
});

test('renders only valid numeric HTTP statuses on failed installations', () => {
  for (const status of [100, 503, 599]) {
    assert.ok(
      renderDiagnostic('http_status', status).includes(`(HTTP ${status})`),
      String(status),
    );
  }
  for (const status of [undefined, 99, 600, 503.5, '503']) {
    assert.doesNotMatch(
      renderDiagnostic('http_status', status),
      /\(HTTP /,
      JSON.stringify(status),
    );
  }
  const nonFailure = renderDiagnostic('http_status', 503, 'installing');
  assert.ok(!nonFailure.includes(en.pipelineMigration.networkDiagnostics.http));
  assert.doesNotMatch(nonFailure, /\(HTTP /);
});
