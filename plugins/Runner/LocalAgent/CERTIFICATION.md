# LocalAgent shared-runtime candidate

Version 0.2.1 targets `langbot-plugin>=0.7.4,<0.8` and declares
`shared-runtime-v1`. This declaration is **not a certificate**. Publication,
independent exact-package review, signing and live acceptance remain separate gates.

## State and authority review

- `LocalAgentPlugin.initialize()` retains no installation config, credentials,
  conversation cache or background task. The default Runner creates its API,
  assembler, context budget, Box binding, usage tracker and control checks per run.
- `get_run_api(ctx)` and the SDK-bound `ctx` helpers carry run resource permissions
  and the trusted RPC installation envelope. Models, tools, RAG, history, steering,
  state and Box actions use Host APIs; no provider keys or direct provider clients
  are constructed in this plugin. Configuring a resource ID does not grant it.
- Compaction checkpoints are Host-owned conversation state. Isolation of that
  state and provider credentials relies on the Host's installation/run authority,
  not globally unique user-provided conversation IDs or Box reuse keys.
- There is no plugin-owned durable filesystem state. A `{global}` Box reuse key
  means reuse within Host-authorized scope, not a process-global sandbox.
- Cancellation and deadlines terminate the local invocation. Cancelling an RPC
  waiter does **not** prove remote Host/provider work was cancelled or rolled back.
  Tests release their simulated remote model actions explicitly.

The repair aligns the dependency/admission contract and adds scoped regression
coverage. It does not claim a previously reproduced tenant-data leak, and does
not introduce unnecessary changes to the existing invocation-local algorithm.

## Verification

Run from this plugin directory with the actual 0.7.4 interpreter:

```sh
python -m pytest tests -q
```

`tests/test_shared_runtime.py` uses real SDK discovery, controller initialization,
Runner dispatch, authorization proxies and bidirectional loopback WebSocket RPC.
One actual component object handles concurrent distinct installation envelopes.
A bounded simulated Host checks every callback envelope against its run owner.
It deliberately collides model, conversation, tool and state-key identifiers:

- distinct prompt/config/reasoning, Host-selected synthetic credentials and output;
- overlapping streaming/non-streaming model/tool calls and scoped RAG;
- real plugin compaction state writes and subsequent scoped readback;
- missing model grants/operations, ungranted tools and knowledge bases;
- one installation's history/model failure, cooperative cancellation or deadline
  while the other completes, followed by healthy same-component reuse;
- Box acquisition/binding/export and both automatic and explicit file reply paths,
  plus unavailable-Box isolation.

`tests/test_shared_release.py` checks real SDK
`PluginDependencyEnvironmentStore` preparation/cache readback through the SDK's
**direct OSS installer** into a disposable directory. It does not mutate the
Runtime virtualenv or substitute an SDK stub.

Build once from this directory using the official CLI, then preserve the bytes:

```sh
python -m langbot_plugin.cli.__init__ build -o /absolute/external/candidate-directory
```

From the repository, verify the frozen package:

```sh
python Runner/certification-tests/verify_localagent_candidate.py \
  --package /absolute/external/candidate-directory/langbot-team-LocalAgent-0.2.1.lbpkg \
  --evidence /absolute/external/new-evidence-directory
```

The verifier requires committed clean plugin source, compares every archive
entry against Git (regenerating only the SDK-serialized manifest), verifies the
installed SDK distribution RECORD, installs the exact archive with
`PluginArtifactStore`, prepares/reuses its dependency environment without
shadow-installing the SDK, and runs the packaged suite from the read-only
extraction in a fresh Python process. It records hashes, commands and results.

## Limits

The Host/model/storage/credential/Box responses are fixtures, not genuine upstream
service responses. These tests are not Core database/RLS acceptance, actual
multi-Workspace installation, OS worker-supervisor/nsjail enforcement, real Box
filesystem execution, or a real provider request. They do not bypass certificate
admission. Final live execution and signing belong to the release owner.
