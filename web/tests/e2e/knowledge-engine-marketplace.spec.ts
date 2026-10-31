import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const reload of [false, true]) {
  test(`knowledge engine installation keeps fields and requires explicit selection${reload ? ' after reload' : ''}`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    let finished = false,
      installs = 0;
    const searches: Record<string, unknown>[] = [];
    const engine = {
      plugin_id: 'qa/engine',
      name: { en_US: 'Installed QA Engine' },
      description: { en_US: 'Registered knowledge engine description' },
      creation_schema: [],
      retrieval_schema: [],
      capabilities: [],
    };
    await page.route('**/api/v1/knowledge/engines', (route) =>
      route.fulfill({
        json: { code: 0, data: { engines: finished ? [engine] : [] } },
      }),
    );
    await page.route('**/api/v1/marketplace/**/search', async (route) => {
      searches.push(route.request().postDataJSON());
      const plugin = (name: string, label: string) => ({
        author: 'qa',
        name,
        label: { en_US: label },
        description: { en_US: `${label} description` },
        latest_version: '2.0.0',
        type: 'plugin',
        components: { KnowledgeEngine: 1 },
        install_count: 10,
      });
      await route.fulfill({
        json: {
          code: 0,
          data: {
            total: 2,
            extensions: [
              plugin('engine', 'QA Engine'),
              plugin('long-engine', 'A much longer engine display label'),
            ],
          },
        },
      });
    });
    await page.route('**/api/v1/plugins/install/marketplace', async (route) => {
      installs++;
      expect(route.request().postDataJSON()).toEqual({
        plugin_author: 'qa',
        plugin_name: 'engine',
        plugin_version: '2.0.0',
      });
      await route.fulfill({ json: { code: 0, data: { task_id: 42 } } });
    });
    await page.route('**/api/v1/system/tasks/42', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            id: 42,
            name: 'plugin-install-marketplace',
            runtime: { done: finished, exception: null },
            task_context: {
              current_action: 'Downloading',
              metadata: { progress_percent: 20 },
            },
          },
        },
      }),
    );
    await page.goto('/home/knowledge?id=new');
    await page.locator('input[name="name"]').fill('Engine choice test');
    await expect(page.locator('input[name="description"]')).toBeVisible();
    const selector = page.getByRole('combobox', {
      name: 'Knowledge Engine',
      exact: true,
    });
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(
      page.getByText('Knowledge engine is required', { exact: true }),
    ).toBeVisible();
    await selector.click();
    const first = page.getByRole('button', {
      name: 'Install QA Engine',
      exact: true,
    });
    const second = page.getByRole('button', {
      name: 'Install A much longer engine display label',
      exact: true,
    });
    await expect(first).toBeVisible();
    const positions = await Promise.all([
      first.boundingBox(),
      second.boundingBox(),
    ]);
    expect(positions.every(Boolean)).toBe(true);
    expect(Math.abs(positions[0]!.x - positions[1]!.x)).toBeLessThanOrEqual(1);
    expect(
      Math.abs(positions[0]!.width - positions[1]!.width),
    ).toBeLessThanOrEqual(1);
    await first.click();
    await expect(first).toContainText('%');
    await expect(second).toBeDisabled();
    if (reload) {
      await expect.poll(() => installs).toBe(1);
      await page.reload();
      await expect(page.locator('input[name="name"]')).toBeVisible();
      await page.locator('input[name="name"]').fill('Recovered engine choice');
      await expect(selector).toHaveText('Select Knowledge Engine');
    }
    finished = true;
    await expect(
      page.getByText('QA Engine is installed and ready to select', {
        exact: true,
      }),
    ).toBeVisible({ timeout: 15000 });
    await page.keyboard.press('Escape');
    await expect(selector).toHaveText('Select Knowledge Engine');
    if (reload)
      await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(
      page.getByText('Knowledge engine is required', { exact: true }),
    ).toBeVisible();
    await selector.click();
    const option = page.getByRole('option', { name: /Installed QA Engine/ });
    await expect(
      option.getByText('Registered knowledge engine description'),
    ).toBeVisible();
    await option.click();
    await expect(selector).toHaveText('Installed QA Engine');
    await expect(
      page.getByText('Knowledge engine is required', { exact: true }),
    ).toHaveCount(0);
    const selectedBox = await selector.boundingBox();
    expect(selectedBox!.height).toBeLessThanOrEqual(40);
    expect(installs).toBe(1);
    expect(searches.length).toBeGreaterThan(0);
    for (const request of searches)
      expect(request).toMatchObject({
        component_filter: 'KnowledgeEngine',
        type_filter: 'plugin',
      });
  });
}
