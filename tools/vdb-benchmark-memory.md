# Measuring Core and plugin memory during local uploads and RAG ingestion

Use the same disposable local Core/Runtime deployment that runs the workload.
A different process namespace, or measurements taken after services stop, does
not establish the workload's RSS or whether an OOM kill occurred.

The sampler records each owned process and discovered descendants separately.
The **Core** row is the direct process, including embedded Chroma, Core's HTTP
and Artifact handling, and any other in-process allocations. These cannot be
assigned to individual components from RSS alone. The **Runtime** root and its
sampled descendant workers are separate. RSS tree sums count shared pages more
than once; optional PSS gives proportional attribution and is available only
when the kernel permits the corresponding `smaps_rollup` read. The tool does
not sum roles and label the result unique memory.

## Measurements and limits

- Use a quiet per-case baseline after fixture setup, followed by upload-only
  or actual RAG ingestion, a quiet interval with the artifacts/index retained,
  and a quiet interval after cleanup. In a fresh run, vary bytes and concurrency
  separately before combining them. Keep file bytes below the 10 MiB multipart
  request ceiling, and treat the parser's output budget as a separate limit.
- `memory-samples.jsonl` contains same-namespace process measurements with a
  sample's monotonic acquisition interval. `memory-summary.json` groups samples
  wholly within independently timed workload windows and includes sample counts
  and missing stages. If a short upload or enqueue is quicker than the sample
  cadence, do not equate absence of samples to absence of allocation. Mark
  combined parse/index windows honestly when their separate boundaries are
  unavailable.
- Direct RSS peaks are sampled, not exact maxima. Kernel `VmHWM` is the
  process-lifetime high-water mark, not reset between phases and not a per-case
  continuous counter. Growing values between phases are useful supplementary
  evidence; unchanged HWM cannot rule out a smaller short-lived spike.
- Report after-idle or after-cleanup RSS separately. RSS staying above baseline
  does not alone prove a leak: allocator arenas, memory mappings, retained
  caches and asynchronous work can keep pages resident.
- Host `MemAvailable` and cgroup-v2 `memory.current`, `memory.max`, and
  OOM event deltas are optional. An inaccessible control group, missing
  counters, or unknown scope produces an unknown result, not zero. Even a
  count increment only proves a kill in that shared cgroup. Correlate with
  process lifecycle and application/launcher evidence before attributing an
  OOM to Core. A process surviving the tested envelope does not establish
  the OOM threshold.

When reusing the harness, sample only process IDs created by that launcher:

```python
with MemorySampler(
    result_directory / 'memory',
    roots={'core': core.pid, 'runtime': runtime.pid},
    stage_events=result_directory / 'result' / 'stages.jsonl',
) as sampler:
    sampler.mark('baseline')
    if not sampler.wait_for_samples('baseline'):
        raise RuntimeError('Owned Core/Runtime memory baseline not observed')
    sampler.mark('benchmark')
    run_owned_workload()
    sampler.mark('recovery')
    sampler.wait_for_samples('recovery')
```

Use flushed JSON Lines events of the form
`{"stage":"case:upload","event":"start","monotonic_ns":123}` and a paired
`"end"` record from the workload. Record these events using
`time.monotonic_ns()` in that same deployment. Keep the Core and Runtime
processes alive until the sampler finalizes the report.

## Run this memory workload

