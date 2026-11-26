import assert from 'node:assert/strict';
import test from 'node:test';
import { loadTs, locales, loadLocale } from './load-ts.mjs';

const { resolveInstallVersion } = loadTs(
  new URL(
    '../../src/app/home/add-extension/resolve-install-version.ts',
    import.meta.url,
  ),
);
const { installableVersion, isPluginIncompatible } = loadTs(
  new URL('../../src/app/infra/entities/plugin/index.ts', import.meta.url),
);

test('installableVersion prefers compatible_version and falls back on old Space', () => {
  assert.equal(
    installableVersion({
      latest_version: '2.0.0',
      compatible_version: '1.8.0',
    }),
    '1.8.0',
  );
  assert.equal(
    installableVersion({ latest_version: '2.0.0', compatible_version: null }),
    null,
  );
  assert.equal(installableVersion({ latest_version: '2.0.0' }), '2.0.0');
  assert.equal(installableVersion({ latest_version: '' }), null);
});

test('isPluginIncompatible covers incompatible and invalid only', () => {
  for (const status of ['incompatible', 'invalid']) {
    assert.equal(isPluginIncompatible({ status }), true);
  }
  for (const status of ['compatible', 'unspecified']) {
    assert.equal(isPluginIncompatible({ status }), false);
  }
  assert.equal(isPluginIncompatible(undefined), false);
});

test('deep link keeps a compatible requested version', () => {
  assert.deepEqual(
    resolveInstallVersion(
      '1.8.0',
      [
        { version: '2.0.0', compatible: false },
        { version: '1.8.0', compatible: true },
      ],
      { latest_version: '2.0.0', compatible_version: '1.9.0' },
    ),
    { kind: 'install', version: '1.8.0' },
  );
});

test('deep link switches an incompatible version to compatible_version', () => {
  assert.deepEqual(
    resolveInstallVersion(
      '2.0.0',
      [
        { version: '2.0.0', compatible: false },
        { version: '1.8.0', compatible: true },
      ],
      { latest_version: '2.0.0', compatible_version: '1.8.0' },
    ),
    { kind: 'switched', version: '1.8.0', requested: '2.0.0' },
  );
  // Unknown requested version also resolves to the compatible release.
  assert.deepEqual(
    resolveInstallVersion('9.9.9', [], {
      latest_version: '2.0.0',
      compatible_version: '1.8.0',
    }),
    { kind: 'switched', version: '1.8.0', requested: '9.9.9' },
  );
});

test('deep link blocks when no release is compatible', () => {
  assert.deepEqual(
    resolveInstallVersion('2.0.0', [{ version: '2.0.0', compatible: false }], {
      latest_version: '2.0.0',
      compatible_version: null,
    }),
    { kind: 'none' },
  );
});

test('deep link without a version installs compatible_version', () => {
  assert.deepEqual(
    resolveInstallVersion('', null, {
      latest_version: '2.0.0',
      compatible_version: '1.8.0',
    }),
    { kind: 'install', version: '1.8.0' },
  );
});

test('old Space without compatibility data keeps the linked version', () => {
  assert.deepEqual(
    resolveInstallVersion('2.0.0', [{ version: '2.0.0' }], {
      latest_version: '2.0.0',
    }),
    { kind: 'install', version: '2.0.0' },
  );
  assert.deepEqual(
    resolveInstallVersion('', null, { latest_version: '2.0.0' }),
    { kind: 'install', version: '2.0.0' },
  );
});

test('every locale defines the same pluginCompat keys', () => {
  const reference = Object.keys(loadLocale('en-US').pluginCompat).sort();
  assert.ok(reference.length > 0);
  for (const locale of locales) {
    assert.deepEqual(
      Object.keys(loadLocale(locale).pluginCompat).sort(),
      reference,
      locale,
    );
  }
});
