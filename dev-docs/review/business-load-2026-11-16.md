# Fixed-arrival business-load validation

## Scope and environment

The workload exercises signed HTTP Bot ingress, persistent multi-member group
conversations, Core orchestration, the in-tree SDK and Plugin Runtime,
LocalAgent, LangRAG, GeneralParsers, SQLite run/event persistence, and real Docker
Box commands. Generation and embeddings use deterministic loopback services.
The offered case mix is 50% chat, 25% Box and 25% RAG.

The development host runs Ubuntu 22.04, Linux 5.15, Python 3.12.13 and Docker
26.1.3, with four logical CPUs and approximately 7.3 GiB RAM. The test service
has a 150% CPU quota and a 2 GiB memory ceiling. Docker Box containers are
observed separately and sit outside that service cgroup. Existing host workloads
share the machine. Results apply to this resource envelope and workload.

The source-stack runner installs plugins built from the tested checkout, uses
the in-tree `langbot-plugin` 0.7.25 and the checksum-verified `lbctl` v0.5.1.
Provider responses have a configured 0.6-second delay. Each Box run executes two
commands. The reference and ramp use a one-second sleep per command; the final
concurrent soak uses four seconds per command.

The observed Box image is `python:3.12-alpine`, image ID
`sha256:4076016aea5420e5c87eb52280edfc527ace1ce31dc1c9288b1cc4ef9a0e8905`,
with repository digest
`python@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89`.

## Implementation

Candidate `011980a7e27c27ea52c1615b9ee808032e3a90eb` adds optional fixed-arrival
scheduling, a bounded waiting queue, per-arrival outcome journals, arrival and
dispatch latency, a per-case arrival P95 gate, custom endurance phase overrides,
and an execution budget override.
Follow-up candidate `af54fa513060cc011fae2fea8caf175e50f620ae` adds a validated
Box command duration setting, fingerprints the actual generated stimulus,
strengthens malformed-profile validation, and covers the independent CLI path
with an actual subprocess invocation counter.

The arrival balance is checked independently of successful response latency.
Queue overflow, expiry at the load deadline and blocked conversations all fail
the run. Acceptance includes run-ledger, history/isolation, Provider-wire, Box
identity, resource-growth and cooldown-queue checks.

## Reproduction

Run from the repository root on a prepared Linux development host with Docker
access. Each output path must be new.

```sh
export LAB_ROOT=/path/to/isolated-lab
export LBCTL=/path/to/lbctl
uv sync --dev --frozen --python 3.12
uv run --no-sync python -m unittest discover -s tools/tests -p 'test_*.py' -q

uv run --no-sync python -m tools.entrypoints.regression_ci \
  --suite endurance --plugins plugins --lbctl "$LBCTL" \
  --output "$LAB_ROOT/runs/baseline"

uv run --no-sync python -m tools.entrypoints.regression_ci \
  --suite endurance --plugins plugins --lbctl "$LBCTL" \
  --load-profile tools/profiles/arrival-ramp.json --budget-seconds 900 \
  --output "$LAB_ROOT/runs/arrival-ramp"

uv run --no-sync python -m tools.entrypoints.regression_ci \
  --suite endurance --plugins plugins --lbctl "$LBCTL" \
  --load-profile tools/profiles/arrival-soak.json --budget-seconds 1200 \
  --output "$LAB_ROOT/runs/concurrent-soak"

uv run --no-sync python -m tools.entrypoints.regression_ci \
  --suite scenarios --scenario-groups faults lifecycle --restart-services \
  --plugins plugins --lbctl "$LBCTL" --output "$LAB_ROOT/runs/recovery-contracts"
```

## Results

The original paced baseline, started from Core `b05872e8`, completed 526 requests
with all business checks, independent mixed evidence and resource recovery
passing. At target rates of 2 and 4 RPS, successful throughput was approximately
1.10 and 1.03 RPS. Completed chat/Box/RAG counts were 308/86/132. These counts
show that slower Box sessions reduce the realized case share under paced load.
This run supplies a functional reference for the new fixed-arrival experiments.

