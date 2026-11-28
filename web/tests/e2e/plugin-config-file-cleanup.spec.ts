import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// The config read API masks sensitive keys (including nested file_key) as ***.
const REDACTED_CONFIG = {
  name: 'demo',
  private_key: { file_key: '***', mimetype: '***' },
  logo: { file_key: 'old_logo.png', mimetype: 'image/png' },
};

async function mockPluginConfig(
  page: Page,
  options: { failSave?: boolean } = {},
) {
  await installLangBotApiMocks(page, { authenticated: true });
  const plugin = {
    enabled: true,
    permission_status: {
      compatibility_mode: false,
      pending_confirmation: false,
    },
    install_source: 'marketplace',
    install_info: {},
    debug: false,
    components: [],
    manifest: {
      manifest: {
        metadata: {
          author: 'qa',
          name: 'files',
          version: '1.0.0',
          label: { en_US: 'File config fixture' },
          description: { en_US: 'File config fixture' },
        },
        spec: {
          config: [
            {
              name: 'name',
              type: 'string',
              label: { en_US: 'Name' },
              required: false,
              default: '',
            },
            {
              name: 'private_key',
              type: 'file',
              label: { en_US: 'Private key' },
              required: false,
              default: null,
            },
            {
              name: 'logo',
              type: 'file',
              label: { en_US: 'Logo' },
              required: false,
              default: null,
            },
          ],
        },
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
  await page.route('**/api/v1/plugins/qa/files', (route) =>
    route.fulfill({ json: { code: 0, data: { plugin } } }),
  );
  const saves: Record<string, unknown>[] = [];
  await page.route('**/api/v1/plugins/qa/files/config', async (route) => {
    if (route.request().method() === 'PUT') {
      saves.push(route.request().postDataJSON());
      if (options.failSave)
        return route.fulfill({ status: 500, json: { code: -1, msg: 'boom' } });
      return route.fulfill({ json: { code: 0, data: {} } });
    }
    return route.fulfill({
      json: { code: 0, data: { config: structuredClone(REDACTED_CONFIG) } },
    });
  });
  let uploads = 0;
  await page.route('**/api/v1/plugins/config-files', (route) => {
    uploads += 1;
    return route.fulfill({
      json: { code: 0, data: { file_key: `plugin_config_new_${uploads}.bin` } },
    });
  });
  const deletes: string[] = [];
  await page.route('**/api/v1/plugins/config-files/*', (route) => {
    deletes.push(decodeURIComponent(route.request().url().split('/').pop()!));
    return route.fulfill({ json: { code: 0, data: { deleted: true } } });
  });
  await page.goto('/home/extensions?id=qa%2Ffiles');
  await expect(page.getByText('old_logo.png')).toBeVisible();
  return { saves, deletes };
}

async function upload(page: Page, field: string, name: string) {
  await page.locator(`#file-input-${field}`).setInputFiles({
    name,
    mimeType: 'application/octet-stream',
    buffer: Buffer.from(name),
  });
}

function fileCard(page: Page, fileKey: string) {
  return page.locator(`div[title="${fileKey}"]`);
}

async function removeFile(page: Page, fileKey: string) {
  await page
    .locator('div.flex.items-center', { has: fileCard(page, fileKey) })
    .getByRole('button', { name: 'Delete' })
    .click();
  await expect(fileCard(page, fileKey)).toHaveCount(0);
}

async function save(page: Page) {
  await page.getByRole('button', { name: 'Save Config', exact: true }).click();
}

test('new file in a sensitive field survives save and the mask is never deleted', async ({
  page,
}) => {
  const { saves, deletes } = await mockPluginConfig(page);
  await removeFile(page, '***');
  await upload(page, 'private_key', 'key.pem');
  await expect(fileCard(page, 'plugin_config_new_1.bin')).toBeVisible();
  await save(page);
  await expect.poll(() => saves.length).toBe(1);
  expect(saves[0].private_key).toMatchObject({
    file_key: 'plugin_config_new_1.bin',
  });
  expect(saves[0].logo).toMatchObject({ file_key: 'old_logo.png' });
  await page.waitForTimeout(500);
  expect(deletes).toEqual([]);
});

test('replacing a file deletes the old one and unused uploads only', async ({
  page,
}) => {
  const { saves, deletes } = await mockPluginConfig(page);
  await removeFile(page, 'old_logo.png');
  await upload(page, 'logo', 'a.png');
  await removeFile(page, 'plugin_config_new_1.bin');
  await upload(page, 'logo', 'b.png');
  await expect(fileCard(page, 'plugin_config_new_2.bin')).toBeVisible();
  await save(page);
  await expect.poll(() => saves.length).toBe(1);
  expect(saves[0].logo).toMatchObject({ file_key: 'plugin_config_new_2.bin' });
  // Unmodified sensitive field is sent back masked; server restores it.
  expect(saves[0].private_key).toMatchObject({ file_key: '***' });
  await expect
    .poll(() => deletes.slice().sort())
    .toEqual(['old_logo.png', 'plugin_config_new_1.bin']);
});

test('saving without file changes deletes nothing', async ({ page }) => {
  const { saves, deletes } = await mockPluginConfig(page);
  await save(page);
  await expect.poll(() => saves.length).toBe(1);
  expect(saves[0]).toMatchObject(REDACTED_CONFIG);
  await page.waitForTimeout(500);
  expect(deletes).toEqual([]);
});

test('a failed save deletes nothing', async ({ page }) => {
  const { saves, deletes } = await mockPluginConfig(page, { failSave: true });
  await removeFile(page, 'old_logo.png');
  await upload(page, 'logo', 'a.png');
  await expect(fileCard(page, 'plugin_config_new_1.bin')).toBeVisible();
  await save(page);
  await expect.poll(() => saves.length).toBe(1);
  await page.waitForTimeout(500);
  expect(deletes).toEqual([]);
});
