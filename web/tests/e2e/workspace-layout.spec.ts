import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

const cloudSystemInfo = {
  edition: 'cloud',
  deployment_mode: 'cloud',
  cloud_service_url: 'https://space.langbot.app',
  wizard_status: 'completed',
};

for (const scenario of [
  'singleton-local',
  'singleton-cloud',
  'multiple',
] as const) {
  test(`Workspace switcher visibility and placement for ${scenario}`, async ({
    page,
  }) => {
    const first = makeWorkspaceEntry(
      'layout-workspace',
      'A Workspace with a deliberately very long name to exercise truncation',
      scenario === 'singleton-local' ? 'local' : 'cloud_projection',
    );
    const workspaces =
      scenario === 'multiple'
        ? [first, makeWorkspaceEntry('other-workspace', 'Other', 'local')]
        : [first];
    await installLangBotApiMocks(page, {
      authenticated: true,
      workspaces,
      storage: { langbot_active_workspace_uuid: first.workspace.uuid },
    });
    if (scenario !== 'singleton-local') {
      await page.route('**/api/v1/system/info', (route) =>
        route.fulfill({ json: { code: 0, data: cloudSystemInfo } }),
      );
      await page.route(
        /\/api\/v1\/workspaces\/layout-workspace\/(members|invitations)$/,
        (route) =>
          route.fulfill({
            json: { code: 0, data: { members: [], invitations: [] } },
          }),
      );
    }
    await page.goto('/home/bots');
    await expect(
      page.getByRole('button', { name: 'Models', exact: true }),
    ).toBeVisible();
    const trigger = page.getByRole('button', {
      name: 'Switch Workspace',
      exact: true,
    });
    await expect(trigger).toHaveCount(scenario === 'singleton-local' ? 0 : 1);
    if (scenario === 'singleton-local') return;
    const upgrade = page.getByRole('button', {
      name: 'Change or upgrade plan',
      exact: true,
    });
    await expect(upgrade).toHaveCount(1);
    const sidebar = page.locator('[data-slot="sidebar-inner"]');
    const header = sidebar.locator('[data-slot="sidebar-header"]');
    const home = sidebar.getByText('Home', { exact: true });
    const navigation = sidebar.getByRole('button', {
      name: 'Models',
      exact: true,
    });
    const [headerBox, triggerBox, homeBox, navBox, upgradeBox] =
      await Promise.all([
        header.boundingBox(),
        trigger.boundingBox(),
        home.boundingBox(),
        navigation.boundingBox(),
        upgrade.boundingBox(),
      ]);
    expect(triggerBox!.y).toBeGreaterThanOrEqual(
      headerBox!.y + headerBox!.height,
    );
    expect(triggerBox!.y + triggerBox!.height).toBeLessThanOrEqual(homeBox!.y);
    expect(Math.abs(triggerBox!.x - navBox!.x)).toBeLessThanOrEqual(1);
    // The upgrade control shares the switcher row and owns its trailing edge,
    // so the row stays flush with the navigation column while the switcher
    // itself ends before the control.
    expect(Math.abs(triggerBox!.y - upgradeBox!.y)).toBeLessThanOrEqual(1);
    expect(upgradeBox!.x).toBeGreaterThanOrEqual(
      triggerBox!.x + triggerBox!.width,
    );
    expect(
      Math.abs(upgradeBox!.x + upgradeBox!.width - navBox!.x - navBox!.width),
    ).toBeLessThanOrEqual(1);
    await expect(upgrade).toBeVisible();
    // The upgrade control is deliberately styled like the workspace switcher:
    // same height, same visible outline, so the two read as one control row.
    expect(
      Math.abs(upgradeBox!.height - triggerBox!.height),
    ).toBeLessThanOrEqual(1);
    for (const control of [trigger, upgrade]) {
      const outline = await control.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          width: parseFloat(style.borderTopWidth),
          color: style.borderTopColor,
          style: style.borderTopStyle,
        };
      });
      expect(outline.style).not.toBe('none');
      expect(outline.width).toBeGreaterThan(0);
      expect(outline.color).not.toBe('rgba(0, 0, 0, 0)');
    }
    await trigger.click();
    const row = page
      .getByRole('menuitem')
      .filter({ hasText: first.workspace.name });
    await expect(row).toBeVisible();
    await expect(
      row.getByRole('button', { name: 'Workspace Settings', exact: true }),
    ).toBeVisible();
    const longName = row.getByText(first.workspace.name, { exact: true });
    expect(
      await longName.evaluate((element) => ({
        overflow: getComputedStyle(element).textOverflow,
        whiteSpace: getComputedStyle(element).whiteSpace,
        clipped: element.scrollWidth > element.clientWidth,
      })),
    ).toEqual({ overflow: 'ellipsis', whiteSpace: 'nowrap', clipped: true });
    await row
      .getByRole('button', { name: 'Workspace Settings', exact: true })
      .click();
    await expect(
      page
        .getByRole('dialog')
        .getByRole('heading', { name: 'Workspace', exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByRole('dialog')
        .getByRole('heading', { name: 'Members', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: 'Switch Workspace',
        exact: true,
        includeHidden: true,
      }),
    ).toHaveCount(1);
  });
}

