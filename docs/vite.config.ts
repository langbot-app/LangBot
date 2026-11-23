import tailwindcss from "@tailwindcss/vite";
import press from "fumapress/vite";
import { fumadocsMdx } from "fumadocs-mdx/vite";
import { defineConfig, type Plugin } from "vite";

/**
 * Mirror the base-path prefixing that the production build applies.
 *
 * `npm run build` finishes with `scripts/finalize-base-path.mjs`, which rewrites
 * root-absolute asset URLs in the generated output so they resolve under the
 * docs mount point inside langbot-landing-page (https://langbot.app/docs/...).
 *
 * The dev server serves the same content under `basePath: "/docs/"` but never
 * runs that step, so those URLs 404 locally. Only assets that survive as literal
 * root-absolute strings are affected: icons referenced from `docs.json` and the
 * brand logo in `press.config.tsx`. Markdown images are unaffected because the
 * asset pipeline rewrites them itself.
 *
 * The rule set intentionally mirrors `scripts/finalize-base-path.mjs` exactly, so
 * a URL that is broken locally is broken in production too, and vice versa.
 */
const prefixBasePathAssets = (): Plugin => ({
  name: "docs-dev-base-path-assets",
  apply: "serve",
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      const url = req.url ?? "";
      const isUnprefixedAsset =
        url.startsWith("/images/") ||
        url.startsWith("/favicon.ico") ||
        url.startsWith("/langbot-logo.png") ||
        url.startsWith("/rss.xml");
      if (isUnprefixedAsset) req.url = `/docs${url}`;
      next();
    });
  },
});

export default defineConfig({
  plugins: [
    prefixBasePathAssets(),
    press({ basePath: "/docs/" }),
    fumadocsMdx(),
    tailwindcss(),
  ],
});
