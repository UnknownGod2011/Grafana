# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Production remediation accepts only canonical operation IDs and strictly validated provider result contracts; malformed operation identity types fail closed before transport and are not reflected into action metadata.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — production remediation identity type boundary

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, `runtime/tests/test_production_remediation.py`, and the consolidated validation runner. The canonical operation-ID regex correctly rejected malformed strings, but calling it with a non-string value raised `TypeError`. Because Python annotations are not runtime enforcement, an API/integration bug could therefore crash execution or reconciliation before the intended fail-closed boundary. Invalid caller objects were also reflected into action metadata on rejection, creating an avoidable serialization/trust-boundary hazard.

### Changes / actions

- Changed `_valid_operation_id` to accept `object` and require exact `str` type before regex matching.
- Invalid non-string operation IDs now fail closed before mutation transport and reconciliation transport calls.
- Rejected invalid operation identities are no longer reflected into `ActionResult.metadata`; the metadata identity is the safe empty-string sentinel.
- Applied the same no-reflection behavior when both the target and operation identity are invalid.
- Added `test_validation_remediation_identity_types.py` covering `None`, integers, booleans, bytes, lists, and dictionaries for execution/reconciliation plus the wrong-target path.
- Ensured the new regression is owned by the existing `test_validation_*.py` consolidated validation gate; removed the temporary unowned filename so `--require-full-coverage` is not weakened.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runtime type hardening committed as `3c212224ee992077a2f27f3fe35bf145cc7d4a81` and invalid-identity metadata hardening as `2c9fd2a8ade2a38e14ed6c365db0d8489ed28741`.
- Regression was added under validation ownership in `da0106e52c70b9420baea826bdde11f9760a49a9`; the temporary unowned duplicate was removed in `092252615219f971d54358e77f93a712c1036df8`.
- Static inspection confirms non-string identities cannot reach the provider mutation/reconciliation methods and cannot be propagated into action metadata.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. External operation identity is runtime-untrusted even when Python signatures annotate it as `str`.
2. Rejection metadata should contain only canonicalized/bounded values, not arbitrary caller objects.
3. New safe runtime regressions must preserve full validation ownership immediately rather than waiting for a later coverage repair.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
