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

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added an unattended local acceptance path with `python scripts/demo_release.py --non-interactive`; it preserves stack recreation, Grafana MCP smoke, healthy evidence gates, deterministic fault injection, and post-fault evidence gates while removing only the human stdin pause.
- Added opt-in `--cleanup` to the release rehearsal so unattended runs can deterministically tear down the compose stack on success, evidence failure, or partial startup failure without touching a pre-existing StageGuard API/stack.
- Made compose teardown fail closed: a failed pre-run teardown can no longer be treated as a fresh telemetry boundary, and failed opt-in cleanup now makes an otherwise successful acceptance run fail.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe` from the authoritative fixed-cardinality `stageguard_lifecycle_safety_state` metric; missing data is alerting.
- Added a dedicated read-only `StageGuard Lifecycle Safety` Grafana dashboard for the authoritative one-hot lifecycle state, telemetry freshness, scrape transport, and separate recovery proof.
- Added `docs/runbooks/lifecycle-safety.md`, an operator procedure that preserves StageGuard's no-replay and telemetry-verified recovery invariants during lifecycle incidents.
- Linked the lifecycle dashboard directly to that repository-owned operator runbook and added validation-owned regression coverage so the operational path cannot silently disappear or become a mutable control surface.

## Latest run — 2026-09-20 — fail-closed acceptance teardown

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py` and `runtime/tests/test_validation_demo_release_noninteractive.py`. The new cleanup path invoked `docker compose down` with `check=False` and discarded its return code. Consequently, a failed pre-run teardown could still be treated as a clean telemetry reset, while a failed final `--cleanup` could still return exit code 0 and falsely claim unattended acceptance succeeded while resources remained.

### Exact changes made

- `_compose_down()` now checks the Docker Compose return code and raises `EvidenceGateError` on non-zero exit.
- `_recreate_compose_stack()` therefore fails closed when stale resources cannot be removed instead of continuing across an untrustworthy telemetry boundary.
- Refactored `main()` to retain an explicit `exit_code`, allowing cleanup failures in `finally` to convert an otherwise successful acceptance result into failure without suppressing the cleanup attempt.
- Cleanup errors are emitted separately as `RELEASE CLEANUP ERROR` for operator diagnosis.
- Preserved the pre-existing-stack ownership guard: `--cleanup` still never tears down a StageGuard API/stack that was running before the rehearsal.
- Added regression coverage for non-zero compose teardown, failed fresh-boundary recreation, and cleanup failure overriding an otherwise successful acceptance result.
- Implementation commit: `52f5adbeec9451f5d78bcfe3c1991de58b8b119a`.
- Regression-test commit: `4a79233592636cf050e3f62f4a51ee2b52927ecc`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the Python source and regression-test updates.
- Static review confirms both the pre-run freshness boundary and requested final cleanup are now fail-closed.
- This repository connector does not expose an executable checkout, so the updated tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. A clean-stack acceptance run must not continue if Docker Compose cannot prove teardown succeeded; otherwise old Prometheus samples or containers could invalidate evidence claims.
2. When `--cleanup` is requested, leaving compose resources behind is an acceptance failure even if all evidence gates passed.
3. Cleanup remains opt-in for interactive/demo users, but its contract is strict once requested.
4. A pre-existing running StageGuard API remains a hard stop and is never cleaned up by this script.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive --cleanup`. Verify Grafana provisions the lifecycle dashboard version 2 and its runbook link, `stageguard-lifecycle-unsafe` remains Normal while lifecycle state is `ok`, pinned `grafana/mcp-grafana:1.4.1` passes the read-only smoke, and both the pre-run teardown and final cleanup are observed to fail closed under a deliberately induced Docker Compose teardown error. After those gates pass, prioritize failures revealed by real execution over additional speculative hardening.
