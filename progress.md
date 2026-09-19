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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities, callable provider transports, strictly validated execution/reconciliation result contracts, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — retry scheduling fail-closed hardening

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, its validation-owned policy tests, and `runtime/remediation.py` to confirm the `ActionResult` contract. The production adapter correctly bounded retryable provider results but invoked the injected sleep/scheduler hook outside the governed exception boundary. A scheduler fault could therefore escape the incident-command path after the first provider call rather than returning a controlled failed action.

### Changes / actions

- Wrapped the inter-attempt sleep hook in the production remediation fail-closed boundary.
- A sleep/scheduler exception now returns a rejected `ActionResult` with StageGuard-owned metadata from the first provider attempt and never performs a second provider mutation attempt.
- Added a regression using a retryable `503` transport and a throwing sleep hook; it asserts exactly one provider call, rejected action state, attempt count `1`, retained bounded status `503`, and generic operator detail.
- Inspected the canonical `ActionResult` dataclass and corrected the new regression to assert its actual `accepted` field rather than a nonexistent `success` alias.
- No CI workflow was added or triggered deliberately; no credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `da93377200f353e7974283f97208f400bf5c3a8c`.
- Regression coverage committed as `c386f3d5d4dcf0b4957988c0c5284eeda2821f4c`, with the contract assertion correction in `5b7091fa368d640d503c4dc10951f014910d6d9b`.
- Static inspection confirms a retry scheduling fault cannot escape the production remediation boundary or cause a second transport execution.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Retry scheduling is part of the mutation boundary: failure between attempts must fail closed rather than escape or proceed to another provider call.
2. The adapter retains only StageGuard-owned bounded metadata from the completed attempt; scheduler exception text is not exposed.
3. No-replay safety takes precedence over exhausting configured retries when local retry machinery itself is unreliable.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
