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

## Latest run — 2026-09-19 — remediation transport/reconciliation contract hardening

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py` and `runtime/tests/test_validation_remediation_policy_config.py`. The production client validated execution results but did not validate at construction time that the injected transport exposed a callable `execute` method. More importantly, `reconcile_operation` accepted an untyped provider return and performed set membership outside its exception boundary; unhashable malformed states such as a list or dictionary could therefore raise `TypeError` through the incident reconciliation path.

### Changes / actions

- Production remediation construction now requires the transport to expose a callable `execute` method, failing before any incident can reach a misconfigured provider adapter.
- Reconciliation now requires an exact string result before checking the two allowed states (`accepted`, `not_found`). Non-string, malformed, differently cased, or control-suffixed states fail closed to `unknown`.
- Added validation-owned regressions for missing/non-callable execute transports and malformed reconciliation states including `None`, bool/int, list, dict, bytes, wrong case, and newline-suffixed strings.
- Added positive reconciliation checks for both canonical states.
- No CI workflow was added or triggered deliberately; no credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `351cda63d3fdf4fd413b59bdc70b2099c16ba411`.
- Regression coverage committed as `0a46770fbf4a3f9e69e51ad9ae02cf619bf2a78b`.
- Static inspection confirms unhashable provider reconciliation values can no longer escape the fail-closed reconciliation boundary.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Provider adapters are runtime trust boundaries; Python Protocol/type annotations alone are not sufficient validation.
2. Reconciliation is intentionally a tiny exact-value protocol. Unknown or malformed provider states must never advance execution state.
3. Construction-time validation is preferable for structural transport misconfiguration, while provider runtime faults continue to fail closed during execution/reconciliation.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership; once green, continue product-facing production hardening from that trustworthy baseline.