test('the Cloud Workspace row shows its plan and opens plan upgrades in settings', async ({
  page,
}) => {
  const workspace = {
    ...makeWorkspaceEntry(
      'plan-workspace',
      'Plan Workspace',
      'cloud_projection',
    ),
    plan_name: 'Pro',
  };
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  await page.route('**/api/v1/system/info', (route) =>
    route.fulfill({ json: { code: 0, data: cloudSystemInfo } }),
  );
  await page.route('**/api/v1/workspaces/plan-workspace/members', (route) =>
    route.fulfill({ json: { code: 0, data: { members: [] } } }),
  );
  await page.route('**/api/v1/workspaces/plan-workspace/invitations', (route) =>
    route.fulfill({ json: { code: 0, data: { invitations: [] } } }),
  );
  let catalogs = 0;
  await page.route(
    'https://space.langbot.app/api/v1/cloud/v2/plans',
    async (route) => {
      catalogs++;
      await route.fulfill({ json: { code: 0, data: [] } });
    },
  );
  await page.goto('/home/bots');
  await page
    .getByRole('button', { name: 'Switch Workspace', exact: true })
    .click();
  const row = page.getByRole('menuitem').filter({ hasText: 'Plan Workspace' });
  await expect(row.getByText('Pro', { exact: true })).toBeVisible();
  await row
    .getByRole('button', { name: 'Workspace Settings', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('button', { name: 'Compare plans', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Compare plans', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('dialog', { includeHidden: true })).toHaveCount(
    2,
  );
  await expect.poll(() => catalogs).toBeGreaterThan(0);
});

test('monitoring uses infrastructure Box health independently of Plugin Runtime status', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let runtimeRequests = 0;
  let scopedStatusRequests = 0;
  await page.route('**/api/v1/box/runtime-status', async (route) => {
    runtimeRequests++;
    await route.fulfill({
      json: {
        code: 0,
        data: {
          available: false,
          enabled: true,
          connector_error: 'Box infrastructure unavailable',
        },
      },
    });
  });
  await page.route('**/api/v1/box/status', async (route) => {
    scopedStatusRequests++;
    await route.fulfill({
      json: { code: 0, data: { available: true, enabled: true } },
    });
  });
  await page.goto('/home/monitoring');
  const card = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'System Status' });
  await expect(card.getByText('Box Runtime', { exact: true })).toBeVisible();
  await card.getByRole('button').click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByText('Box infrastructure unavailable', { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText('Connected', { exact: true })).toHaveCount(1);
  await expect(dialog.getByText('Disconnected', { exact: true })).toHaveCount(
    1,
  );
  expect(runtimeRequests).toBeGreaterThan(0);
  expect(scopedStatusRequests).toBe(0);
});
