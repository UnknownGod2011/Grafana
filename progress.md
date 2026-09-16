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
- Static timeline field policy itself is bounded to 64 string keys; malformed, oversized, string-as-iterable, and non-terminating allowlists fail closed before projection.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-16 — Bounded timeline policy iteration

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/timeline_projection.py` and `runtime/tests/test_timeline_projection.py`. Scalar values were bounded, but the static-field policy iterable itself had no width/termination bound. A malformed extension could therefore supply an oversized or infinite iterator and keep an operator timeline request iterating indefinitely.

### Changes / actions

- Added `_MAX_STATIC_FIELDS = 64` and `_bounded_static_fields()`.
- Materialize at most 65 policy entries with `itertools.islice`; fail closed above the 64-field contract.
- Reject strings/bytes as accidental field iterables and reject any non-string field entry.
- Preserve exact-limit behavior and existing scalar/display/reconciliation disclosure rules.
- Added regressions for string allowlists, mixed-type allowlists, 65-field allowlists, infinite generators, and the exact 64-field boundary.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub source update succeeded: `33fbdab12347de47fe40e126f5af4c87e1f6109b`.
- Regression-test update succeeded: `68dd9f5335b17dfd071335ed001b3e7c49b89796`.
- This runner does not expose an executable checkout, so the new tests were not run and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Treat disclosure policy configuration as a trust boundary too, even though normal production callers use static in-process policy.
2. Bound iteration rather than merely checking collection length so generators and non-terminating iterables cannot hang projection.
3. Fail closed for malformed policy instead of partially projecting fields from it.

### Blockers / unknowns

- Latest timeline projection/public-audit/execution-safety and MCP smoke/launcher/negotiation/compose tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the consolidated MCP smoke/launcher tests plus focused timeline/public-audit/execution-safety suites in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
