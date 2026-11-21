import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('the document picker accepts formats provided by an installed parser', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    language: 'en-US',
  });
  const mime =
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  const parser = {
    plugin_id: 'qa/sheets',
    name: { en_US: 'Spreadsheet parser' },
    supported_mime_types: [mime],
  };
  const base = {
    uuid: 'sheets',
    name: 'Sheets',
    knowledge_engine: { capabilities: ['doc_ingestion'] },
  };
  await page.route('**/api/v1/knowledge/bases/sheets', (route) =>
    route.fulfill({ json: { code: 0, data: { base } } }),
  );
  await page.route('**/api/v1/knowledge/parsers?*', (route) => {
    const requested = new URL(route.request().url()).searchParams.get(
      'mime_type',
    );
    return route.fulfill({
      json: { code: 0, data: { parsers: requested === mime ? [parser] : [] } },
    });
  });
  await page.route('**/api/v1/files/documents', (route) =>
    route.fulfill({ json: { code: 0, data: { file_id: 'workbook.xlsx' } } }),
  );
  await page.route('**/api/v1/knowledge/bases/sheets/files', (route) =>
    route.fulfill({ json: { code: 0, data: { files: [] } } }),
  );

  await page.goto('/home/knowledge?id=sheets');
  await page.getByRole('tab', { name: 'Documents' }).click();
  const fileInput = page.locator('input[type=file]');
  await expect(fileInput).toHaveJSProperty('accept', '');
  const chooser = page.waitForEvent('filechooser');
  await page.locator('label[for=file-upload]').click();
  await (
    await chooser
  ).setFiles({
    name: 'workbook.xlsx',
    mimeType: mime,
    buffer: Buffer.from('fixture'),
  });
  await expect(page.getByRole('combobox')).toContainText('Spreadsheet parser');
  const upload = page.waitForRequest(
    (request) =>
      request.method() === 'POST' &&
      request.url().endsWith('/knowledge/bases/sheets/files'),
  );
  await page.getByRole('button', { name: 'Upload', exact: true }).click();
  expect((await upload).postDataJSON()).toEqual({
    file_id: 'workbook.xlsx',
    parser_plugin_id: 'qa/sheets',
  });
});
