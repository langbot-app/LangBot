import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
test("share metadata references the branded versioned preview", () => {
  for (const file of ['docs.json']) {
    assert.ok(readFileSync(path.join(root, file), "utf8").includes('/images/social/docs-v3.png'), file);
  }
});
test("sharing PNG is a small 1200 by 630 image", () => {
  const file = path.join(root, 'images/social/docs-v3.png');
  assert.ok(existsSync(file), "branded image is present");
  const png = readFileSync(file);
  assert.equal(png.subarray(1, 4).toString(), "PNG");
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
  assert.ok(png.length < 200_000);
});
