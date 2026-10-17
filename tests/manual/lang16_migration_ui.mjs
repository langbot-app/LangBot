// Actual migration UI against the isolated Core and synthetic HTTP 503 marketplace.
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
const require = createRequire(
  new URL("../../web/package.json", import.meta.url),
);
const { chromium } = require("@playwright/test");
const browser = await chromium.launch({
  channel: "msedge",
  headless: true,
  args: ["--renderer-process-limit=2", "--disable-gpu"],
});
const result = { errors: [] };
let page;
try {
  page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    locale: "en-US",
  });
  page.on("pageerror", (error) => result.errors.push(error.message));
  await page.addInitScript((token) => {
    localStorage.setItem("token", token);
    localStorage.setItem("langbot_language", "en-US");
    localStorage.setItem("userEmail", "qa-network@example.invalid");
  }, process.env.LANG16_UI_TOKEN);
  await page.goto("http://127.0.0.1:13000/home/pipelines", {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await page
    .getByRole("button", { name: /^(Skip|跳过|Review migration|检查迁移)$/ })
    .first()
    .waitFor({ timeout: 20000 });
  if (page.url().includes("/wizard")) {
    await page.getByRole("button", { name: /^(Skip|跳过)$/ }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: /^(OK|确定)$/ })
      .click();
    await page.waitForURL((url) => !url.pathname.includes("/wizard"));
    await page.goto("http://127.0.0.1:13000/home/pipelines", {
      waitUntil: "domcontentloaded",
    });
  }
  const tourSkip = page.locator('[data-guided-tour-action="skip"]');
  try {
    await tourSkip.waitFor({ state: "visible", timeout: 10000 });
    await tourSkip.click();
  } catch {}
  await page
    .getByRole("button", { name: /Review migration|检查迁移/ })
    .click({ timeout: 15000 });
  await page
    .getByRole("button", {
      name: /Install plugins and migrate|自动安装插件并迁移/,
    })
    .click();
  await page
    .getByText(/marketplace could not serve|插件市场暂时无法/)
    .first()
    .waitFor({ timeout: 15000 });
  await page
    .getByRole("button", { name: /Installation details|安装详情/ })
    .click();
  await page.getByText(/http_status.*HTTP 503/).waitFor({ timeout: 5000 });
  result.body = await page.locator("body").innerText();
  result.diagnosticVisible =
    result.body.includes("HTTP 503") && result.body.includes("http_status");
  await page.screenshot({ path: "migration-error.png", fullPage: true });
} catch (error) {
  result.failure = error.message;
  if (page) {
    result.url = page.url();
    result.body = await page.locator("body").innerText();
    await page.screenshot({ path: "migration-failure.png", fullPage: true });
  }
  throw error;
} finally {
  await writeFile("migration-ui.json", JSON.stringify(result, null, 2));
  await browser.close();
}
