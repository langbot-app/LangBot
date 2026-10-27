import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/home/plugins/components/plugin-install-task/install-progress.ts',
);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const sourceRequire = createRequire(sourcePath);
const loadedModule = { exports: {} };
new Function('require', 'module', 'exports', compiled)(
  sourceRequire,
  loadedModule,
  loadedModule.exports,
);

const {
  InstallStage,
  STAGE_PROGRESS_RANGE,
  computeStageProgress,
  mapActionToStage,
} = loadedModule.exports;

test('maps the connector stage strings the runtime actually emits', () => {
  assert.equal(
    mapActionToStage('preparing plugin install'),
    InstallStage.DOWNLOADING,
    '"preparing plugin install" must not be read as the dependency stage',
  );
  assert.equal(
    mapActionToStage('downloading plugin package'),
    InstallStage.DOWNLOADING,
  );
  assert.equal(
    mapActionToStage('inspecting plugin package'),
    InstallStage.INSTALLING_DEPS,
  );
  assert.equal(
    mapActionToStage('storing plugin package'),
    InstallStage.INSTALLING_DEPS,
  );
  assert.equal(
    mapActionToStage('persisting the installation'),
    InstallStage.INSTALLING_DEPS,
  );
  assert.equal(mapActionToStage('launching plugin'), InstallStage.LAUNCHING);
  assert.equal(
    mapActionToStage('waiting for plugin to become ready'),
    InstallStage.LAUNCHING,
    'the readiness wait is still an active stage, not completion',
  );
});

test('the combined install-and-start stage is not reported as launching', () => {
  // The runtime installs dependencies and starts the plugin in one step; the
  // wording contains "starting" and must not be mapped to the launch stage.
  assert.equal(
    mapActionToStage('installing or starting plugin'),
    InstallStage.INSTALLING_DEPS,
  );
});

test('measured byte counts stay inside the download stage range', () => {
  const [start, end] = STAGE_PROGRESS_RANGE[InstallStage.DOWNLOADING];

  // 90 of 100 bytes is 90% of the download range, even after 40s elapsed.
  const progress = computeStageProgress({
    stage: InstallStage.DOWNLOADING,
    downloadCurrent: 90,
    downloadTotal: 100,
    stageElapsedSeconds: 40,
  });

  assert.ok(
    progress >= start && progress <= end,
    `expected progress within [${start}, ${end}], received ${progress}`,
  );
  assert.equal(
    progress,
    41,
    'drift must not be layered on top of a measured byte ratio',
  );
});

test('fallback drift advances within fixed stage boundaries', () => {
  const stages = [
    [InstallStage.DOWNLOADING, 5, 25, 44],
    [InstallStage.INSTALLING_DEPS, 45, 65, 84],
    [InstallStage.INITIALIZING, 85, 87, 87],
    [InstallStage.LAUNCHING, 88, 92, 96],
  ];

  for (const [stage, start, midpoint, ceiling] of stages) {
    const progressAt = (stageElapsedSeconds) =>
      computeStageProgress({ stage, stageElapsedSeconds });
    assert.equal(progressAt(0), start);
    assert.equal(progressAt(1), start);
    assert.equal(progressAt(4), start + 2);
    assert.equal(progressAt((midpoint - start) * 2), midpoint);
    assert.equal(progressAt(100000), ceiling);
  }
});

test('preserves Host stage progress when byte counts are unavailable', () => {
  assert.equal(
    computeStageProgress({
      stage: InstallStage.DOWNLOADING,
      reportedProgress: 23,
      stageElapsedSeconds: 0,
    }),
    23,
  );
  assert.equal(
    computeStageProgress({
      stage: InstallStage.INSTALLING_DEPS,
      reportedProgress: 64,
      stageElapsedSeconds: 0,
    }),
    64,
  );
  assert.equal(
    mapActionToStage('checking plugin update'),
    InstallStage.CHECKING,
  );
  assert.equal(
    mapActionToStage('validating plugin package'),
    InstallStage.VALIDATING,
  );
  assert.equal(
    mapActionToStage('applying plugin update'),
    InstallStage.INSTALLING_DEPS,
  );
  assert.equal(
    mapActionToStage('refreshing plugin components'),
    InstallStage.LAUNCHING,
  );
  assert.equal(mapActionToStage('plugin updated'), InstallStage.DONE);
});

test('measured bytes override Host coarse progress and fallback stays bounded', () => {
  assert.equal(
    computeStageProgress({
      stage: InstallStage.DOWNLOADING,
      downloadCurrent: 90,
      downloadTotal: 100,
      reportedProgress: 15,
      stageElapsedSeconds: 40,
    }),
    41,
  );
  for (const reportedProgress of [-5, 100]) {
    const progress = computeStageProgress({
      stage: InstallStage.DOWNLOADING,
      reportedProgress,
      stageElapsedSeconds: 0,
    });
    assert.ok(progress >= 5 && progress <= 45);
  }
});

test('a missing or zero download total advances using fallback drift', () => {
  for (const downloadTotal of [undefined, 0]) {
    for (const [stageElapsedSeconds, expected] of [
      [0, 5],
      [4, 7],
      [20, 15],
      [100000, 44],
    ]) {
      assert.equal(
        computeStageProgress({
          stage: InstallStage.DOWNLOADING,
          downloadCurrent: 10,
          downloadTotal,
          stageElapsedSeconds,
        }),
        expected,
        `download total ${downloadTotal}, elapsed ${stageElapsedSeconds}s`,
      );
    }
  }
});