The complete regression-tool suite passed on Linux with **216 tests**. Ruff lint
and format checks and `git diff --check` passed. New regressions independently
count actual HTTP and CLI invocations, exercise queue overflow and deadline
expiry, retain group turn/history semantics, and reject unsupported options.

The fixed-arrival ramp produced these measured results. Every dispatched
request completed and matched its persisted AgentRun. All arrival balances
reconciled, with zero unknown outcomes or blocked conversations.

| Phase | Offered RPS | Planned | Successful | Client queue drops | Deadline expiry | Arrival P95, chat / Box / RAG |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | 0.8 | 96 | 96 | 0 | 0 | 2.00 / 6.94 / 2.12 seconds |
| Pressure | 4 | 480 | 130 | 334 | 16 | 37.50 / 63.38 / 27.88 seconds |
| Recovery | 0.8 | 96 | 96 | 0 | 0 | 2.18 / 6.97 / 2.19 seconds |

The ramp correctly failed its pressure-stage arrival, throughput and latency
checks. The independent mixed-business oracle passed. The waiting queue reached
its configured capacity of 16; Core's sampled query queue peaked at four.
All four Core/Box cooldown queues returned to zero in every phase, and resource
growth stayed within the configured limits. The recovery phase reused the same
16 conversations after pressure and restored low-rate latency and delivery.

The initial 15-minute steady run completed 720/720 requests, with no arrival
losses, ledger discrepancies, health failures or resource-threshold failures.
Its chat/Box/RAG arrival P95 values were 2.05/7.02/2.38 seconds. The full run
failed the independent Box concurrency assertion: at 0.8 aggregate RPS, Box
arrivals were five seconds apart and their one-second command windows were
entirely serialized. This failed result remains in `runs/arrival-soak`.

The follow-up extends each Box command to four seconds while retaining the
offered mix, rate, 16 groups, eight workers and all acceptance assertions. An
independent live SQLite event query confirmed overlapping commands on different
Box hostnames. The workload's recorded stimulus hash also matches the actual
generated scenario file.

The corrected 15-minute run **passed**, with 720/720 arrivals dispatched and
completed, zero drops/expiry/unknown outcomes, 16 conversations, three Bots and
four distinct reused Boxes. All 720 persisted AgentRuns reconciled. The
independent mixed oracle confirmed overlapping Box tool-event windows and
generation Provider service intervals. Chat/Box/RAG arrival P95 values were
**2.09/13.33/2.94 seconds**. The waiting queue peaked at zero, all four cooldown
queues returned to zero, and resource checks passed. Core and Plugin Runtime
RSS growth was 26.60 and 20.18 MiB respectively, within their 64 MiB allowances.
Evidence is retained in `runs/concurrent-soak`.

The finite fault/lifecycle pass completed **93/93 checks** with all stages
passing, including model failures/fallback, tool and cancellation behavior,
conversation lifecycle, attachment delivery and retrieval. The controlled Core
and Plugin Runtime restart checks also passed, with all four expected AgentRuns
reconciled. The test command enabled `faults` and `lifecycle`, plus
`--restart-services`.

All test-owned service processes and Docker Boxes were stopped after the runs.
The host's existing Console HTTP endpoint remained reachable at the final check.

## Evidence and interpretation

Each real-stack run retains `gate/gate.json`, `gate/suite/summary.json`, the
resolved profile, plugin versions and hashes, request/arrival journals, process
and container observations, Provider recordings and service logs. Generated
credentials remain in the run's private directory.

Arrival-to-completion latency includes client waiting and run-ledger
verification. Its percentile population consists of dispatched outcomes.
Undispatched arrivals are reported separately and always fail acceptance.
Worker limits and group serialization can constrain dispatch. Service queues,
CPU use and actual execution overlap are required to interpret bottlenecks.

Unverified scope includes real-model answer quality, provider network behavior,
public IM delivery, E2B/nsjail behavior, PostgreSQL multi-Core capacity,
day-scale endurance and a production SLO. The finite recovery pass exercises
attachment delivery and injected execution faults separately from mixed load.
