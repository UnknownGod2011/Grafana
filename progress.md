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
- Unattended cleanup must independently attempt all runtime components it owns, verify the host API is unreachable and compose has zero containers, and report any partial teardown as failure.

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
- Fixed `--cleanup` to independently attempt host-API and compose cleanup, verify both postconditions, and aggregate failures rather than stranding one owned component when the other cleanup leg fails.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, a dedicated read-only lifecycle dashboard, and `docs/runbooks/lifecycle-safety.md` linked from that dashboard.

## Latest run — 2026-09-20 — make owned cleanup independent and failure-aggregating

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py`, its cleanup regression tests, and the local API lifecycle in `scripts/demo_local.py`. The previous cleanup implementation correctly verified both the host API and compose postconditions, but returned immediately when the API remained reachable. That meant a wedged host API could strand simulator/Prometheus/Grafana containers even though the rehearsal had already proved those compose resources were created and owned by this run.

### Exact changes made

- Reworked `_cleanup_owned_runtime()` so API cleanup and compose cleanup are independent legs once rehearsal ownership is established.
- API stop exceptions and an API that remains reachable are recorded as cleanup failures but no longer prevent teardown of the rehearsal-owned compose project.
- Compose teardown failure no longer prevents the bounded compose postcondition check; surviving resources are reported separately.
- Cleanup aggregates all observed failures into one `EvidenceGateError`, preserving fail-closed acceptance while maximizing safe teardown.
- Extended `runtime/tests/test_validation_demo_release_cleanup.py` for successful ordering, API-survival continuation, API-stop-exception continuation, compose-down-failure verification, and surviving compose resources.
- Implementation commit: `6892c7400fb5117a2df2d9ca42ad6466d848665c`.
- Regression-test commit: `e495b6ca9dfead990e32b38a48cf921bc246c45c`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the source and regression-test updates.
- Static review confirms that a failed API cleanup cannot suppress compose teardown, and a failed compose teardown cannot suppress compose postcondition verification.
- Pre-run ownership safety is unchanged: cleanup only runs when `stack_owned` is true, after the empty-project preflight and fresh-stack boundary.
- This repository connector does not expose an executable checkout, so the updated unit tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. Once ownership is established, cleanup should be best-effort across independent resources but fail closed in its final result.
2. A cleanup error is evidence to aggregate, not a reason to abandon safe cleanup of another resource owned by the same rehearsal.
3. Preserve the project-scoped compose ownership model; do not inspect or terminate unrelated host resources.
4. Preserve the no-port-killing rule and the existing refusal to touch any pre-existing StageGuard compose project.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- `demo_local._spawn_api()` can still leave a process-management edge case if a newly spawned API never becomes healthy; this should be exercised in an executable checkout before changing PID handling speculatively.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix concrete failures, then run `python scripts/demo_release.py --non-interactive --cleanup` from an empty compose project and verify both cleanup legs under injected failure (including an API-stop failure) without leaving compose resources. Also verify a stopped pre-existing StageGuard compose container is refused without destruction. After those gates pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution over additional speculative hardening.
