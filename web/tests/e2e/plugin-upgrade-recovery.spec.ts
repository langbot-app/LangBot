import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const entry of ['list', 'sidebar'] as const) {
  test(`plugin upgrade from ${entry} recovers its operation and progress after reload`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    let upgrades = 0,
      phase: 'checking' | 'validating' | 'launching' | 'done' | 'failed' =
        'checking';
    const task = () => ({
      id: 80,
      name: 'plugin-upgrade-qa/upgradable',
      label: 'qa/upgradable',
      runtime: {
        done: phase === 'done' || phase === 'failed',
        exception: phase === 'failed' ? 'Signature rejected fixture' : null,
      },
      task_context: {
        current_action: {
          checking: 'Checking update',
          validating: 'Validating package',
          launching: 'Waiting for plugin to become ready',
          done: 'Plugin updated',
          failed: 'Validating package',
        }[phase],
        metadata: { plugin_name: 'qa/upgradable', operation: 'upgrade' },
      },
    });
    const plugin = {
      install_source: 'marketplace',
      install_info: {},
      debug: false,
      manifest: {
        manifest: {
          metadata: {
            author: 'qa',
            name: 'upgradable',
            label: { en_US: 'Upgrade Fixture' },
            version: '1.0.0',
            description: { en_US: 'Upgrade fixture plugin' },
          },
          spec: {},
        },
      },
    };
    await page.route('**/api/v1/plugins', (route) =>
      route.fulfill({ json: { code: 0, data: { plugins: [plugin] } } }),
    );
    await page.route('**/api/v1/extensions', (route) =>
      route.fulfill({
        json: { code: 0, data: { extensions: [{ type: 'plugin', plugin }] } },
      }),
    );
    await page.route(
      '**/api/v1/plugins/qa/upgradable/upgrade',
      async (route) => {
        upgrades++;
        expect(route.request().method()).toBe('POST');
        await route.fulfill({ json: { code: 0, data: { task_id: 80 } } });
      },
    );
    await page.route('**/api/v1/system/tasks?**', (route) =>
      route.fulfill({
        json: { code: 0, data: { tasks: upgrades ? [task()] : [] } },
      }),
    );
    await page.route('**/api/v1/system/tasks/80', (route) =>
      route.fulfill({ json: { code: 0, data: task() } }),
    );
    await page.goto('/home/extensions');
    if (entry === 'list') {
      const card = page
        .locator('[data-slot="card"]')
        .filter({ has: page.getByText('Upgrade Fixture', { exact: true }) });
      await card.getByRole('button').last().click();
    } else {
      const item = page
        .locator('[data-slot="sidebar-menu-sub-item"]')
        .filter({ has: page.getByRole('link', { name: /Upgrade Fixture/ }) });
      await item.hover();
      await item.getByRole('button').click();
    }
    await page
      .getByRole('menuitem', { name: 'Update Plugin', exact: true })
      .click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Confirm Update', exact: true })
      .click();
    let dialog = page.getByRole('dialog');
    await expect(
      dialog.getByRole('heading', {
        name: 'Updating qa/upgradable',
        exact: true,
      }),
    ).toBeVisible();
    await expect.poll(() => upgrades).toBe(1);
    phase = 'validating';
    await expect(dialog.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '45',
    );
    await page.reload();
    await page.getByRole('button', { name: /Plugin Tasks/ }).click();
    await page.getByText('qa/upgradable', { exact: true }).click();
    dialog = page.getByRole('dialog');
    await expect(
      dialog.getByRole('heading', {
        name: 'Updating qa/upgradable',
        exact: true,
      }),
    ).toBeVisible();
    await expect(dialog.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '45',
    );
    phase = 'launching';
    await expect
      .poll(async () =>
        Number(
          await dialog.getByRole('progressbar').getAttribute('aria-valuenow'),
        ),
      )
      .toBeGreaterThanOrEqual(88);
    phase = entry === 'list' ? 'done' : 'failed';
    if (phase === 'done') {
      await expect(
        dialog.getByText('Plugin updated successfully', { exact: true }),
      ).toBeVisible();
      await expect(dialog.getByRole('progressbar')).toHaveAttribute(
        'aria-valuenow',
        '100',
      );
    } else
      await expect(
        dialog.getByText('Signature rejected fixture', { exact: true }),
      ).toBeVisible();
    expect(upgrades).toBe(1);
  });
}
