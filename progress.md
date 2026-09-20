# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and dedicated Grafana alert/dashboard surfaces for the authoritative composite lifecycle safety state.

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

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added an unattended local acceptance path with `python scripts/demo_release.py --non-interactive`; it preserves stack recreation, Grafana MCP smoke, healthy evidence gates, deterministic fault injection, and post-fault evidence gates while removing only the human stdin pause.
- Added opt-in `--cleanup` so unattended runs deterministically tear down compose resources owned by that rehearsal on success, evidence failure, or partial startup failure.
- Made compose teardown fail closed on non-zero exit and timeout-bounded at 45 seconds.
- Added a bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are never destroyed just because the API health probe is unreachable.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe` from the authoritative fixed-cardinality `stageguard_lifecycle_safety_state` metric; missing data is alerting.
- Added a dedicated read-only `StageGuard Lifecycle Safety` Grafana dashboard for the authoritative one-hot lifecycle state, telemetry freshness, scrape transport, and separate recovery proof.
- Added `docs/runbooks/lifecycle-safety.md`, preserving StageGuard's no-replay and telemetry-verified recovery invariants during lifecycle incidents, and linked it from the lifecycle dashboard.

## Latest run — 2026-09-20 — compose ownership preflight

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py` and `runtime/tests/test_validation_demo_release_noninteractive.py`. The prior ownership guard checked only `demo_local._api_running()`. That was insufficient: an existing compose project can have stopped, unhealthy, starting, or partially-created containers while the API is unreachable. In that state the rehearsal would call `docker compose down --remove-orphans` and could destroy resources it did not create.

### Exact changes made

- Added `_compose_has_resources()` using bounded `docker compose ps -q --all` against the repository compose project.
- The ownership preflight is timeout-bounded and fails closed on non-zero Compose exit or timeout; inability to prove an empty project never authorizes teardown.
- `main()` now refuses acceptance before `_recreate_compose_stack()` whenever project containers already exist, even when the API is unreachable, and tells the operator to inspect or explicitly stop the stack.
- Kept the existing fast API-running guard first, avoiding an unnecessary Compose query in that known pre-existing-stack case.
- Preserved post-preflight ownership semantics: only after the empty-project check and successful freshness teardown can the rehearsal mark the stack as owned and clean it up.
- Added regression coverage for resource detection, empty-project acceptance, preflight non-zero exit, preflight timeout, and the critical API-down/pre-existing-container non-destruction case. Updated existing main-path tests to model a clean ownership preflight.
- Implementation commit: `1bdadaa8cbd7fb10edd312dcfa485523676b8716`.
- Regression-test commit: `b638350fdc3b70e601713249ea02ccb59a94ae9c`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the Python source and regression-test updates.
- Static review confirms the rehearsal cannot reach `_recreate_compose_stack()` or cleanup when the ownership preflight reports existing compose containers.
- The preflight itself is bounded and fail-closed, so Docker/Compose uncertainty does not become permission to destroy resources.
- This repository connector does not expose an executable checkout, so the updated tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. API reachability is not a valid ownership signal for local infrastructure.
2. Existing project containers are user-owned unless this process created them during the current rehearsal.
3. The unattended acceptance command may fail and require explicit operator cleanup rather than destroy ambiguous pre-existing resources.
4. Compose ownership discovery must be subject to the same timeout/fail-closed policy as teardown.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive --cleanup` from an empty compose project. Also explicitly create a stopped StageGuard compose container and verify the rehearsal refuses to destroy it. After those gates pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution over additional speculative hardening.
