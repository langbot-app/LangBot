import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';
import { getBoxScopeContext } from '../../src/app/home/pipelines/components/pipeline-form/BoxScopeContext';

const unavailableHint = '沙箱未启用，请启用 Box 并确认连接正常后再修改作用域。';
const forcedHint = '已强制使用全局沙箱，无法修改作用域。';
const customHint = '已强制使用固定沙箱作用域，无法修改作用域。';

// Exercise the real generic renderer, not a retired local-agent page. Host
// execution scope is not a plugin configuration field; see fixtures/README.md.
async function openConditionForm(page: Page, available: boolean, forced = '') {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_language: 'zh-Hans' },
  });
  const params = new URLSearchParams({ available: String(available), forced });
  await page.goto(`/tests/e2e/fixtures/dynamic-form.html?${params}`);
  const scope = page
    .locator('[data-slot="form-item"]')
    .filter({ has: page.getByText('沙箱作用域', { exact: true }) })
    .getByRole('combobox');
  await expect(scope).toBeVisible();
  return scope;
}

async function updateContext(page: Page, context: Record<string, unknown>) {
  await page.evaluate((detail) => {
    window.dispatchEvent(new CustomEvent('test-form-context', { detail }));
  }, context);
}

async function expectWarning(page: Page, hint: string) {
  const warning = page.getByRole('button', { name: hint, exact: true });
  await expect(warning).toBeVisible();
  await warning.hover();
  await expect(page.getByRole('tooltip')).toHaveText(hint);
}

async function expectNoWarning(page: Page) {
  for (const hint of [unavailableHint, forcedHint, customHint]) {
    await expect(page.getByRole('button', { name: hint })).toHaveCount(0);
  }
  await expect(page.getByRole('tooltip')).toHaveCount(0);
}

test.describe('sandbox condition renderer compatibility (UI fixture only)', () => {
  for (const scenario of [
    { name: 'Box disabled', forced: '' },
    { name: 'Box disconnected', forced: '' },
    {
      name: 'unavailable Box takes precedence over forced global',
      forced: '{global}',
    },
    {
      name: 'unavailable Box takes precedence over forced fixed',
      forced: '{pipeline_id}',
    },
  ]) {
    test(scenario.name, async ({ page }) => {
      const scope = await openConditionForm(page, false, scenario.forced);
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await expect(page.getByRole('tooltip')).not.toContainText('强制');
      await expect(page.getByRole('button', { name: forcedHint })).toHaveCount(
        0,
      );
    });
  }

  for (const forced of ['{global}', ' {global} ', '{pipeline_id}']) {
    test(`available context explains the restriction without rewriting config (${JSON.stringify(forced)})`, async ({
      page,
    }) => {
      const scope = await openConditionForm(page, true, forced);
      await expect(scope).toHaveCSS('pointer-events', 'none');
      // The generic renderer must not coerce values based on a Host policy.
      await expect(scope).toHaveText('每个会话（推荐）');
      await expectWarning(
        page,
        forced.trim() === '{global}' ? forcedHint : customHint,
      );
      await expect(
        page.getByRole('button', { name: unavailableHint }),
      ).toHaveCount(0);
      await expect(page.getByTestId('saved-values')).toContainText(
        '"box-session-id-template":"{launcher_type}_{launcher_id}"',
      );
    });
  }

  for (const forced of ['', '   ']) {
    test(`available unforced context is editable (${JSON.stringify(forced)})`, async ({
      page,
    }) => {
      const scope = await openConditionForm(page, true, forced);
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
    test(`caller context updates the warning without remounting (${forced || 'unforced'})`, async ({
      page,
    }) => {
      const scope = await openConditionForm(page, false, forced);
      const original = await scope.elementHandle();
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await page.mouse.move(0, 0);
      await updateContext(page, getBoxScopeContext(true, forced));
      if (forced) {
        await expect(scope).toHaveCSS('pointer-events', 'none');
        await expectWarning(page, forcedHint);
      } else {
        await expect(scope).toHaveCSS('pointer-events', 'auto');
        await expectNoWarning(page);
      }
      await page.mouse.move(0, 0);
      await updateContext(page, getBoxScopeContext(false, forced));
      await expect(scope).toHaveCSS('pointer-events', 'none');
      await expectWarning(page, unavailableHint);
      await expect(page.getByRole('tooltip')).not.toContainText('强制');
      expect(await original!.evaluate((element) => element.isConnected)).toBe(
        true,
      );
    });
  }

  test('manifest secret and number aliases retain live show/disable conditions', async ({
    page,
  }) => {
    await openConditionForm(page, true);
    const secret = page
      .locator('[data-slot="form-item"]')
      .filter({ has: page.getByText('Plugin secret', { exact: true }) })
      .locator('input');
    await expect(secret).toHaveAttribute('type', 'password');
    await expect(secret).toHaveCSS('pointer-events', 'auto');
    await expect(page.getByRole('spinbutton')).toHaveValue('3');
    await secret.fill('fixture-only-not-a-credential');
    await updateContext(page, { locked: true });
    await expect(secret).toHaveCSS('pointer-events', 'none');
    await expectWarning(page, 'Live reason wins');
    await page.mouse.move(0, 0);
    await page
      .locator('[data-slot="form-item"]')
      .filter({ has: page.getByText('Mode', { exact: true }) })
      .getByRole('combobox')
      .click();
    await page.getByRole('option', { name: 'Hidden', exact: true }).click();
    await expect(secret).toHaveCount(0);
    await expect(page.getByRole('spinbutton')).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: 'Live reason wins' }),
    ).toHaveCount(0);
  });
});

