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
- Timeline display strings reject C0/C1 controls, DEL, Unicode line/paragraph separators, the complete Unicode `Cf` format-control category, and Unicode `Cs` surrogate code points.
- Timeline policy iterators and Mapping access are treated as untrusted extension/persistence behavior; ordinary read failures fail closed without partial disclosure.
- Static timeline projection reads each allowlisted Mapping value exactly once, avoiding membership/read TOCTOU behavior from custom persistence adapters.
- An absent static timeline policy may delegate to the canonical reconciliation projector; an explicitly configured null/malformed policy never does and fails closed.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — explicit-null timeline policy fail-closed semantics

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/timeline_projection.py`, `runtime/tests/test_timeline_projection.py`, the runtime directory, and searched the repository for TODO markers. The timeline policy lookup used `Mapping.get(event_type)` with the default `None`, making an absent policy entry indistinguishable from an explicitly configured null entry. For canonical reconciliation event names, an explicit null policy therefore fell through to reconciliation projection instead of being treated as malformed configuration.

### Changes / actions

- Changed timeline policy lookup to use the private `_MISSING` sentinel, distinguishing absence from an explicit null entry.
- Only a genuinely absent static policy entry may now delegate to canonical reconciliation projection.
- Explicit `None` policy entries fail closed before payload projection; valid empty iterables remain an intentional disclose-nothing policy.
- Added `runtime/tests/test_timeline_policy_presence.py` covering absent-policy reconciliation projection, explicit-null fail-closed behavior, and explicit-empty disclose-nothing behavior.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- Implementation committed as `58d36cc90070655aa3a133490dbb2dd1c60150cb`.
- Regression coverage committed as `ca396259fe570aa8075c27e0c5a01ae5d5f99bf1`.
- This connector runner does not expose an executable checkout, so the new regressions were not executed and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Treat policy absence and policy corruption as different states: absence permits the narrow built-in reconciliation projection; explicit malformed configuration must fail closed.
2. Preserve an empty iterable as a valid explicit policy because it provides a useful intentional disclose-nothing override.
3. Keep the reconciliation fallback canonical and independent of arbitrary payload metadata.

### Blockers / unknowns

- Latest timeline projection/public-audit/execution-safety and MCP smoke/launcher/negotiation/compose tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the consolidated MCP smoke/launcher tests plus focused timeline/public-audit/execution-safety suites in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
