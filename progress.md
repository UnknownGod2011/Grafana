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
- Production remediation accepts only canonical operation IDs, strictly validated provider result contracts, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — production remediation policy configuration boundary

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, its primary production-remediation tests, and the prior operation-identity regression. The execution/result boundary was strongly runtime-validated, but constructor policy values still relied on Python annotation/coercion behavior: non-string allowlist identities could crash on `.strip()`, `bool` could be accepted as an integer attempt count or numeric timeout/delay, and non-finite floats such as `NaN` could bypass range comparisons.

### Changes / actions

- Added a finite bounded-number validator that accepts only exact `int`/`float` values, excludes `bool`, rejects NaN/infinity, and enforces the existing timeout/delay bounds.
- Made allowlisted production/uplink configuration require exact, non-empty strings before any `.strip()` call.
- Made `max_attempts` require an exact integer in `{1,2,3}`, closing Python's `True == 1` coercion path.
- Made the injected sleep hook explicitly callable at construction time.
- Added `runtime/tests/test_validation_remediation_policy_config.py` covering malformed allowlist types, blank strings, bool/non-finite/string numeric policy values, valid boundary values, and a non-callable sleep hook.
- Kept the regression under the existing `test_validation_*.py` validation ownership convention.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `63730a2ff42ef5d21652cb136e598408496a533c`.
- Regression committed as `04b77267b3e8c126c1ed258275bec509956c04cf`.
- Static inspection confirms malformed constructor policy cannot progress to remediation transport and finite valid boundary values preserve the documented policy range.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Deployment-derived remediation policy is runtime-untrusted even when constructors carry Python type annotations.
2. Security-sensitive numeric policy must reject booleans and non-finite floats explicitly rather than relying on comparison semantics.
3. Validation hooks should fail at construction rather than producing a later partial-remediation-path runtime fault.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
