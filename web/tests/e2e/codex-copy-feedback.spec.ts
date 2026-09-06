import { expect, test, type Page } from '@playwright/test';

// Isolated real React/Radix fixture. No backend or OAuth requests are made.
async function mount(page: Page, mode: string) {
  page.on('pageerror', (error) => console.error(error.message));
  await page.route('**/copy-harness', (route) =>
    route.fulfill({
      contentType: 'text/html',
      body: `
    <div id="root"></div><script type="module">
    import RefreshRuntime from '/@react-refresh';
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => (type) => type;
    window.__vite_plugin_react_preamble_installed__ = true;
    </script><script type="module">
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    const {createRoot} = ReactDOM;
    import i18n from '/node_modules/.vite/deps/i18next.js';
    import {initReactI18next} from '/node_modules/.vite/deps/react-i18next.js';
    import {Toaster} from '/src/components/ui/sonner.tsx';
    import '/src/app/global.css';
    import {Dialog, DialogContent, DialogTitle} from '/src/components/ui/dialog.tsx';
    import Section from '/src/app/home/components/models-dialog/component/provider-form/CodexAccountSection.tsx';
    await i18n.use(initReactI18next).init({lng:'en', resources:{en:{translation:{}}}, interpolation:{escapeValue:false}});
    const root=createRoot(document.getElementById('root'));
    window.renderCode=(code='FIXTURE-1234',attempt='attempt-1')=>root.render(React.createElement(Dialog,{open:true},
      React.createElement(DialogContent,{},React.createElement(DialogTitle,{},'Copy fixture'),React.createElement(Section,{providerId:'fixture',login:{phase:'pending',device:{user_code:code,authorization_id:attempt,verification_uri:'https://example.invalid',expires_at:9999999999}}})),React.createElement(Toaster)));
    window.renderCode();
    </script>`,
    }),
  );
  await page.addInitScript((mode) => {
    const w = window as any;
    w.copyEvents = [];
    document.addEventListener('copy', () => {
      const el = document.activeElement as HTMLTextAreaElement;
      w.copyEvents.push({
        tag: el.tagName,
        selected: el.value?.slice(el.selectionStart, el.selectionEnd),
      });
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value:
        mode === 'unavailable'
          ? undefined
          : {
              writeText: (text: string) => {
                if (mode === 'success') {
                  w.written = text;
                  return Promise.resolve();
                }
                if (mode === 'delayed')
                  return new Promise((resolve) => {
                    w.resolveCopy = resolve;
                  });
                return Promise.reject(new Error('denied'));
              },
            },
    });
    if (mode === 'false') document.execCommand = () => false;
    if (mode === 'throw')
      document.execCommand = () => {
        throw new Error('denied');
      };
  }, mode);
  await page.goto('/copy-harness');
  await expect(
    page.getByRole('button', { name: 'models.codex.copyCode', exact: true }),
  ).toBeVisible();
}
const copy = (page: Page) =>
  page.getByRole('button', { name: 'models.codex.copyCode', exact: true });
const copied = (page: Page) =>
  page.getByRole('button', { name: 'models.codex.copied', exact: true });

test('Clipboard API success shows icon, toast and transient feedback', async ({
  page,
}) => {
  await mount(page, 'success');
  await expect(copy(page).locator('svg.lucide-copy')).toBeVisible();
  await copy(page).click();
  await expect(copied(page).locator('svg.lucide-check')).toBeVisible();
  await expect(
    page.getByText('common.copySuccess', { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => (window as any).written)).toBe(
    'FIXTURE-1234',
  );
  await expect(copy(page)).toBeVisible({ timeout: 4000 });
});
for (const mode of ['unavailable', 'rejected'])
  test(`${mode} API performs a real selected-text copy inside modal`, async ({
    page,
  }) => {
    await mount(page, mode);
    await copy(page).click();
    await expect(copied(page)).toBeVisible();
    expect(await page.evaluate(() => (window as any).copyEvents)).toEqual([
      { tag: 'TEXTAREA', selected: 'FIXTURE-1234' },
    ]);
    await expect(copied(page)).toBeFocused();
    await expect(page.locator('textarea')).toHaveCount(0);
  });
for (const mode of ['false', 'throw'])
  test(`${mode} fallback reports failure and manual guidance`, async ({
    page,
  }) => {
    await mount(page, mode);
    await copy(page).click();
    await expect(
      page.getByText('common.copyFailed', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('models.codex.copyManually', { exact: true }),
    ).toBeVisible();
    await expect(copy(page)).toBeVisible();
    await expect(page.locator('textarea')).toHaveCount(0);
    await expect(copy(page)).toBeFocused();
  });
test('new code or attempt clears copied feedback', async ({ page }) => {
  await mount(page, 'success');
  await copy(page).click();
  await expect(copied(page)).toBeVisible();
  await page.evaluate(() =>
    (window as any).renderCode('FIXTURE-5678', 'attempt-2'),
  );
  await expect(copy(page)).toBeVisible();
  await copy(page).click();
  await expect(copied(page)).toBeVisible();
  await page.evaluate(() =>
    (window as any).renderCode('FIXTURE-5678', 'attempt-3'),
  );
  await expect(copy(page)).toBeVisible();
});
test('completion from an old attempt cannot mark the new code copied', async ({
  page,
}) => {
  await mount(page, 'delayed');
  await copy(page).click();
  await page.evaluate(() =>
    (window as any).renderCode('FIXTURE-5678', 'attempt-2'),
  );
  await expect(page.getByText('FIXTURE-5678')).toBeVisible();
  await page.evaluate(() => (window as any).resolveCopy());
  await expect(copy(page)).toBeVisible();
  await expect(copied(page)).toHaveCount(0);
});
