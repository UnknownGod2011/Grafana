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
- Production remediation accepts only canonical operation IDs and strictly validated provider result contracts; ambiguous provider results never trigger replay.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — strict production remediation result contract

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py` and `runtime/tests/test_production_remediation.py`. The previous run correctly rejected non-`TransportResult` objects, but Python dataclass annotations do not enforce field types. A provider adapter could therefore return a nominal `TransportResult` with truthy integers/strings, boolean status codes, out-of-range HTTP status codes, or contradictory `accepted=True, retryable=True` state and cross the mutation trust boundary.

### Changes / actions

- Added `_valid_transport_result` as an explicit runtime contract validator for the provider boundary.
- Require exact `bool` types for `accepted` and `retryable`; this intentionally rejects integers because Python `bool` subclasses `int`.
- Require `status_code` to be `None` or an exact integer in the HTTP status range 100-599.
- Reject contradictory accepted-and-retryable results rather than treating them as successful mutation acknowledgements.
- Preserve the no-replay invariant: every malformed or contradictory result fails closed after exactly one provider call, with no retry even when `max_attempts=3`.
- Expanded the focused regression to cover a dict response, integer accepted flag, boolean status, low/high invalid status, string retry flag, and accepted+retryable contradiction.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runtime contract hardening committed as `799cb7f74fd01ebdaff4716959bd4c2df1cfcb64`.
- Regression expansion committed as `31cd6dfe56f3c53e2aa98397bd57ed491c09de2b`.
- Static inspection confirms malformed result metadata does not propagate an untrusted status code and no malformed-result path reaches retry/sleep.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Type annotations are documentation, not validation, at an external provider trust boundary.
2. Contradictory provider acknowledgements are execution uncertainty and must not be normalized into success.
3. HTTP status metadata is bounded before it enters StageGuard action state.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
