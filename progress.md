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
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — fail-closed production remediation transport boundary

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py` and its focused regression suite. The adapter treated expected timeout/OS failures as bounded retryable failures, but an unexpected provider SDK exception or a malformed adapter return could escape as an exception/attribute error and crash the incident command path. Retrying an unknown/malformed mutation result would also be unsafe because the provider may already have performed the write.

### Changes / actions

- Hardened `AllowlistedProductionRemediationClient.recover_uplink_idempotent` so unexpected transport exceptions fail closed as a rejected `ActionResult` rather than escaping across the incident-command boundary.
- Unexpected exceptions are deliberately non-retryable: after a consequential provider call, execution state is uncertain and StageGuard must not issue another write merely because its adapter failed unexpectedly.
- Added strict `TransportResult` runtime validation. Malformed provider-adapter responses fail closed and do not retry.
- Preserved the existing bounded retry behavior for explicit `TimeoutError`/`OSError` cases and explicit typed `retryable=True` results.
- Added regressions proving both an unexpected provider exception and a malformed transport response produce one provider call only, a rejected action result, and no retry despite `max_attempts=3`.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Boundary hardening committed as `411df170fd85fff9b087ff1131111d87331b7a6a`.
- Regression coverage committed as `ff3979f423612315926e8860d6ab33a6f16cb162`.
- Static inspection confirms explicit retryable results retain the existing retry path while unknown adapter failures terminate after the first attempted mutation.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Unexpected exceptions after a production mutation attempt represent execution uncertainty, not a safe retry signal.
2. Provider adapters must return the exact bounded `TransportResult` contract; duck-typed or malformed responses are rejected at the trust boundary.
3. Failure detail remains generic so provider SDK exception text cannot leak credentials or sensitive backend detail into operator-visible state.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
