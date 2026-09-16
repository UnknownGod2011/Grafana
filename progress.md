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

## Latest run — 2026-09-17 — consolidated local validation gate

### Inspected at start

Read `progress.md` completely first, then inspected the current README, timeline projection implementation and policy-presence regression, plus the runtime test inventory. The highest-value unblocked item was to turn the repeatedly documented focused-validation next step into a reproducible local command without using CI or credentials.

### Changes / actions

- Added `scripts/run_stageguard_validation.py`, a dependency-light consolidated validation runner.
- The runner executes four separately attributed unittest gates: timeline disclosure (`test_timeline*.py`), public audit (`test_*audit*.py`), execution safety (`test_*execution*.py`), and Grafana MCP (`test_*mcp*.py`).
- Gates run in separate Python processes so a failure is assigned to a boundary instead of being buried in one monolithic test invocation.
- Default behavior fails fast; `--keep-going` collects all failing gates and `--list` exposes the selected patterns without running tests.
- The runner deliberately does not start Docker, contact Grafana, read credentials, or trigger GitHub Actions. Live MCP smoke remains a distinct acceptance gate.
- Removed unittest's explicit top-level-directory argument after review so discovery does not require `runtime/tests` to be an importable package; execution from repository root still makes `runtime` imports available.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- Initial runner creation committed as `7d8a0f7766accbb6a3823f7ba8cd0e87c860f4a4`.
- Discovery-layout correction committed as `b0fd4ded477de251dc596202fb37a6ea06d2b5f2`.
- This connector runner still does not expose an executable repository checkout, so the new command itself and selected test gates were not executed; no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Make the safety/MCP validation baseline a checked-in executable command rather than relying on an operator to reconstruct several unittest invocations from prose.
2. Keep live Docker/Grafana checks outside the dependency-light runner so ordinary development validation remains free, deterministic, and credentialless.
3. Preserve separate process boundaries for each gate to improve failure classification and reduce ambiguity when historical failures are revisited.

### Blockers / unknowns

- The consolidated runner and latest connector-authored tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --keep-going`. Fix any selected-gate failures first; if all gates pass, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
