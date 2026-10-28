# Coding Runner shared-worker candidates

Only ACPAgentRunner, ClaudeCodeAgent and CodexAgent are covered here. The revised
b5 topology is one nsjail process per installation, private home/tmp/data,
read-only code, sanitized environment, shared network. Native worker children
use worker policy, not Box quotas. The historical RED reproducer is retained as
`historical_coding_runner_shared_blockers.py`, excluded from ordinary discovery;
its five overgeneralized assertions are not counted as passing tests.

## Repeatable checks

Use the genuine b5 interpreter, not an SDK-stub test process:

```
$PYTHON -m pytest Runner/certification-tests/test_coding_relay_v1.py Runner/certification-tests/test_coding_native_lifecycle.py -q
$PYTHON Runner/certification-tests/verify_coding_candidates.py --evidence /absolute/fresh/outside-repo
CODING_RUNNER_SOURCE_ROOT=/absolute/fresh/outside-repo/extracted $PYTHON -m pytest Runner/certification-tests/test_coding_relay_v1.py Runner/certification-tests/test_coding_native_lifecycle.py -q
```

The build script requires a clean committed tree, builds with official b5 `lbp`
from an external Git-archived staging directory, records archive/member hashes,
verifies installed SDK RECORD, prepares real dependencies, checks cache and no
shadow SDK, then exercises discovery and real SDK WebSocket RPC on each exact
extraction. CLI/model replies in RPC probes are labeled local protocol fixtures,
not vendor calls. Frozen archives remain unsigned.

The process-isolation test launches **two actual separate Python workers** with
private temporary HOME/TMP/data roots and empty inherited environment, sharing
TCP loopback. It proves listener/token separation, same display/conversation ID
handling and independent cancellation. It does **not** implement or certify
nsjail mounts, cgroups, kernel escape resistance, production admission, or live
Workspace isolation. Actual b5 nsjail topology is independently recorded in the
authoritative topology-reassessment.md/.json evidence.

Same-installation tests separately use one Runner with two Agent configurations,
one plugin-config listener and different daemon IDs. Native tests execute real
Python child/process groups through all three bundled clients; vendor binaries,
credentials, external SSH sessions, live provider replies and two-Workspace
acceptance remain release/operator gates. Existing approval/steering/MCP and
multimodal/continuation protocol suites must also stay green.

`pkg/daemon_relay.py` and `pkg/runtime_support.py` are canonical in ACP and copied
byte-for-byte into the other two packages. Update/test/sync all three, including
the matching user daemon. The relay's upstream Apache license and original hash
are recorded in `pkg/RELAY-NOTICE.md` and `pkg/LICENSE-sdk.txt`.

No Core/installed-SDK modification, publication, certificate, signature, or force
installation is part of this candidate work. Independent exact-digest review and
ordinary signing are still required before any shared-runtime release claim.
