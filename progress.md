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
- Unattended cleanup must stop the host StageGuard API process and remove compose containers it owns; both outcomes are verified and a partial teardown is a cleanup failure.

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
- Fixed `--cleanup` to stop and verify the StageGuard API host process, tear down compose, then verify no compose containers remain.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, a dedicated read-only lifecycle dashboard, and `docs/runbooks/lifecycle-safety.md` linked from that dashboard.

## Latest run — 2026-09-20 — verify compose cleanup completion

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository tree, `scripts/demo_release.py`, and `runtime/tests/test_validation_demo_release_cleanup.py`. The previous run correctly added host-API shutdown verification, but `docker compose down` success was still accepted as proof that compose cleanup completed. A zero exit code is not the same as a postcondition: remaining project containers would contaminate later freshness rehearsals while `--cleanup` reported success.

### Exact changes made

- Extended `_cleanup_owned_runtime()` in `scripts/demo_release.py` to call the existing bounded `_compose_has_resources()` after `docker compose down`.
- Cleanup now fails closed with `EvidenceGateError` if any project container remains after teardown.
- Updated `--cleanup` help text to describe verified removal rather than merely requesting a stop.
- Extended `runtime/tests/test_validation_demo_release_cleanup.py` to require API-stop -> compose-down -> compose-verification ordering.
- Added a regression case proving surviving compose resources become a cleanup failure.
- Preserved the existing surviving-API failure behavior and its rule that compose teardown is not attempted while the owned API is still reachable.
- Implementation commit: `d5a1bc91a72bb20f5531f6593967d2e55e427eba`.
- Regression-test commit: `9da22ac52134241d5f5b6fdebbeff1f0f28f260d`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted both source and regression-test updates.
- Static review confirms cleanup now verifies both runtime components it owns: the host API must be unreachable and the compose project must report zero containers.
- The compose postcondition reuses the existing 45-second bounded, fail-closed ownership query, so Docker timeout/error during verification cannot be mistaken for successful cleanup.
- This repository connector does not expose an executable checkout, so the updated unit tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. Process exit codes are transport/control-plane evidence, not sufficient proof of cleanup postconditions.
2. Reuse the same project-scoped `docker compose ps -q --all` ownership primitive before and after acceptance rather than adding host-wide Docker inspection.
3. Keep cleanup fail-closed: inability to prove zero remaining project containers makes unattended acceptance fail.
4. Do not add port-killing logic; StageGuard must never terminate unrelated host processes merely because they occupy a known development port.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix concrete failures, then run `python scripts/demo_release.py --non-interactive --cleanup` from an empty compose project and verify the API is unreachable and `docker compose ps -q --all` is empty afterward. Also verify a stopped pre-existing StageGuard compose container is refused without destruction. After those gates pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution over additional speculative hardening.
