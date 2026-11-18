# SQLite write admission experiment

Set `database.sqlite.experimental_write_queue: true` and restart Core to run the experiment. The default is false. Both configurations retain WAL, the 30-second SQLite busy timeout and the short Artifact publication transaction from #3075.

The queue belongs to one SQLite engine. Artifact publication, monitoring records, session summary updates and RunLedgerStore's write sessions acquire it before opening a session, and release it after the session exits. Pure Ledger reads go straight to the pool. Nested Workspace calls join the owning transaction. A transaction that has already started outside admission cannot safely acquire a slot partway through. An independent Ledger write attempted by the same task while holding the slot fails explicitly. Other engines, other processes and direct SQL are outside the queue.

## Reproduce

On a development host with the Core test dependencies, use a fresh directory on the test disk for each process:

```sh
out=$(mktemp -d /path/on/test/disk/queue.XXXXXX)
for trial in off-1 on-2 on-3 off-4; do
    ADMISSION=${trial%-*} BENCH_OUT="$out/$trial.jsonl" PYTHONPATH=src:sdk/src:. \
        python -m pytest -q tests/manual/sqlite_write_admission.py -k sqlite-database \
        --basetemp="$out/tmp-$trial" || break
done
```

Each process initializes a fresh disk-backed database using the production SQLite manager. Each wave starts 4 Box publishers (1, 1, 10 and 10 previously exported files), 12 writers appending 4 events each to distinct runs, and 4 readers looking up a run 6 times each. Workers share one engine and pool. Launch order is shuffled with the wave index as the seed. Setup and file export precede the timer. Timing ends when all 76 operations finish. Every publication and read is checked, and all persisted event sequences are reconciled at the end of each process.

Discard wave 0 as warm-up. Pool the next 16 waves per process by mode. Percentiles use nearest rank. Throughput is completed publications, appends and reads divided by the sum of timed wave durations. Time to first write starts at the Ledger call and ends immediately after its first INSERT succeeds; it includes queueing, connection checkout, duplicate lookup and driver time. The queued run additionally measures time inside lock acquisition. Neither value isolates SQLite's internal lock wait.

## Artifact and Ledger benchmark on Linux (before monitoring joined the queue)

The baseline for both settings was #3075 (`85b7c9107`). Python 3.12.14, SQLite 3.53.1, ext4, database content backend, one process and one engine. Each setting completed 1,536 measured appends, 128 publications and 768 reads, with no missing or duplicate event sequences. The numbers below combine the two processes per setting.

| Metric | Queue off | Queue on |
| --- | ---: | ---: |
| Ledger append P50 | 14.05 ms | 44.69 ms |
| Ledger append P99 | 679.70 ms | 433.57 ms |
| Slowest ledger append | 1,006.77 ms | 532.66 ms |
| Longest time to first successful Ledger INSERT | 1,004.39 ms | 530.22 ms |
| Longest application queue wait | No queue | 526.77 ms |
| All completed operations / second | 111.26 | 164.92 |
| Read P50 | 21.60 ms | 7.80 ms |
| Read P99 | 256.73 ms | 15.65 ms |

Both queue-on trials had higher throughput and lower read and Ledger P99 than either queue-off trial. The extra wait for otherwise fast appends raises their median. This measures overlapping bursts on one engine; sustained open-loop load, monitoring writes and multi-process contention remain unmeasured.

## Transaction stage diagnostics

In YAML, `experimental_write_queue: false` disables admission, `artifact_ledger` queues Artifact publication and Ledger writes, and `true` includes monitoring. Set `database.sqlite.experimental_write_timing: true` separately to emit one `sqlite_write_timing` log line for each measured committed write scope. Both experiments default to off.

- `queue_ms` measures entry to acquisition of the application slot (zero when bypassed).
- `before_write_ms` measures admission to the first successful compiled INSERT, UPDATE or DELETE on the committing connection. It includes connection checkout, preparation, reads and execution of that first DML. `first_dml_ms` is the driver-call portion; it includes scheduling, SQLite waits and SQL execution.
- `through_commit_ms` measures first DML return to successful outer commit return. Nested Workspace calls share the outer sample. `summary_ms` separately measures time spent applying or linking the summary or expiring receipts inside the sampled scope; this overlaps the stages.

No query text, arguments or tenant/session identifiers are logged. Read-only, rolled-back and uninstrumented transactions have no committed-write sample. An unqueued outer transaction cannot be promoted by a nested call. The measurements describe completed transactions and exclude time before entering the marked scope.

For a matched-prefix diagnosis, use the existing accelerated soak environment and set `LANGBOT_SOAK_TIMING_WAVES=45`, `LANGBOT_SOAK_WRITE_TIMING=1`, and `LANGBOT_SOAK_SQLITE_WRITE_QUEUE` to `off`, `artifact_ledger`, or `on`. This replays the original deterministic inputs, GC and pacing schedule and records all wave times, including misses; it ends with a diagnostic marker, not a soak PASS. Leave the diagnostic length unset for normal fail-fast acceptance.
