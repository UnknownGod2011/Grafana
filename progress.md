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
- Timeline event identifiers are non-empty, terminal-safe strings bounded to 160 characters before policy lookup or reconciliation parsing.
- Static timeline values are bounded JSON scalars and terminal-safe; nested values, oversized strings, non-finite floats, and unbounded integers fail closed.
- Static timeline field policy itself is bounded to 64 unique, non-empty, terminal-safe string keys of at most 128 characters; malformed, duplicate, oversized, string-as-iterable, and non-terminating allowlists fail closed.
- Timeline display strings reject C0/C1 controls, DEL, Unicode line/paragraph separators, the complete Unicode `Cf` format-control category, and Unicode `Cs` surrogate code points. This prevents invisible presentation manipulation and invalid UTF-8 response text while retaining ordinary printable international text, combining marks, and emoji.
- Timeline policy iterators and Mapping access are treated as untrusted extension/persistence behavior; ordinary read failures fail closed without partial disclosure.
- Static timeline projection reads each allowlisted Mapping value exactly once, avoiding membership/read TOCTOU behavior from custom persistence adapters.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — Unicode surrogate timeline hardening

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/timeline_projection.py` and `runtime/tests/test_timeline_projection.py`. The central display validator rejected controls and Unicode format characters but still accepted Unicode surrogate code points (`Cs`). Python strings can contain lone surrogates, while normal UTF-8 encoding rejects them; allowing one into an operator timeline could therefore turn malformed durable/plugin data into a JSON/HTTP response-encoding failure.

### Changes / actions

- Hardened `_safe_display_string()` to reject the complete Unicode `Cs` surrogate category in addition to the existing `Cf` and line/control restrictions.
- Kept the policy centralized so the protection applies to event identifiers, reconciliation identifiers, static field names, and allowlisted string values.
- Added regressions for lone high-surrogate injection across reconciliation event types, ordinary event identifiers, static field names, and static values.
- Preserved printable international Unicode, combining marks, and ordinary emoji.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- Implementation committed as `39830ff0323c61c223f4d3517b509378ba951066`.
- Regression tests committed as `00b469ac5a145d18140c2bbb7e12654636f90d4e`.
- This connector runner does not expose an executable checkout, so the regressions were not executed and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Reject surrogate code points at the operator-display boundary instead of relying on downstream JSON/HTTP encoders to fail unpredictably.
2. Use Unicode general category `Cs`, covering both high and low surrogate ranges without maintaining code-point lists.
3. Preserve valid non-ASCII operator text; this remains a Unicode-safe rather than ASCII-only boundary.

### Blockers / unknowns

- Latest timeline projection/public-audit/execution-safety and MCP smoke/launcher/negotiation/compose tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the consolidated MCP smoke/launcher tests plus focused timeline/public-audit/execution-safety suites in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
