import assert from "node:assert/strict";
import test from "node:test";
import { detectLocale, preferredLocale, saveLocale, enterDocs, localeDestination, STORAGE_KEY } from "../src/locale-preference.mjs";

export function browser(saved, languages = ["ja-JP"], pathname = "/docs/") {
  const values = new Map(saved === undefined ? [] : [[STORAGE_KEY, saved]]);
  return { values, navigator: { languages }, localStorage: {
    getItem: (key) => values.get(key), setItem: (key, value) => values.set(key, value),
  }, location: { pathname, search: "?next=https://evil.example/&q=中文", hash: "#part", replace(value) { this.destination = value; } } };
}
test("saved locale wins; regional browser languages negotiate in order", () => {
  for (const [saved, languages, expected] of [
    ["en", ["zh-TW"], "en"], [null, ["fr", "zh-TW", "ja-JP"], "zh"],
    [null, ["ja-JP", "en-US"], "ja"], ["invalid", ["de"], "en"],
    ["//evil.example", ["ZH-Hant-TW"], "zh"], [null, [], "en"],
  ]) assert.equal(detectLocale(saved, languages), expected);
});
test("entry preserves query/hash with a fixed local destination", () => {
  for (const path of ["/docs", "/docs/"]) {
    const b = browser(undefined, ["zh-TW"], path); enterDocs(b);
    assert.equal(b.location.destination, `/docs/zh/insight/guide${b.location.search}${b.location.hash}`);
    assert.equal(b.values.get(STORAGE_KEY), "zh");
  }
});
test("explicit links never redirect or overwrite a preference", () => {
  const b = browser("ja", ["en"], "/docs/zh/usage/platforms/discord");
  enterDocs(b); preferredLocale(b);
  assert.equal(b.location.destination, undefined); assert.equal(b.values.get(STORAGE_KEY), "ja");
  const first = browser(undefined, ["en"], b.location.pathname);
  preferredLocale(first); assert.equal(first.values.get(STORAGE_KEY), "en");
});
test("manual selection persists; invalid and blocked storage remain safe", () => {
  const b = browser("invalid"); assert.equal(preferredLocale(b), "ja");
  saveLocale("zh", b); enterDocs(b); assert.match(b.location.destination, /^\/docs\/zh\//);
  saveLocale("evil", b); assert.equal(b.values.get(STORAGE_KEY), "zh");
  Object.defineProperty(b, "localStorage", { get() { throw new Error("blocked"); } });
  assert.doesNotThrow(() => { enterDocs(b); saveLocale("en", b); });
  assert.match(b.location.destination, /^\/docs\/ja\//);
});
test("language changes use translated API alternates and safe missing-locale fallback", () => {
  const links = [{language: "zh-CN", href: "https://langbot.app/docs/zh/api-reference/系统/获取系统信息"}];
  assert.equal(localeDestination("zh", links, "http://localhost"), "/docs/zh/api-reference/%E7%B3%BB%E7%BB%9F/%E8%8E%B7%E5%8F%96%E7%B3%BB%E7%BB%9F%E4%BF%A1%E6%81%AF");
  assert.equal(localeDestination("en", links, "http://localhost"), "/docs/en/insight/guide");
  for (const href of ["https://evil.example/docs/en/attack", "/docs/zh/attack", "javascript:alert(1)"])
    assert.equal(localeDestination("en", [{language: "en", href}], "https://langbot.app"), "/docs/en/insight/guide");
});
