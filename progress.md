# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Supported MCP deployment is stdio-only; compose exposes only the required read-only datasource/Prometheus/Loki evidence surface.
- MCP launcher configuration, peer metadata, diagnostics, and smoke configuration are bounded, terminal-safe, and credential-redacted before operator display.
- Direct official `grafana/mcp-grafana` Docker launches, including recognized Docker Hub aliases, must explicitly use stdio.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Durable checkpoint/audit failures fail closed; provider operation reconciliation is required where supported.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Metric/Loki activation is policy-owned and versioned; HTTP callers cannot supply arbitrary Grafana queries or datasource identities.
- Operator timeline disclosure is allowlist-based. Reconciliation exposes only canonical bounded `result` and `reason`; provider bodies, operation IDs, targets, credentials, arbitrary metadata, and raw actor identities remain private.
- Static timeline values are bounded JSON scalars and terminal-safe; nested values, oversized strings, non-finite floats, and unbounded integers fail closed.
- Static timeline field policy itself is bounded to 64 string keys; malformed, oversized, string-as-iterable, and non-terminating allowlists fail closed.
- Static timeline field policy iterator failures fail closed; malformed plugin/configuration iterators cannot surface partial disclosure or operator-facing 500s.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-16 — Fail-closed policy iterator handling

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/timeline_projection.py` and `runtime/tests/test_timeline_projection.py`. The static-field policy was bounded, but exceptions raised while materializing a plugin/configuration iterable were only partially covered (`TypeError`/`ValueError`). A malformed iterator could still raise another runtime exception during operator timeline projection.

### Changes / actions

- Hardened `_bounded_static_fields()` to catch any ordinary `Exception` from `iter()`/bounded materialization and return `None`.
- Preserved `BaseException` semantics so process-control signals are not swallowed.
- Added a regression with an iterator whose `__iter__` raises `RuntimeError`; projection fails closed with no disclosure.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub source update succeeded: `4435d56b92454c03fa12ad63c3b814b18f97d6ac`.
- Regression-test update succeeded: `9e7b9e11bcd8ab5258101f6816e59fa0327f8ce5`.
- This runner does not expose an executable checkout, so the new test was not run and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Treat policy iterator execution as untrusted extension/configuration behavior.
2. Fail closed on ordinary iterator failures rather than expose partial fields or convert malformed policy into a public server error.
3. Do not catch `BaseException`, preserving cancellation and process-level control semantics.

### Blockers / unknowns

- Latest timeline projection/public-audit/execution-safety and MCP smoke/launcher/negotiation/compose tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the consolidated MCP smoke/launcher tests plus focused timeline/public-audit/execution-safety suites in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