test('pipeline plugin schema round-trips without resurrecting Core sandbox ownership', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_language: 'en-US' },
  });
  const runnerId = 'plugin:qa/conditions/default';
  await page.route('**/api/v1/pipelines/_/metadata', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          configs: [
            {
              name: 'ai',
              label: { en_US: 'AI Feature' },
              stages: [
                {
                  name: 'runner',
                  label: { en_US: 'Runner' },
                  config: [
                    {
                      name: 'id',
                      type: 'select',
                      label: { en_US: 'Runner' },
                      default: runnerId,
                      options: [
                        { name: runnerId, label: { en_US: 'Fixture runner' } },
                      ],
                    },
                  ],
                },
                {
                  name: runnerId,
                  label: { en_US: 'Plugin settings' },
                  config: [
                    {
                      name: 'note',
                      type: 'string',
                      label: { en_US: 'Plugin note' },
                      default: '',
                      show_if: {
                        field: '__system.pipeline_id',
                        operator: 'eq',
                        value: 'pipeline-scope-fixture',
                      },
                    },
                  ],
                },
              ],
            },
          ],
        },
      },
    }),
  );
  const pipeline = {
    uuid: 'pipeline-scope-fixture',
    name: 'Plugin scope fixture',
    description: '',
    emoji: '⚙️',
    is_default: false,
    config: {
      ai: {
        runner: { id: runnerId },
        runner_config: { [runnerId]: { note: 'original' } },
      },
      trigger: {},
      safety: {},
      output: {},
    },
  };
  let saved: typeof pipeline | undefined;
  await page.route(
    '**/api/v1/pipelines/pipeline-scope-fixture',
    async (route) => {
      if (route.request().method() === 'PUT') {
        saved = route.request().postDataJSON();
        await route.fulfill({ json: { code: 0, data: {} } });
      } else {
        await route.fulfill({ json: { code: 0, data: { pipeline } } });
      }
    },
  );
  await page.goto('/home/pipelines?id=pipeline-scope-fixture');
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  await expect(
    page.getByRole('region', { name: 'Configuration' }).getByRole('textbox'),
  ).toHaveValue('original');
  await expect(page.getByText('Sandbox Scope', { exact: true })).toHaveCount(0);
  await page
    .getByRole('region', { name: 'Configuration' })
    .getByRole('textbox')
    .fill('round-trip');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect
    .poll(() => saved?.config.ai)
    .toEqual({
      runner: { id: runnerId },
      runner_config: { [runnerId]: { note: 'round-trip' } },
    });
});
