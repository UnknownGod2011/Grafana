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
- Added opt-in `--cleanup` so unattended runs deterministically tear down the compose stack on success, evidence failure, or partial startup failure without touching a pre-existing StageGuard API/stack.
- Made compose teardown fail closed on non-zero exit and timeout-bounded at 45 seconds, so neither the fresh-evidence boundary nor requested cleanup can hang indefinitely or silently succeed after teardown failure.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe` from the authoritative fixed-cardinality `stageguard_lifecycle_safety_state` metric; missing data is alerting.
- Added a dedicated read-only `StageGuard Lifecycle Safety` Grafana dashboard for the authoritative one-hot lifecycle state, telemetry freshness, scrape transport, and separate recovery proof.
- Added `docs/runbooks/lifecycle-safety.md`, preserving StageGuard's no-replay and telemetry-verified recovery invariants during lifecycle incidents, and linked it from the lifecycle dashboard.

## Latest run — 2026-09-20 — bounded unattended teardown

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py` and `runtime/tests/test_validation_demo_release_noninteractive.py`. The prior run correctly rejected non-zero `docker compose down` exits, but the subprocess itself had no timeout. A wedged Docker daemon or Compose process could therefore hang both the pre-run freshness boundary and final `--cleanup` forever, violating the repository's timeout-bounded unattended-validation invariant.

### Exact changes made

- Added `COMPOSE_DOWN_TIMEOUT_SECONDS = 45.0` to the release rehearsal.
- `_compose_down()` now passes that bound directly to `subprocess.run`.
- `subprocess.TimeoutExpired` is translated into `EvidenceGateError`, preserving the same fail-closed contract used for non-zero Compose exits.
- Because both fresh-stack recreation and final cleanup use `_compose_down()`, the bound protects both lifecycle edges without duplicating behavior.
- Added regression coverage proving the timeout is supplied and that timeout expiry is rejected as an evidence-gate failure.
- Implementation commit: `cd87fad510967e3e0e6c0ccf7762620e557072ef`.
- Regression-test commit: `0025f5c4b5b0e84a563975f1ea37afbf31285a46`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the Python source and regression-test updates.
- Static review confirms timeout expiry cannot be mistaken for successful teardown and flows through the existing failure handling.
- This repository connector does not expose an executable checkout, so the updated tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. Unattended acceptance lifecycle operations must be time-bounded as well as return-code checked.
2. A Docker teardown timeout is an acceptance failure, not a warning, because StageGuard cannot prove a fresh evidence boundary or successful requested cleanup afterward.
3. The timeout remains a repository constant rather than a user-facing tuning flag until real execution demonstrates a need for configuration.
4. The pre-existing-stack ownership guard remains unchanged; the rehearsal never destroys a stack it did not start.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive --cleanup`. Verify Grafana provisions the lifecycle dashboard and runbook link, `stageguard-lifecycle-unsafe` remains Normal while lifecycle state is `ok`, pinned `grafana/mcp-grafana:1.4.1` passes the read-only smoke, and teardown failure/timeout both produce non-zero acceptance without touching a pre-existing stack. After those gates pass, prioritize failures revealed by real execution over additional speculative hardening.
