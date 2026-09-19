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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at both configuration and runtime boundaries, callable provider transports, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — symmetric malformed runtime target regression

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, `runtime/production_remediation.py`, `runtime/tests/test_production_remediation.py`, and `runtime/tests/test_validation_remediation_boundary.py`. The runtime implementation validates both production and uplink identities through the same canonical trust boundary, while the malformed-string regression exercised only the production-ID position.

### Changes / actions

- Expanded the validation-owned runtime-target regression so every malformed canonical-string case is exercised independently in both `production_id` and `uplink` positions.
- Covered empty strings, leading/trailing whitespace, embedded control characters, and overlength identities symmetrically.
- Strengthened each case to assert the rejection detail, zero provider attempts, preservation of the already-valid bounded operation ID as correlation metadata, and no transport contact.
- Kept the hostile-object regression for both identity positions unchanged; its raising `__eq__` continues to prove validation occurs before equality comparison.
- No new test surface or workflow was created, and no credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Symmetric malformed-target regression committed as `cbf0ec8ee99711ad56ddbc2235e3d97d04d3fbc5`.
- Static inspection confirms both runtime target arguments pass through `_valid_allowlist_identity` before equality and before `transport.execute`.
- No green execution claim is made: this connector runner can modify and inspect repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Both runtime identity positions are treated as independent untrusted inputs even though they currently share one validator.
2. Provider non-contact remains an explicit safety assertion rather than an implementation assumption.
3. The regression stays in the existing consolidated remediation-boundary gate to avoid validation ownership drift and noisy CI expansion.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout, classify and fix every concrete failure without weakening credential isolation/no-replay semantics, then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
