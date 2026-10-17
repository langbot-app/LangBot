// Real local UI navigation, without touching an existing browser profile.
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
const require = createRequire(
  new URL("../../web/package.json", import.meta.url),
);
const { chromium } = require("@playwright/test");
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://127.0.0.1:13000/login", {
    waitUntil: "networkidle",
    timeout: 20000,
  });
  await page.screenshot({ path: "login.png", fullPage: true });
  const login = await page.locator("body").innerText();
  await page.goto("http://127.0.0.1:13000/register", {
    waitUntil: "networkidle",
    timeout: 20000,
  });
  await page.screenshot({ path: "register.png", fullPage: true });
  await writeFile(
    "ui.json",
    JSON.stringify(
      { login, register: await page.locator("body").innerText(), errors },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
