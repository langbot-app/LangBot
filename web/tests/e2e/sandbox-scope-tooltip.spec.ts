import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// UI fixtures only: real app/components, intercepted APIs, no production Box.
// Load the shipped metadata rather than reproducing its tooltip conditions.
const requireFromTest = createRequire(__filename);
const { load } = createRequire(requireFromTest.resolve('eslint'))(
  'js-yaml',
) as {
  load: (source: string) => unknown;
};
const aiMetadata = load(
  readFileSync(
    resolve(
      __dirname,
      '../../../src/langbot/templates/metadata/pipeline/ai.yaml',
    ),
    'utf8',
  ),
);
const unavailableHint = '沙箱未启用，请启用 Box 并确认连接正常后再修改作用域。';
const forcedHint = '已强制使用全局沙箱，无法修改作用域。';

interface BoxState {
  enabled: boolean;
  available: boolean;
}

async function openPipeline(page: Page, box: BoxState, forced = '') {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_language: 'zh-Hans' },
  });
  await page.route('**/api/v1/system/info', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          debug: false,
          version: 'sandbox-scope-ui-fixture',
          edition: 'community',
          cloud_service_url: 'https://space.langbot.app',
          enable_marketplace: true,
          allow_modify_login_info: true,
          disable_models_service: false,
          limitation: {
            max_bots: -1,
            max_pipelines: -1,
            max_extensions: -1,
            force_box_session_id_template: forced,
          },
          outbound_ips: [],
          wizard_status: 'completed',
          wizard_progress: null,
        },
      },
    }),
  );
  await page.route('**/api/v1/box/status', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          ...box,
          profile: 'UI fixture only',
          recent_error_count: 0,
          active_sessions: 0,
          managed_processes: 0,
          session_ttl_sec: 3600,
          backend: { name: 'ui-fixture', available: box.available },
        },
      },
    }),
  );
  await page.route(/\/api\/v1\/tools(?:\?.*)?$/, (route) =>
    route.fulfill({ json: { code: 0, data: { tools: [] } } }),
  );
  await page.route('**/api/v1/pipelines/_/metadata', (route) =>
    route.fulfill({ json: { code: 0, data: { configs: [aiMetadata] } } }),
  );
  await page.route('**/api/v1/pipelines/sandbox-scope-fixture', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          pipeline: {
            uuid: 'sandbox-scope-fixture',
            name: 'Sandbox scope — UI fixture only',
            description: '',
            emoji: '⚙️',
            is_default: false,
            config: {
              ai: {
                runner: { runner: 'local-agent' },
                'local-agent': {
                  'box-session-id-template': '{launcher_type}_{launcher_id}',
                },
              },
              trigger: {},
              safety: {},
              output: {},
            },
          },
        },
      },
    }),
  );
  await page.goto('/home/pipelines?id=sandbox-scope-fixture');
  await page.getByRole('button', { name: 'AI 能力', exact: true }).click();
  // DynamicForm gates this control through its wrapper's pointer-events,
  // and its label targets that wrapper rather than the nested select.
  const scope = page
    .locator('[data-slot="form-item"]')
    .filter({ has: page.getByText('沙箱作用域', { exact: true }) })
    .getByRole('combobox');
  await expect(scope).toBeVisible();
  return scope;
}

async function expectWarning(page: Page, hint: string) {
  const warning = page.getByRole('button', { name: hint, exact: true });
  await expect(warning).toBeVisible();
  await warning.hover();
  await expect(page.getByRole('tooltip')).toHaveText(hint);
}

async function expectNoWarning(page: Page) {
  await expect(page.getByRole('button', { name: unavailableHint })).toHaveCount(
    0,
  );
  await expect(page.getByRole('button', { name: forcedHint })).toHaveCount(0);
  await expect(page.getByRole('tooltip')).toHaveCount(0);
}

test.describe('sandbox scope disabled reason (UI fixtures only)', () => {
  for (const scenario of [
    { name: 'Box disabled', enabled: false, available: false, forced: '' },
    { name: 'Box disconnected', enabled: true, available: false, forced: '' },
    {
      name: 'unavailable Box takes precedence over forced global',
      enabled: true,
      available: false,
      forced: '{global}',
    },
  ]) {
    test(scenario.name, async ({ page }) => {
      const scope = await openPipeline(page, scenario, scenario.forced);
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await expect(page.getByRole('tooltip')).not.toContainText('强制');
      await expect(page.getByRole('button', { name: forcedHint })).toHaveCount(
        0,
      );
    });
  }

  for (const forced of ['{global}', ' {global} ']) {
    test(`available Box with forced global explains the deployment restriction (${JSON.stringify(forced)})`, async ({
      page,
    }) => {
      const scope = await openPipeline(
        page,
        { enabled: true, available: true },
        forced,
      );
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expect(scope).toHaveText('全局（所有人共享）');
      await expectWarning(page, forcedHint);
      await expect(
        page.getByRole('button', { name: unavailableHint }),
      ).toHaveCount(0);
    });
  }

  for (const forced of ['', '   ']) {
    test(`available and unforced Box is editable without a disabled warning (${JSON.stringify(forced)})`, async ({
      page,
    }) => {
      const scope = await openPipeline(
        page,
        { enabled: true, available: true },
        forced,
      );
      await expect(scope).toHaveCSS('pointer-events', 'auto');
      await expect(scope).toHaveText('每个会话（推荐）');
      await expectNoWarning(page);
      await scope.click();
      await page
        .getByRole('option', { name: '全局（所有人共享）', exact: true })
        .click();
      await expect(scope).toHaveText('全局（所有人共享）');
      await expectNoWarning(page);
    });
  }

  for (const forced of ['', '{global}']) {
    test(`Box status polls update the warning without remounting (${forced || 'unforced'})`, async ({
      page,
    }) => {
      await page.clock.install();
      const box = { enabled: true, available: false };
      const scope = await openPipeline(page, box, forced);
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await page.mouse.move(0, 0);

      const recovered = page.waitForResponse('**/api/v1/box/status');
      box.available = true;
      await page.clock.fastForward(31_000);
      await recovered;
      if (forced) {
        await expect(scope).toHaveCSS('pointer-events', 'none');
        await expectWarning(page, forcedHint);
      } else {
        await expect(scope).toHaveCSS('pointer-events', 'auto');
        await expectNoWarning(page);
      }
      await page.mouse.move(0, 0);

      const disconnected = page.waitForResponse('**/api/v1/box/status');
      box.available = false;
      await page.clock.fastForward(31_000);
      await disconnected;
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await expect(page.getByRole('tooltip')).not.toContainText('强制');
    });
  }
});