Reuse the [public retrieval setup and wheelhouse](vdb-benchmark-public.md#setup-and-run).
The launcher fetches and verifies the pinned 150 MiB
[Salesforce WikiText-103 raw train shard](https://huggingface.co/datasets/Salesforce/wikitext)
(CC BY-SA; see dataset provenance) on first use. Exact-size, disjoint
UTF-8 windows are materialized under the requested external output directory
and hashed before the workload. Set `--asset-cache` to reuse a verified input
cache; never commit the source shard, processed inputs or generated evidence.

```bash
uv run --no-sync python -m tools.entrypoints.vdb_benchmark_local --suite rss \
  --profile tools/profiles/vdb-upload-memory-public.json \
  --plugin-wheelhouse "$QA_ROOT/wheels" --output "$QA_ROOT/vdb-upload-rss" \
  --memory-mapping-every 5 --trial-timeout 1800
```

Use `vdb-upload-memory-public-probe.json` to preflight storage, ownership, and
sampling. The full profile sends real 8 MiB TEXT cases serially and with four
HTTP requests in flight, and independently indexes four 512 KiB or 2 MiB TXT
files with four outstanding task lifecycles. The 2 MiB concurrent case is
repeated on the same Core after cleanup.
File-size readback confirms accepted bytes, not just requested bytes. RAG indexing
uses a 2,048-character chunk size (no overlap) with deterministic embedding;
it verifies completed file receipts and counts actual persisted Chroma vectors.
Cleanup removes owned files through the document API before deleting the KB,
and independently checks that no indexed vectors remain. This sequence does
not establish that a KB-only delete removes underlying vectors.
The index stage includes enqueue, parsing, embedding and upserts. These are
closed-loop cases and not a guarantee at different formats, vector scales,
concurrency or container limits.

Upload and memory results are reported separately. Samples begin before the
first case; the child emits per-case quiet baseline, upload, ingest, retained
idle and post-cleanup idle windows. Unless a resource limit and OOM counters
are readable, successful cases mean the processes stayed alive in this run,
not that a specific container limit is safe. Low host headroom aborts rather
than intentionally forcing an OOM.

## Optional mapping attribution

To inspect what occupies the sampled resident set, opt into detailed Linux
`smaps` at a slower cadence than the basic RSS measurements. For example,
`MemorySampler(..., mapping_every=5, chroma_dir=owned_data_dir / 'chroma')`
reads one detailed sample in every five ordinary ticks for Core and Runtime
(with their observed descendants). Ordinary sampling does not read detailed
`smaps` by default. A trace includes aggregate counts only, not individual
mapping names, memory addresses, or the configured Chroma directory path.

Each mapping contributes once to a category: named heap, named stack,
other anonymous maps, shared memory, explicit files under the owned Chroma
path, shared libraries, other private/shared file maps, kernel special maps,
or unclassified. Inspect each stage's `mapping_attribution` for coverage,
peak and final **sampled mapping** composition and category deltas relative
to an actual quiet baseline sample. The peak detailed sample can occur at
a different time from the more frequently observed process RSS peak. A
short stage or inaccessible `smaps` cannot establish category sizes.

These are **mapping categories, not owners of allocations**. The kernel's
`Anonymous` field is a separate per-mapping backing counter and can also
include anonymous copy-on-write pages in file mappings. It is not additive
to the RSS categories. Chroma files account only for named file maps under
the configured directory, not all Chroma memory. Anonymous RSS may include
Python, Chroma's native allocator, SQLite scratch space, parser buffers, and
other allocations; a large anonymous category does not identify which
component is responsible. `smaps` RSS and `status` RSS are collected separately;
small signed differences are not proof of unclassified allocations.


## Optional native allocation diagnostic

Run Memray separately from ordinary RSS and timing experiments. It samples
allocation call stacks instead of mapping labels, adds overhead, and its
native allocation high-water mark is **not** the process RSS peak. Install
Memray in the QA environment (or pass an isolated official wheel installation
with `--memray-site`). Use a fresh output directory:

```bash
uv pip install 'memray==1.19.1'
uv run --no-sync python -m tools.entrypoints.vdb_benchmark_local --suite rss \
  --profile tools/profiles/vdb-upload-memory-public-probe.json \
  --plugin-wheelhouse "$QA_ROOT/wheels" --output "$QA_ROOT/native-rss" \
  --core-memray --memory-mapping-every 5 --trial-timeout 1800

uv run --no-sync python -m tools.entrypoints.vdb_benchmark_memray_report \
  --input "$QA_ROOT/native-rss/01-chroma/core-allocations.bin" \
  --output "$QA_ROOT/native-rss-peak.json"
```

The launcher invokes `memray run --aggregate --native` for Core only.
Keep the raw trace outside Git; native stack paths may disclose local
filesystem structure. Publish aggregate category counts rather than frames
or local paths.
