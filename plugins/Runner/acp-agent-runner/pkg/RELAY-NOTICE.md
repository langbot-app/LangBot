# Plugin-owned coding relay v1

`daemon_relay.py` is derived from langbot-plugin 0.6.0b5
`langbot_plugin/api/agent_tools/daemon.py`, upstream
https://github.com/langbot-app/langbot-plugin-sdk (Apache-2.0).
Original SHA-256: `140d1448666a1412777cd3e51a03ae2ce2ba48b3593b89484b581a1e202d7ad0`.
Full upstream license: `LICENSE-sdk.txt`.

Modified by LangBot plugin contributors: negotiated coding-relay-v1, socket
ownership, serialized listener startup, shared token policy, cancellation
acknowledgement/fencing, disconnect cleanup. No installed SDK is patched.
Canonical source is ACP's pkg/daemon_relay.py; the other two copies must be
byte-identical (enforced by certification-tests/test_coding_relay_v1.py).
