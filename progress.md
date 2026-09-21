# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and Grafana lifecycle safety surfaces.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Production remediation accepts only canonical operation IDs, bounded canonical target identities, frozen execution/reconciliation capabilities, exact validated transport/reconciliation result types, and bounded finite policy configuration.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.
- Local acceptance never destroys pre-existing compose resources merely because the StageGuard API is unreachable.
- Cleanup independently attempts all requested runtime components it owns and reports partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt.
- A persisted local API PID is never sufficient authority to signal a process; shutdown structurally verifies the live command signature first.
- Health reachability is not process ownership: a structurally verified unhealthy local API is still an owned process.
- Persisted PID metadata must be a strictly positive process ID before lookup or signal.
- Local stop must not report success if teardown of an owned component fails.
- Successful Compose teardown must be verified against all project containers, including stopped containers, not inferred solely from `docker compose down` returning zero or the default running-only `compose ps` view.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Hardened unattended Compose ownership preflight/teardown and aggregate cleanup verification.
- Added critical Grafana lifecycle alert/dashboard/runbook surfaces.
- Hardened local API startup ownership so early child exit/readiness timeout cannot strand stale PID metadata; cleanup targets only the exact spawned child.
- Hardened cross-invocation API shutdown against PID reuse with structured argv validation.
- Decoupled API health from process ownership; verified unhealthy processes are still safely cleaned up.
- Rejected zero/negative persisted PIDs before process lookup/signalling.
- Implemented truthful local stop teardown: missing Docker or non-zero `docker compose down` becomes `DemoError`; `Stopped.` is emitted only after successful teardown or explicit `--keep-stack`.
- Implemented independent local stop cleanup so API failure no longer suppresses owned Compose teardown; multiple failures are aggregated.
- Implemented post-`down` project-container verification before local stop can report success.

## Latest run — 2026-09-21 — all-state Compose verification gate

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and the complete focused `runtime/tests/test_demo_local_stop_lifecycle.py` suite. Also checked current official Docker Compose documentation for `docker compose ps` and `docker compose down` semantics.

### Finding

The previous post-`down` verification used `docker compose ps -q`. Docker's current official CLI documentation states that `compose ps` shows only running containers by default; `--all` is required to include stopped containers. Therefore a stopped-but-retained StageGuard project container could be missed and local stop could still print `Stopped.` despite incomplete teardown.

### Exact changes made

- Updated the focused lifecycle regression contract to require `docker compose ps --all -q` after successful `down`.
- The retained-container regression now models a project container visible only through the all-state query.
- The empty-project success regression likewise requires the all-state query before successful completion.
- Relaxed the independent-cleanup assertion from an exact single Docker call to `assert_any_call("down")`, because successful teardown now legitimately performs a subsequent verification call.
- Regression commit: `776b1d398037d60d2ad3ce15177a1ec4a6d2b7f1`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression update.
- Official Docker docs verified the semantic gap: default `docker compose ps` lists only running containers, while `--all` includes stopped containers.
- This is intentionally a red implementation gate: current `scripts/demo_local.py` still invokes `ps -q`, so no green claim is made.
- This connector environment does not expose a runnable checkout, so executable lifecycle validation remains pending.

### Decisions

1. Cleanup truthfulness means absence of both running and stopped project containers.
2. Verification remains Compose-project-scoped; StageGuard will not enumerate, prune, or manipulate unrelated Docker resources.
3. The regression is established before implementation so the intended safety behavior is explicit and reviewable.
4. No CI workflow is added solely for this validation; avoid noisy GitHub Actions usage.

### Blockers / unknowns

- The implementation must change the post-`down` query from `compose ps -q` to `compose ps --all -q`.
- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Implement the all-state post-teardown query (`docker compose ps --all -q`) in `scripts/demo_local.py`, then execute the accumulated local lifecycle suites on Linux and Windows before consolidated validation, unattended Docker cleanup rehearsal, and the pinned Grafana MCP `1.4.1` read-only smoke.
