import { expect, test } from '@playwright/test';

test.skip(
  !process.env.LANGBOT_RUNNER_PIPELINE_ID,
  'Requires the isolated real backend and SDK pytest fixture',
);

test('real backend and SDK: save, copy and execute with extensions off', async ({
  page,
  request,
}) => {
  const api = process.env.LANGBOT_RUNNER_API_URL!;
  const pipelineId = process.env.LANGBOT_RUNNER_PIPELINE_ID!;
  const token = process.env.LANGBOT_RUNNER_TOKEN!;
  const runnerId = 'plugin:e2e/agent-runner-qa/default';
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(
    ({ token }) => {
      localStorage.setItem('token', token);
      localStorage.setItem('userEmail', 'admin@langbot.test');
      localStorage.setItem('langbot_language', 'en-US');
      for (const key of [
        'langbot_sidebar_guide_v1',
        'langbot_pipeline_setup_guide_v1',
      ]) {
        localStorage.setItem(key, 'completed');
      }
    },
    { token },
  );
  await page.goto(`/home/pipelines?id=${pipelineId}`, {
    waitUntil: 'domcontentloaded',
  });
  await page.getByRole('button', { name: 'Skip', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'OK', exact: true })
    .click();
  await expect(
    page.getByRole('dialog', { name: 'Skip', exact: true }),
  ).not.toBeVisible();
  await page.goto(`/home/pipelines?id=${pipelineId}`, {
    waitUntil: 'domcontentloaded',
  });
  await page.locator('[data-guide="pipeline-section-ai"]').click();
  await expect(
    page.getByRole('combobox', { name: 'Runner', exact: true }),
  ).toContainText('QA Echo Runner');
  const prefixInput = page
    .getByRole('region', { name: 'Configuration', exact: true })
    .getByRole('textbox');
  await prefixInput.fill('browser saved');
  const savedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/pipelines/${pipelineId}`) &&
      response.request().method() === 'PUT',
  );
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  expect((await (await savedResponse).json()).code).toBe(0);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('[data-guide="pipeline-section-ai"]').click();
  await expect(prefixInput).toHaveValue('browser saved');
  await page.getByRole('button', { name: 'Management', exact: true }).click();
  await page.getByRole('button', { name: 'Copy', exact: true }).click();
  const copiedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/pipelines/${pipelineId}/copy`) &&
      response.request().method() === 'POST',
  );
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  const copiedPayload = await (await copiedResponse).json();
  expect(copiedPayload.code).toBe(0);
  const copiedId = copiedPayload.data.uuid;
  for (const id of [pipelineId, copiedId]) {
    const response = await request.get(`${api}/api/v1/pipelines/${id}`, {
      headers,
    });
    expect(response.ok()).toBeTruthy();
    const stored = (await response.json()).data.pipeline;
    expect(stored.config.ai.runner.id).toBe(runnerId);
    expect(stored.config.ai.runner_config[runnerId]).toEqual({
      prefix: 'browser saved',
      hidden: { keep: [null, false, '  raw  '] },
    });
    expect(stored.extensions_preferences.enable_all_plugins).toBe(false);
    expect(stored.extensions_preferences.plugins).toEqual([]);
    await page.goto(`/home/pipelines?id=${id}`, {
      waitUntil: 'domcontentloaded',
    });
    const input = page.getByPlaceholder('Send Private Chat message...');
    await expect(input).toBeEnabled();
    await input.fill(`Chromium ${id}`);
    await input.press('Enter');
    await expect(
      page.getByText(`browser saved: Chromium ${id}`, { exact: true }),
    ).toBeVisible({ timeout: 20_000 });
  }
});
