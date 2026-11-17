# #2804 post-install follow-up — screenshot evidence

Captured against a real Vite dev server with Playwright, API mocked (no backend).
`before` is `master@09ef402a`; `after` is the tip of this branch.

| shot | what it proves |
| --- | --- |
| `compare-multi.png` | A plugin with Runner + Tool + Command + KnowledgeEngine shows one row per distinct step, and the pipeline step exactly once — the "no duplicate of the same kind" criterion. The rows sit under one divider inside the banner instead of each carrying its own border; the whole row is the hit target and opens the create form directly (`?id=new`). Before: nothing. |
| `compare-parser.png` | A Parser-only plugin adds no follow-up; the banner stays one line in both. |
| `compare-review.png` | With a permission review pending, the banner turns amber with a shield (it is an action, not a success) and its one row is Review; no follow-up competes with it. |
| `compare-multi-zh-Hans.png` / `compare-multi-zh-Hant.png` | The Chinese renderings. Copy is native, not translated English, and the traditional locale uses the same word for a plugin as the rest of its file. |
| `full-review-list.png` | The pending-review list section outside the dialog. Same amber, same header-plus-divided-rows shape as the dialog banner; its Review button gains the shield and trailing arrow the dialog row has. Both call sites share the short text and the full label. |
| `compare-review-zh-Hans.png` / `compare-review-zh-Hant.png` | Pending review renders as the same row as a follow-up step (icon, text, arrow under the banner's divider), in amber instead of green. The visible text shortens to Review / 审阅 / 審閱 with the full phrase in `aria-label`; the pending banner drops 外掛 for 插件. |
| `full-narrow-focus-zh-Hans.png` | At 390 px wide the rows stay full width; Tab reaches the first row with a visible focus ring and Enter opens the create form. |

Reproduce:

```sh
cd web
pnpm exec playwright test --config playwright.followup-shots.config.ts
```

The spec asserts the rendered links, so these images cannot drift from the
component without the test failing. On `master` the multi-component case fails
(no links) while the other two pass — that pair is the regression proof.

## i18n

All eight locales carry the keys (`node web/scripts/check-i18n.mjs` passes). Copy
is written per language rather than mirroring the English sentence:

- the English source repeated "for this plugin" on all three lines, then a
  "Next:" prefix on each; the prefix is now one `nextSteps` heading and every
  line is just verb + noun, so the five locales that had a colon lose it too;
- `zh-Hant` mixed 外掛 with 插件 in the same block (`installComplete` said 外掛
  while `updateComplete` next to it said 插件); both now say 插件, matching the
  rest of that file;
- `ja-JP` uses the full-width colon its other copy uses.

Both Chinese cases are asserted by the spec, not eyeballed: they check the exact
link text and that the pipeline step stays a single link.
