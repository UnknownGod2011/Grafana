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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities, strictly validated provider result contracts, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — canonical production/uplink allowlist identities

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py` and `runtime/tests/test_validation_remediation_policy_config.py`. The previous run correctly rejected non-string and blank allowlist values, but still accepted identities with surrounding whitespace, embedded control characters, and unbounded length. Those values become provider request fields, so accepting them created avoidable ambiguity and log/protocol abuse surface at the production mutation boundary.

### Changes / actions

- Added `_valid_allowlist_identity` to require exact strings of 1-128 characters.
- Reject leading/trailing whitespace rather than silently canonicalizing it, so deployment typos fail closed instead of changing identity semantics.
- Reject C0 controls and DEL anywhere in production/uplink identities before any remediation transport can be reached.
- Added regression coverage for empty/non-string identities, surrounding whitespace, newline/tab/carriage-return/DEL injection, 129-character oversized values, and valid 128-character boundary values.
- Kept the regression inside the existing validation-owned test module; no CI workflow was added or triggered deliberately.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `34edd59413958ad550d1b2f4c4af3b5a87128a2c`.
- Regression committed as `76691d84f22cde129863e11c26f0111092af3771`.
- Static inspection confirms malformed deployment identities now fail during client construction, before provider transport is reachable.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Production/uplink allowlist values are security-sensitive protocol identities, not arbitrary display strings.
2. Identity configuration is not silently trimmed: an operator typo should be explicit and fail closed.
3. A 128-character ceiling is ample for deployment identifiers while bounding provider/log payloads.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
