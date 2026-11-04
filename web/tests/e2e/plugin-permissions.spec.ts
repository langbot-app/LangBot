import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

type Permission = {
  id: string;
  category: 'workspace_operations' | 'capabilities';
  required_permissions: string[];
  risk: 'read' | 'write' | 'dangerous';
  granted: boolean;
  grantable: boolean;
};

async function mockPermissions(
  page: Page,
  options: {
    compatibility?: boolean;
    canManage?: boolean;
    upgrade?: boolean;
    blocked?: boolean;
    apiKey?: boolean;
  } = {},
) {
  await installLangBotApiMocks(page, { authenticated: true });
  const permissions: Permission[] = options.compatibility
    ? [
        'langbot.info',
        'bot.read',
        'bot.message.send',
        'bot.platform_api',
        'models.read',
        'models.invoke',
        'storage.plugin',
        'storage.workspace',
        'knowledge.read',
        'knowledge.vector',
        'knowledge.parser',
        'config.read',
        'plugin_tools',
        'mcp',
        'sandbox',
        'plugin.read',
      ].map((id) => ({
        id,
        category: 'capabilities',
        required_permissions: ['resource.manage'],
        risk: id === 'sandbox' ? 'dangerous' : 'write',
        granted: false,
        grantable: !options.blocked,
      }))
    : [
        {
          id: 'stats.basic',
          category: 'workspace_operations',
          required_permissions: ['resource.view'],
          risk: 'read',
          granted: !!options.upgrade,
          grantable: true,
        },
        {
          id: 'bot.message.send',
          category: 'capabilities',
          required_permissions: ['runtime.operate'],
          risk: 'write',
          granted: false,
          grantable: true,
        },
        {
          id: 'sandbox',
          category: 'capabilities',
          required_permissions: ['resource.manage'],
          risk: 'dangerous',
          granted: false,
          grantable: !options.blocked,
        },
      ];
  const state = {
    installation_uuid: 'permission-fixture',
    compatibility_mode: !!options.compatibility,
    pending_confirmation: true,
    enabled: false,
    can_manage: options.canManage ?? true,
    can_confirm: (options.canManage ?? true) && !options.apiKey,
    grants: {
      workspace_operations: options.upgrade
        ? ['stats.basic']
        : ([] as string[]),
      capabilities: [] as string[],
    },
    permissions,
  };
  if (options.apiKey) for (const item of permissions) item.grantable = false;
  const plugin = () => ({
    enabled: state.enabled,
    permission_status: {
      compatibility_mode: state.compatibility_mode,
      pending_confirmation: state.pending_confirmation,
    },
    install_source: 'marketplace',
    install_info: {},
    debug: false,
    components: [],
    manifest: {
      manifest: {
        metadata: {
          author: 'qa',
          name: 'permissions',
          version: options.upgrade ? '2.0.0' : '1.0.0',
          label: { en_US: 'Permission fixture' },
          description: { en_US: 'Permission contract fixture' },
        },
        spec: { config: [] },
      },
    },
  });
  await page.route('**/api/v1/plugins', (route) =>
    route.fulfill({ json: { code: 0, data: { plugins: [plugin()] } } }),
  );
  await page.route('**/api/v1/extensions', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: { extensions: [{ type: 'plugin', plugin: plugin() }] },
      },
    }),
  );
  await page.route('**/api/v1/plugins/qa/permissions', (route) =>
    route.fulfill({ json: { code: 0, data: { plugin: plugin() } } }),
  );
  const writes: {
    confirm: boolean;
    workspace_operations: string[];
    capabilities: string[];
  }[] = [];
  await page.route(
    '**/api/v1/plugins/qa/permissions/permissions',
    async (route) => {
      if (route.request().method() === 'PUT') {
        const body = route.request().postDataJSON();
        writes.push(body);
        state.grants = {
          workspace_operations: body.workspace_operations,
          capabilities: body.capabilities,
        };
        for (const item of permissions)
          item.granted = state.grants[item.category].includes(item.id);
        if (body.confirm) {
          state.pending_confirmation = false;
          state.enabled = true;
        }
      }
      await route.fulfill({ json: { code: 0, data: state } });
    },
  );
  return { writes, state };
}

