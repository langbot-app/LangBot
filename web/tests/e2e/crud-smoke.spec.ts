import { expect, Page, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

async function save(page: Page) {
  const button = page.getByRole('button', { name: /^Save$/ });
  await expect(button).toBeEnabled();
  await button.click();
}

async function submit(page: Page) {
  await page.getByRole('button', { name: /^Submit$/ }).click();
}

async function confirmDelete(page: Page) {
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^Confirm Delete$/ })
    .click();
}

test.describe('frontend CRUD smoke flows', () => {
  test('creates, edits, and deletes a pipeline', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/pipelines?id=new');

    await expect(page.locator('input[name="basic.name"]')).toBeVisible();
    await page.locator('input[name="basic.name"]').fill('Escalation Pipeline');
    await page
      .locator('input[name="basic.description"]')
      .fill('Routes urgent customer issues.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/pipelines\?id=pipeline-1$/);
    await page.reload();
    await expect(page.locator('input[name="basic.name"]')).toHaveValue(
      'Escalation Pipeline',
    );

    await page
      .locator('input[name="basic.description"]')
      .fill('Routes urgent customer issues to operators.');
    await save(page);
    await expect(page.locator('input[name="basic.description"]')).toHaveValue(
      'Routes urgent customer issues to operators.',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/pipelines$/);
    await expect(
      page.getByText('Select a pipeline from the sidebar'),
    ).toBeVisible();
  });

  test('creates, edits, and deletes a knowledge base', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/knowledge?id=new');

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('Support Knowledge');
    await page
      .locator('input[name="description"]')
      .fill('Source material for support answers.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/knowledge\?id=knowledge-1$/);
    await page.reload();
    await expect(page.locator('input[name="name"]')).toHaveValue(
      'Support Knowledge',
    );
    await page.waitForTimeout(600);

    await page
      .locator('input[name="description"]')
      .fill('Updated source material for support answers.');
    await save(page);
    await expect(page.locator('input[name="description"]')).toHaveValue(
      'Updated source material for support answers.',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/knowledge$/);
    await expect(
      page.getByText('Select a knowledge base from the sidebar'),
    ).toBeVisible();
  });

  test('creates, edits, and deletes an MCP server', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/mcp?id=new');

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('playwright-mcp');
    await page
      .locator('input[name="url"]')
      .fill('https://mcp.example.test/sse');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/mcp\?id=playwright-mcp$/);
    await page.reload();
    await expect(page.locator('input[name="name"]')).toHaveValue(
      'playwright-mcp',
    );

    await page
      .locator('input[name="url"]')
      .fill('https://mcp.example.test/updated-sse');
    await save(page);
    await expect(page.locator('input[name="url"]')).toHaveValue(
      'https://mcp.example.test/updated-sse',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/mcp$/);
    await expect(
      page.getByText('Select an MCP server from the sidebar'),
    ).toBeVisible();
  });

  test('updates and deletes a manually-created skill', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/skills?action=create');

    await page.locator('#display_name').fill('Release Notes');
    await page.locator('#name').fill('release_notes');
    await page.locator('#description').fill('Drafts release notes.');
    await page
      .locator('#instructions')
      .fill('Summarize merged changes for the next release.');
    await save(page);

    await expect(page).toHaveURL(/\/home\/skills\?id=release_notes$/);
    await page.reload();
    await expect(page.locator('#description')).toHaveValue(
      'Drafts release notes.',
    );

    await page
      .locator('#description')
      .fill('Drafts concise release notes for maintainers.');
    await expect(page.locator('#description')).toHaveValue(
      'Drafts concise release notes for maintainers.',
    );
    await save(page);
    await page.reload();
    await expect(page.locator('#description')).toHaveValue(
      'Drafts concise release notes for maintainers.',
    );
    await expect(page.locator('#instructions')).toHaveValue(
      'Summarize merged changes for the next release.',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/add-extension$/);
  });
});
