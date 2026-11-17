# Storage white-box QA pilot

Baseline: `1f227f7aa8e3f4e3f1e5c7d5019e4d8a128d00ec`. This is a test-only change. Preserve representative behavior, not a target test count.

| Change | Retained behavior and evidence |
| --- | --- |
| Remove app-reference identity, base initialize no-op, and initial S3 client/bucket attribute assertions (four cases total) | Provider selection still checks missing, explicit local, explicit S3, and unknown configuration. Manager shutdown must await both active provider and content store; S3 shutdown must close its client once across repeated shutdown calls. |
| Combine five Moto CRUD cases into one lifecycle | Missing, write binary payload, read bytes back via an independent Moto client, load/size through the provider, and delete verified both via provider absence and independent Moto 404. Keep bounded reads, overwrite, multiple keys, prefix deletion, initialization and not-found error tests separate. |
| Require provider initialization to be awaited in all four selection cases | An in-memory variant invoking but discarding the provider initialize coroutine passed all four original call-count checks and failed all four new await checks. |
| Add subprocess regression-gate boundary cases | A process exiting 23 after recording a passing business summary must fail the gate; a process exiting 0 with a failing business summary must also fail. Both must preserve an inspectable verdict and must not report a timeout. Two separate in-memory variants (ignore child exit, accept a present but false summary verdict) survived all original gate tests and each failed the new case. |

Local Linux, Python 3.12.14, locked dependencies:

```sh
uv run --no-sync pytest -q tests/unit_tests/storage
uv run --no-sync python -m unittest discover -s tools/tests -p 'test_*.py'
```

Full Storage: **188 passed before, 180 passed after**, no failed or skipped cases. Count reduction is not a demonstrated speedup. The unchanged eight-variant in-memory panel was run in independent pytest processes against the same three test files (manager, provider selection and S3). It replaced only one behavior per process: missing configuration raises, explicit S3 selects local, manager omits provider shutdown, S3 omits client close, PUT drops bytes, GET returns empty bytes, size reports zero, or delete is a no-op. Test assertions detected all eight both before and after; no new survivor in this panel. Product files were not mutated on disk. The added missing-await variant is separate from those eight.

This verifies only the named boundaries and synthetic variants. Moto is a local S3 simulator; this did not run a real MinIO/AWS service or broaden branch-protection/CI gates.