test('strict installation supports partial grants and a second confirmation', async ({
  page,
}, testInfo) => {
  const { writes } = await mockPermissions(page);
  await page.goto('/home/extensions');
  const review = page.getByRole('region', {
    name: 'Permission confirmation required',
  });
  await expect(review).toBeVisible();
  await review.locator('summary').click();
  await expect(review.getByText('Dangerous', { exact: true })).toBeVisible();
  await expect(
    review.getByText('Sends bot messages', { exact: true }),
  ).toBeVisible();
  await review
    .getByRole('checkbox', { name: 'sandbox', exact: true })
    .uncheck();
  await review
    .getByRole('button', { name: 'Review permissions', exact: true })
    .click();
  expect(writes).toHaveLength(0);
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByText('bot.message.send', { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText('sandbox', { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath('strict-confirmation.png'),
    fullPage: true,
  });
  await dialog
    .getByRole('button', { name: 'Confirm grants', exact: true })
    .click();
  await expect
    .poll(() => writes)
    .toEqual([
      {
        confirm: true,
        workspace_operations: ['stats.basic'],
        capabilities: ['bot.message.send'],
      },
    ]);
  await expect(review).toHaveCount(0);
});

test('compatibility confirmation grants all 16 capabilities and keeps its warning after revocation', async ({
  page,
}, testInfo) => {
  const { writes } = await mockPermissions(page, { compatibility: true });
  await page.goto('/home/extensions?id=qa%2Fpermissions');
  await expect(
    page.getByText('Undeclared permissions', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(16);
  await expect(page.getByRole('checkbox').first()).toBeDisabled();
  await page
    .getByRole('button', { name: 'Review permissions', exact: true })
    .click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm grants', exact: true })
    .click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].capabilities).toHaveLength(16);
  expect(writes[0].workspace_operations).toEqual([]);
  const row = page
    .locator('div.rounded-md.border.p-2')
    .filter({ has: page.getByText('bot.message.send', { exact: true }) });
  await row.getByRole('button', { name: 'Revoke', exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[1].confirm).toBe(false);
  expect(writes[1].capabilities).toHaveLength(15);
  expect(writes[1].capabilities).not.toContain('bot.message.send');
  await expect(row.getByRole('checkbox')).not.toBeChecked();
  await expect(
    page
      .getByRole('alert')
      .filter({ hasText: 'This plugin does not declare permissions' }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('compatibility-revoked.png'),
    fullPage: true,
  });
  await page.goto('/home/extensions');
  await expect(
    page.getByText('Undeclared permissions', { exact: true }),
  ).toBeVisible();
});

test('upgrade preserves existing grants and confirms newly declared permissions', async ({
  page,
}) => {
  const { writes } = await mockPermissions(page, { upgrade: true });
  await page.goto('/home/extensions?id=qa%2Fpermissions');
  await expect(
    page.getByText('Permission confirmation required', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('checkbox', { name: 'stats.basic', exact: true }),
  ).toBeChecked();
  await page
    .getByRole('button', { name: 'Review permissions', exact: true })
    .click();
  await expect(
    page.getByRole('dialog').getByText('sandbox', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm grants', exact: true })
    .click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({
    confirm: true,
    workspace_operations: ['stats.basic'],
    capabilities: ['bot.message.send', 'sandbox'],
  });
});

for (const principal of ['API key', 'missing resource.manage']) {
  test(`${principal} cannot confirm plugin grants`, async ({
    page,
  }, testInfo) => {
    const { writes } = await mockPermissions(page, {
      canManage: principal === 'API key',
      apiKey: principal === 'API key',
      upgrade: true,
    });
    await page.goto('/home/extensions?id=qa%2Fpermissions');
    await expect(
      page.getByRole('button', { name: 'Review permissions', exact: true }),
    ).toBeDisabled();
    const revoke = page.getByRole('button', { name: 'Revoke', exact: true });
    if (principal === 'API key') await expect(revoke).toBeEnabled();
    else await expect(revoke).toBeDisabled();
    await expect(page.getByRole('checkbox').first()).toBeDisabled();
    await expect(
      page.getByText(/Managing plugin permissions requires resource.manage/),
    ).toBeVisible();
    expect(writes).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath('permission-denied.png'),
      fullPage: true,
    });
    if (principal === 'API key') {
      await revoke.click();
      await expect
        .poll(() => writes)
        .toEqual([
          { confirm: false, workspace_operations: [], capabilities: [] },
        ]);
    }
  });
}

test('ungrantable strict permissions are disabled; compatibility cannot partially confirm', async ({
  page,
}) => {
  await mockPermissions(page, { blocked: true });
  await page.goto('/home/extensions?id=qa%2Fpermissions');
  await expect(
    page.getByRole('checkbox', { name: 'sandbox', exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Review permissions', exact: true }),
  ).toBeEnabled();
  await mockPermissions(page, { compatibility: true, blocked: true });
  await page.reload();
  await expect(
    page.getByRole('button', { name: 'Review permissions', exact: true }),
  ).toBeDisabled();
});

test('completed installation remains pending instead of claiming activation', async ({
  page,
}, testInfo) => {
  await mockPermissions(page);
  await page.route('**/api/v1/system/tasks?**', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          tasks: [
            {
              id: 298,
              name: 'plugin-install-marketplace',
              label: 'qa/permissions',
              runtime: { done: true, exception: null },
              task_context: {
                current_action: 'Permission confirmation required',
                metadata: {
                  plugin_name: 'qa/permissions',
                  pending_confirmation: true,
                },
              },
            },
          ],
        },
      },
    }),
  );
  await page.goto('/home/extensions');
  await page.getByRole('button', { name: /Plugin Tasks/ }).click();
  await page.getByText('qa/permissions', { exact: true }).last().click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog
      .getByText('Permission confirmation required', { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    dialog.getByText('Installation successful', { exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath('installed-pending.png'),
    fullPage: true,
  });
  await dialog
    .getByRole('link', { name: 'Review permissions', exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: 'Permission fixture', exact: true }),
  ).toBeVisible();
});
