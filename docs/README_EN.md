# [LangBot](https://github.com/langbot-app/LangBot) Official Documentation

> This repository is the documentation repository for LangBot. Code repository:  
> [LangBot Code Repository](https://github.com/langbot-app/LangBot)  
> This is the documentation for LangBot 4.0. For 3.0 documentation, please see the `v3` branch

## Contributing to Documentation

The documentation is built with [Fumapress](https://press.fumadocs.dev/) and [Fumadocs](https://fumadocs.dev/). Local development requires Node.js 24 or later.

Clone this repository and execute the following command in the directory to install dependencies:

```bash
npm ci
```

After completion, you can modify the documentation. After modifications, use the following command to start locally:

```bash
npm run dev
```

### Using Images

Place images in the `images` directory, then reference them using the absolute path (relative to the project root), such as:

```markdown
![image](/images/xxx.png)
```

### Deployment Details

The documentation is built as a static site in `dist/public` and hosted on Cloudflare Pages. Type checking, documentation contract tests, and a full static build run before deployment.

### Agent-readable exports

`npm run build` generates agent text after finalizing the `/docs` base path and
sitemaps. Every published page has a canonical `.md` companion, advertised by an
HTML `rel="alternate" type="text/markdown"` link without changing the visible UI.

- `/docs/llms.txt` and `/docs/llms-full.txt`: all-language index and complete text.
- `/docs/{en,zh,ja}/llms.txt` and `llms-full.txt`: language-specific exports.
- `llm.txt` is an identical compatibility alias for each `llms.txt` index.
- `/docs/openapi/service-api-{en,zh,ja}.json`: complete API specifications.

The generator reads canonical MDX with a Markdown AST (not compiled image
variables), preserves callout titles and literal image URLs, and exports every
API operation with its request/response contract, security and transitive schema
references. Unknown semantic JSX or executable expressions fail the build rather
than silently losing content. Generated files stay in `dist/public`; edit source
MDX/OpenAPI, not generated Markdown. `npm test` covers conversion, and
`npm run test:static` verifies sitemap coverage, discovery, links and API contracts
after a build. Run `npm run generate:agent-docs` to regenerate text in an existing
finalized build.

### Some Standardization Guidelines

- Folder and file naming: **Use all lowercase, separate words with `-`, such as** `plugin-intro.mdx`
- Sub-file (folder) naming: **No prefix** (i.e., the folder name), such as: in the `deploy` folder, the folder `langbot`, the `manual` file in the `langbot` folder is called `manual.mdx`
- Documentation files should use `.mdx`; the build adapter converts existing Mintlify-compatible components into Fumadocs-renderable markup.
- Configure sidebar navigation structure in `docs.json`.

---

**[中文版 README](README.md)**
