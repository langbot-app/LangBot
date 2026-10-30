# Deterministic model faults

Run the test backend with Python 3.11 or newer:

```sh
python tools/mock_llm.py --port 18080 --record /tmp/mock-requests.jsonl
```

Point the LangBot OpenAI-compatible provider at `http://127.0.0.1:18080/v1`
and choose a model below. The default `mock-chat`, `mock-embedding`, tool and
smoke models retain their existing behavior. `GET /v1/models` lists all models.

| Model | Injected behavior |
| --- | --- |
| `mock-stream-disconnect` | Send two SSE chunks, then close an incomplete HTTP chunked response. Requires streaming. |
| `mock-stream-stall` | Pause for two seconds after the second SSE chunk, then finish. Requires streaming. |
| `mock-recover-503` | Return 503 on the first request in a scope, then `LANGBOT_RECOVERY_OK`. |
| `mock-recover-stream-disconnect` | Disconnect the first stream in a scope; later streams finish with `LANGBOT_STREAM_RECOVERY_OK`. |
| `mock-embedding-429`, `mock-embedding-503` | Return the named HTTP error. |
| `mock-embedding-timeout` | Wait two seconds before responding. Set the client timeout below two seconds to observe a timeout. |
| `mock-embedding-wrong-count` | Omit the final input's vector, including an empty result for one input. |
| `mock-embedding-wrong-dimension` | Return one fewer dimension, or two dimensions when one was requested. Supports float and base64 encoding. |
| `mock-embedding-recover-503` | Return 503 on the first embedding request in a scope, then normal vectors. |

The daily tool recovery models validate returned tool results before advancing.
`mock-daily-empty-rag-chat` rejects either configured knowledge sentinel anywhere
in the model messages. Token-hash embeddings exercise protocol and retrieval
plumbing; they do not evaluate semantic model quality.

## Isolate recovery attempts

Assign each run/case/conversation a unique scope, such as `run17.rag.group3`.
Set this in the LangBot model's advanced parameters:

```json
{"extra_body": {"mock_scope": "run17.rag.group3"}}
```

The Core LiteLLM requester forwards this as top-level `mock_scope` in both chat
and embedding requests. A model-level value is shared by every conversation
using that model: use a separate model configuration per scope or use a marker
`LB_MOCK_SCOPE=run17.rag.group3` in the current user message. Markers in older
chat history are ignored. Embedding input strings also support markers, but
they change the hashed vectors; prefer `extra_body` for embedding tests.
An explicit `mock_scope` overrides markers. IDs accept 1–128 ASCII letters,
digits and `_.:-`. Scopes are test correlation IDs, not tenant authorization.

To exercise the same contract directly, run this request twice; the first
returns 503 and the second returns the recovery message:

```sh
curl -i http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mock-recover-503","mock_scope":"run17.direct","messages":[{"role":"user","content":"hello"}]}'
```

Counters are isolated by endpoint, model name and scope. Each validated request,
including an SDK retry, consumes an attempt; tool steps still follow the actual
tool history. SDK retries can consume the failure and recovery within one
product call: the current Core embedding path retries a 503 even when model
advanced parameters set `max_retries: 0` and `num_retries: 0`. Use the permanent
error models to assert a visible error, and inspect recorded attempts for
recovery scenarios. A request rejected by prompt/tool/input validation does not
consume an attempt.

After draining a scenario's requests, release all its counters:

```sh
curl -X DELETE http://127.0.0.1:18080/_mock/scopes/run17.rag.group3
```

The response reports the number released. Reusing a released scope restarts its
fault sequence. Idle counters expire after one hour; at 2,048 retained counters,
new scopes receive 400 until counters are released or expire. Existing scopes
continue working. The backend is unauthenticated and defaults to loopback;
use it only in the test environment.

## Configure and verify a fault

Custom `--scenarios` JSON can set `status`, `delay_seconds`,
`chunk_delay_seconds`, `disconnect_after_chunks`, or the pair
`stall_after_chunks` / `stall_seconds`. Delays are bounded to 0–60 seconds;
the first role chunk counts toward stream positions. Add `recover_after: N`
to apply the controls only to the first N requests per scope (1–100).
Embedding scenarios use `kind: "embedding"` and optionally
`embedding_fault: "count"` or `"dimension"`.

Each completed handler appends the request, scope, attempt (for recovery), HTTP
status, actual `faults`, and `response_complete` to the JSONL record. Delays
include measured elapsed time. A deliberate stream cut records its chunk count
and `injected_disconnect`; socket errors caused by the client record
`disconnected`. `response` contains the planned chat message or embedding
payload; `response_complete` reports whether the server finished writing it,
not whether the client received it. Check the client result too. A configured
stream position that was never reached produces no injection event and cannot
count as a successful fault test. Records contain request bodies; use test data.

Run the HTTP tests without installing LangBot dependencies:

```sh
python -m unittest discover -s tools -p test_mock_llm.py -v
```
