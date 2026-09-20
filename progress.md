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
- Unattended cleanup must stop both the host StageGuard API process and compose services it owns; a surviving API is a cleanup failure.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Made compose teardown fail closed on non-zero exit and timeout-bounded at 45 seconds.
- Added a bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are not destroyed when the API is unreachable.
- Fixed `--cleanup` to stop the StageGuard API host process before compose teardown and fail closed if the API remains reachable.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, a dedicated read-only lifecycle dashboard, and `docs/runbooks/lifecycle-safety.md` linked from that dashboard.

## Latest run — 2026-09-20 — complete unattended runtime cleanup

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py`, `scripts/demo_local.py`, `docker-compose.yml`, and the existing non-interactive release regression tests. Found a concrete lifecycle leak: `demo_local.up()` launches the StageGuard API as a host process, outside Docker Compose, while release `--cleanup` only called `docker compose down`. A successful unattended acceptance could therefore leave the authenticated API listening on port 9110 and contaminate the next run despite reporting cleanup.

### Exact changes made

- Added `_cleanup_owned_runtime()` to `scripts/demo_release.py`.
- Cleanup now stops the owned StageGuard host API first, verifies that its health endpoint is no longer reachable, and only then tears down the owned compose stack.
- If the API remains reachable after the stop attempt, cleanup fails closed and the acceptance result becomes failure instead of falsely reporting a clean environment.
- Updated `--cleanup` help/output to state that both the owned API and compose stack are removed.
- Added `runtime/tests/test_validation_demo_release_cleanup.py` covering cleanup order and the surviving-API fail-closed case.
- Implementation commit: `a6d59e994ce3aa4181707161c77c0584b786f38a`.
- Regression-test commit: `afddd04020b6bae2074bb1520beaed12969afcbc`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the source and regression-test updates.
- Static review confirms `--cleanup` can no longer report success after merely removing compose services while leaving the StageGuard API host process alive.
- The helper verifies API termination before compose teardown, making a surviving API visible rather than hiding the partial cleanup.
- Existing pre-existing-stack ownership guards remain before runtime ownership is claimed, so this cleanup path is not invoked for an API/compose stack that predates the rehearsal.
- This repository connector does not expose an executable checkout, so the new tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. The acceptance runtime is the host API plus compose services; cleanup semantics must cover both.
2. Cleanup order is API first, compose second, so the API cannot remain alive against disappearing evidence dependencies.
3. A reachable API after `_stop_api()` is an explicit acceptance failure.
4. Pre-existing resources remain user-owned and outside this cleanup path.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix concrete failures, then run `python scripts/demo_release.py --non-interactive --cleanup` from an empty compose project and verify ports 9110, 9108, 9090, and 3000 are no longer listening afterward. Also verify a stopped pre-existing StageGuard compose container is refused without destruction. After those gates pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution over additional speculative hardening.
