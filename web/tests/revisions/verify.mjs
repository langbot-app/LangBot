import { createServer } from 'vite';
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';
const workdir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../..',
);
const evidence = path.join(workdir, 'evidence');
await mkdir(evidence, { recursive: true });
const servers = [];
let browser;
const results = [];
const latest = (mode) => ({
  uuid: 'latest',
  name: 'pro',
  revision: mode === 'same' ? 1 : 2,
  display_name: { en_US: 'Pro' },
  description: { en_US: 'Workspace plan' },
  price_cny: '70',
  price_usd: '10',
  price_jpy: '1500',
  features: [],
  limits:
    mode === 'equal' || mode === 'same'
      ? { 'bots.max': 2, 'members.max': 3 }
      : { 'bots.max': 8, 'members.max': 5 },
  entitlement_features: { mcp_stdio: !['same', 'equal'].includes(mode) },
  disabled_adapters: ['same', 'equal'].includes(mode) ? ['telegram'] : [],
  chat_history_retention_days: ['same', 'equal'].includes(mode) ? 30 : 90,
  monthly_bonus_credits: ['same', 'equal'].includes(mode) ? 10 : 20,
  is_active: true,
  subscription_disabled: mode === 'paused',
  sort_order: 1,
  highlight: false,
});
try {
  for (const [repo] of [
    ['space', 4185],
    ['core', 4186],
  ]) {
    const server = await createServer({
      configFile: path.join(
        workdir,
        repo,
        'web/tests/revisions/vite.config.mjs',
      ),
    });
    await server.listen();
    servers.push(server);
  }
  browser = await chromium.launch({ headless: true });
  for (const repo of ['space', 'core']) {
    const modes =
      repo === 'space'
        ? [
            'changed',
            'same',
            'equal',
            'paused',
            'removed',
            'member',
            'stripe',
            'cancel-failure',
          ]
        : [
            'changed',
            'same',
            'equal',
            'paused',
            'removed',
            'member',
            'unknown',
            'error',
          ];
    for (const mode of modes) {
      const page = await browser.newPage({
        viewport: { width: 1360, height: 1100 },
      });
      page.setDefaultTimeout(120000);
      const errors = [];
      page.on('pageerror', (error) => {
        errors.push(error.message);
        console.error(error.message);
      });
      await page.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.hostname === '127.0.0.1') return route.continue();
        if (url.pathname === '/api/v1/cloud/v2/plans')
          return route.fulfill({
            status: mode === 'error' ? 500 : 200,
            contentType: 'application/json',
            body: JSON.stringify({
              code: 0,
              data: mode === 'removed' ? [] : [latest(mode)],
            }),
          });
        return route.abort();
      });
      const port = repo === 'space' ? 4185 : 4186;
      await page.goto(
        `http://127.0.0.1:${port}/tests/revisions/index.html?mode=${mode}${mode === 'stripe' ? '&intent=1' : ''}`,
        { waitUntil: 'domcontentloaded', timeout: 120000 },
      );
      if (repo === 'core' && mode === 'error')
        await page.getByRole('alert').waitFor();
      else if (mode === 'unknown')
        await page
          .getByText(/Current subscription details are unavailable/)
          .waitFor();
      else
        await page
          .locator(
            repo === 'space'
              ? '[data-plan-comparison]'
              : '[data-cloud-plans] article',
          )
          .first()
          .waitFor();
      if (errors.length)
        throw new Error(`${repo}/${mode}: ${errors.join(';')}`);
      if (await page.locator('[data-revision-comparison]').count())
        throw new Error('Standalone comparison remains');
      if (
        ['same', 'equal'].includes(mode) &&
        (await page.locator('[data-owned-plan]').count())
      )
        throw new Error('Identical benefits duplicated');
      const area = page.locator(
        repo === 'space' ? '[data-plan-comparison]' : '[data-cloud-plans]',
      );
      if (!['unknown', 'error'].includes(mode)) {
        const copy = await area.innerText();
        if (
          /&#|revision|mcp stdio|workspace multi user|platform telegram/.test(
            copy,
          )
        )
          throw new Error('Internal metadata leaked into plan presentation');
        if (
          repo === 'core' &&
          (await area.locator('[data-changed], .bg-amber-500\\/10').count())
        )
          throw new Error('Diff highlighting remains');
        if (
          ['same', 'equal'].includes(mode) &&
          /Subscribed on|Latest quotas for this plan/.test(copy)
        )
          throw new Error('Unnecessary comparison labels');
      }
      if (mode === 'changed') {
        await area.getByText(/Subscribed on/).waitFor();
        await area
          .getByText('Latest quotas for this plan', { exact: true })
          .waitFor();
        const owned = page.locator('[data-owned-plan]');
        if ((await owned.count()) !== 1)
          throw new Error('Missing integrated owned version');
        const horizontal = await owned.evaluate((el) => {
          const next = el.nextElementSibling;
          return (
            !!next &&
            Math.abs(
              next.getBoundingClientRect().y - el.getBoundingClientRect().y,
            ) < 5 &&
            next.getBoundingClientRect().x > el.getBoundingClientRect().x
          );
        });
        if (!horizontal)
          throw new Error('Owned and latest are not adjacent horizontally');
      }
      if (repo === 'space' && mode === 'stripe') {
        if (await page.getByRole('dialog').count())
          throw new Error('Deep link bypassed renewal gate');
        await page
          .getByRole('button', { name: 'Manage subscription' })
          .first()
          .click();
        await page.getByText('Server refresh confirmed cancellation').waitFor();
        if (!(await page.getByRole('dialog').count()))
          await page
            .getByRole('button', { name: /Upgrade to|Subscribe to|Choose/ })
            .last()
            .click();
        await page.getByRole('dialog').waitFor();
      }
      if (repo === 'space' && mode === 'cancel-failure') {
        await page
          .getByRole('button', { name: 'Manage subscription' })
          .first()
          .click();
        await page.getByText('Cancellation failed').waitFor();
        if (await page.getByRole('dialog').count())
          throw new Error('Failed cancellation opened checkout');
      }
      if (
        mode === 'member' &&
        repo === 'core' &&
        (await page.getByRole('link').count())
      )
        throw new Error('Member purchase link');
      if (
        mode === 'changed' ||
        mode === 'equal' ||
        mode === 'member' ||
        mode === 'paused'
      )
        await page.screenshot({
          path: path.join(evidence, `${repo}-${mode}.png`),
          fullPage: true,
        });
      results.push(`${repo}/${mode}: PASS`);
      console.log(results.at(-1));
      await page.close();
    }
  }
} finally {
  await writeFile(
    path.join(evidence, 'browser-results.txt'),
    results.join('\n') + '\n',
  );
  if (browser) await browser.close();
  for (const server of servers) await server.close();
}
