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
- Timeline policy iterators and Mapping access are treated as untrusted extension/persistence behavior; ordinary read failures fail closed without partial disclosure.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-16 — Fail-closed timeline Mapping access

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/timeline_projection.py` and `runtime/tests/test_timeline_projection.py`. Iterator materialization already failed closed, but custom `Mapping` implementations could still raise ordinary runtime exceptions from policy lookup, payload membership/index access, or reconciliation `.get()` calls and turn an operator timeline request into a server error.

### Changes / actions

- Hardened reconciliation payload reads so ordinary custom-Mapping failures return an empty projection.
- Hardened static policy Mapping lookup and allowlisted payload reads with the same fail-closed boundary.
- Preserved `BaseException` semantics by catching only ordinary `Exception`.
- Added a reusable broken Mapping fixture and regressions for reconciliation reads, policy lookup failures, and static payload read failures.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- Implementation update committed as `b77f55f8cb23191d2ffaa512c9a6c9456b887dd9`.
- Regression-test update committed as `b7782ad2575f9642c7e749bcbf65ffa8be187d46`.
- This runner does not expose an executable checkout, so the new tests were not run and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Treat both durable payload Mapping access and extension/configuration policy Mapping access as untrusted boundaries.
2. Fail closed on ordinary read failures rather than emit partial disclosure or operator-facing 500s.
3. Continue not catching `BaseException`, preserving cancellation/process-control behavior.

### Blockers / unknowns

- Latest timeline projection/public-audit/execution-safety and MCP smoke/launcher/negotiation/compose tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the consolidated MCP smoke/launcher tests plus focused timeline/public-audit/execution-safety suites in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
