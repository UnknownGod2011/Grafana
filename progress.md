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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — Cloud audit filter injection hardening

### Inspected at start

Read `progress.md` completely first. Inspected the consolidated validation runner, runtime test inventory, `test_anchored_cloud_audit_reader.py`, `test_durable_audit_reader.py`, and `runtime/durable_audit_reader.py`. The audit reader already bounded filter literals and escaped quotes/backslashes, but raw C0/DEL control characters could still enter Cloud Logging filter text. The existing public-audit validation wildcard already owns audit tests, including the new security regression, so no new validation gate was necessary.

### Changes / actions

- Hardened `_literal()` in `runtime/durable_audit_reader.py` to reject C0 ASCII control characters and DEL before constructing Cloud Logging filter text.
- Kept quote and backslash escaping for legitimate bounded identifiers.
- Added `runtime/tests/test_audit_filter_security.py` covering quote/backslash containment, newline/carriage-return/tab/NUL/US/DEL rejection, no-query-on-rejection, and hostile logger-name rejection.
- Did not broaden live-cloud behavior or instantiate Google Cloud clients; tests use a local fake logger.
- No credentials, cloud resources, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Audit reader hardening committed as `df312ee6bcbe69134d91d0b5bc395a588188ba56`.
- Security regression committed as `445c50544299555891558fc258207532b7b6abfa`.
- Static inspection confirms rejection happens before `list_entries`, while quotes/backslashes remain escaped inside a single incident literal.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Reject control characters instead of normalizing them: audit incident/log identifiers are security-sensitive filter operands, not free-form presentation text.
2. Preserve ordinary spaces and Unicode while rejecting only raw C0/DEL controls, minimizing compatibility impact.
3. Reuse the existing `public audit` validation ownership rather than adding another overlapping gate.
4. Keep live Google Cloud acceptance explicitly separate from deterministic fake-logger regression tests.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially fake-cloud restart, GCS/cloud-storage, simulator, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify the fake-cloud restart and GCS/cloud-storage durability tests. Admit only in-memory/fake-storage contracts to dependency-light production validation, while keeping anything that can instantiate authenticated Google Cloud clients behind an explicit live acceptance path.
