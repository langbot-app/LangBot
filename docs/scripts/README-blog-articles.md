# LangBot Blog → Wiki article synchronization

`langbot-app/langbot-landing-page/src/content/blog` is the canonical article source. The Wiki publishes generated copies under `{en,zh,ja}/articles/` and stores every rendered image locally under `images/articles/` so Wiki pages do not depend on third-party hotlinks.

## Run locally

From the Wiki checkout, with the landing-page repository available as a sibling checkout:

```bash
node scripts/sync-blog-articles.mjs --source ../langbot-landing-page
node scripts/sync-blog-articles.mjs --check --source ../langbot-landing-page
node scripts/sync-blog-articles.mjs --check
npm test
```

The synchronizer:

- requires matching English and Chinese slug sets;
- uses the canonical Japanese article when one exists and a clearly marked English fallback otherwise;
- groups navigation into product updates, engineering, tutorials/integrations, and announcements with localized labels;
- copies source images and downloads external images into the Wiki repository;
- rewrites Markdown image URLs to Wiki-local paths;
- escapes prose that would otherwise be parsed as MDX expressions;
- replaces the generated article directories and updates the `docs.json` article tabs deterministically.

Do not edit generated article pages or mirrored images manually. Fix the canonical Blog post or the synchronizer, then regenerate.

A daily GitHub Actions workflow provides drift recovery. Article publishing work should still synchronize and verify the Wiki in the same task so a new Blog post does not wait for the scheduled run.
