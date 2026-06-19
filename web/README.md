# Debug LangBot Frontend

Please refer to the [Development Guide](https://link.langbot.app/en/docs/dev-config) for more information.

## Tests

Run the frontend smoke tests without a backend process:

```bash
pnpm test:e2e
```

The Playwright suite starts Vite and mocks the LangBot backend and Space APIs.
