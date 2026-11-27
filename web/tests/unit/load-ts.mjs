import { readFileSync } from 'node:fs';
import ts from 'typescript';

export function loadTs(url, dependencies = {}) {
  const compiled = ts.transpileModule(readFileSync(url, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    (name) => {
      if (Object.hasOwn(dependencies, name)) return dependencies[name];
      if (name.startsWith('./')) {
        return loadTs(new URL(`${name}.ts`, url), dependencies);
      }
      throw new Error(`Unexpected runtime import in ${url}: ${name}`);
    },
    mod,
    mod.exports,
  );
  return mod.exports;
}

export const locales = [
  'en-US',
  'zh-Hans',
  'zh-Hant',
  'ja-JP',
  'es-ES',
  'ru-RU',
  'th-TH',
  'vi-VN',
];

export function loadLocale(locale) {
  const url = new URL(`../../src/i18n/locales/${locale}.ts`, import.meta.url);
  return loadTs(url).default;
}
