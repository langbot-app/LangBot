# Runner tutorial verification

With the local SDK installed, run:

```bash
python scripts/verify-runner-tutorial.py
python scripts/verify-plugin-api-examples.py
npm test
npm run build
```

The tutorial checker extracts the published Chinese, English and Japanese examples, checks that their code and manifests match, and executes event handlers including disabled replies, empty input, private/group messages and delivery failure. Platform actions use Mock; these tests do not prove external message delivery.

The official `langbot-plugin-demo/RunnerDemo` plugin adds multi-step actions, configuration isolation and progress/error examples. Its `scripts/smoke.py` installs a built package and runs the scenarios against a local Host. Use the same SDK and Core revision when testing.
