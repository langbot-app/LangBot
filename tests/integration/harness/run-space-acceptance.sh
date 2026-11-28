#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
: "${HARNESS_TS_RPC_TRANSPORT:?Build the Harness TS RPC transport first}"
: "${HARNESS_PLAYWRIGHT:?Set the path to playwright-core/index.mjs}"
: "${HARNESS_BROWSER_BUNDLE:?Bundle the Harness RPC and WSS transports first}"
export PYTHONPATH="$PWD/src:$PWD/sdk/src${PYTHONPATH:+:$PYTHONPATH}"
"${HARNESS_PYTHON:-python}" -m pytest -q tests/integration/harness/test_http_rpc.py -k space
