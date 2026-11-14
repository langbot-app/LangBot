import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import ts from 'typescript';
import jsxRuntime from 'react/jsx-runtime';

const nodeRequire = createRequire(import.meta.url);

const dir = path.dirname(fileURLToPath(import.meta.url));

function loadTs(relPath, deps = {}) {
  const src = fs.readFileSync(path.resolve(dir, relPath), 'utf8');
  const out = ts.transpileModule(src, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const mod = { exports: {} };
  const req = (id) => {
    if (id in deps) return deps[id];
    if (id === 'react/jsx-runtime') return jsxRuntime;
    return nodeRequire(id);
  };
  new Function('require', 'module', 'exports', out)(req, mod, mod.exports);
  return mod.exports;
}

test('renders a link per distinct follow-up', () => {
  const follow = loadTs(
    '../../src/app/home/plugins/components/plugin-install-task/plugin-follow-up.ts',
  );
  const comp = loadTs(
    '../../src/app/home/plugins/components/plugin-install-task/PluginInstallFollowUp.tsx',
    {
      'react-router-dom': {
        Link: ({ to, children, ...p }) =>
          React.createElement('a', { href: to, ...p }, children),
      },
      'react-i18next': {
        useTranslation: () => ({ t: (k) => k.split('.').pop() }),
      },
      'lucide-react': new Proxy(
        {},
        { get: () => () => React.createElement('i') },
      ),
      './plugin-follow-up': follow,
    },
  );
  const plugin = {
    components: [
      { manifest: { manifest: { kind: 'Runner' } } },
      { manifest: { manifest: { kind: 'Tool' } } },
      { manifest: { manifest: { kind: 'Command' } } },
      { manifest: { manifest: { kind: 'KnowledgeEngine' } } },
    ],
  };
  const html = renderToStaticMarkup(
    React.createElement(comp.default, { plugin }),
  );
  console.log(html);
  assert.equal(
    (html.match(/href="\/home\/pipelines\?id=new"/g) || []).length,
    1,
    'pipeline once',
  );
  assert.equal((html.match(/href="\/home\/agents\?id=new"/g) || []).length, 1);
  assert.equal(
    (html.match(/href="\/home\/knowledge\?id=new"/g) || []).length,
    1,
  );
});

test('renders nothing without a follow-up component', () => {
  const follow = loadTs(
    '../../src/app/home/plugins/components/plugin-install-task/plugin-follow-up.ts',
  );
  const comp = loadTs(
    '../../src/app/home/plugins/components/plugin-install-task/PluginInstallFollowUp.tsx',
    {
      'react-router-dom': {
        Link: ({ to, children, ...p }) =>
          React.createElement('a', { href: to, ...p }, children),
      },
      'react-i18next': { useTranslation: () => ({ t: (k) => k }) },
      'lucide-react': new Proxy(
        {},
        { get: () => () => React.createElement('i') },
      ),
      './plugin-follow-up': follow,
    },
  );
  const html = renderToStaticMarkup(
    React.createElement(comp.default, {
      plugin: { components: [{ manifest: { manifest: { kind: 'Parser' } } }] },
    }),
  );
  assert.equal(html, '');
});
