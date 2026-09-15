# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's supported MCP deployment is stdio-only and its compose evidence surface is restricted to `datasource,prometheus,loki` with writes and proxied tools disabled.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery.
- `recovery_unverified` can only use the recovery-only verification path and cannot replay provider remediation.
- Any remediation side effect followed by ambiguous checkpoint persistence remains behind the execution-uncertainty barrier, including local/non-reconciling adapters and process restarts during reconciliation.
- Execution uncertainty is resolved only through durable reload/reconciliation and fresh Grafana evidence; `/v1/execute` is never the recovery mechanism.
- Production adapters that support provider reconciliation must additionally resolve their server-owned operation ID before fresh evidence can release uncertainty.
- Durable checkpoint/audit failures fail closed; ambiguous provider execution blocks replay.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Metric/Loki activation remains policy-owned and versioned; callers cannot supply arbitrary Grafana queries or datasource identities through the HTTP API.
- Operator timeline disclosure is allowlist-based. Canonical remediation reconciliation may expose only bounded `result` and `reason`; operation IDs, provider bodies, targets, credentials, arbitrary audit metadata, and raw actor identities must never be exposed.
- Reconciliation timeline parsing rejects oversized durable event names before splitting/parsing them.
- Static timeline fields expose only bounded JSON scalars; nested objects/arrays, oversized strings, arbitrary-precision integers outside signed 63-bit magnitude, and non-finite numbers fail closed even when their field name is allowlisted.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.
- An earlier `runtime/timeline_projection.py` revision was independently syntax-compiled and exercised in an isolated local smoke on 2026-09-15. The latest scalar/integer hardening has not yet received repository-level execution.

## Run log — 2026-09-16 — Grafana MCP evidence-surface contract

### Inspected at start

Read `progress.md` completely first. Inspected the current repository tree, `docker-compose.yml`, `runtime/mcp_smoke.py`, `runtime/tests/test_observability_image_pins.py`, and the existing Grafana MCP security document. Confirmed the compose MCP service is pinned to `grafana/mcp-grafana:1.4.1`, stdio-only, `--disable-write`, `--disable-proxied`, and explicitly limited to `datasource,prometheus,loki`.

### Changes / actions

- Re-checked current official Grafana MCP documentation for tool gating and read-only semantics.
- Confirmed upstream documents `--disable-write` as the global write-tool gate and `--enabled-tools` as a replacement for the default category list. Upstream also documents that raw SQL query tools are removed under `--disable-write` unless deliberately restored with `--enable-query`.
- Strengthened `runtime/tests/test_observability_image_pins.py` with a credential-free compose contract that locks the StageGuard MCP transport to stdio, locks the enabled categories to `datasource,prometheus,loki`, requires `--disable-write` and `--disable-proxied`, rejects `--enable-query`, and guards against accidental network-transport widening.
- The contract also names high-risk/unneeded categories so future compose expansion is an explicit reviewed change rather than a silent capability increase.
- Attempted a fresh executable checkout before editing; the runner still failed DNS resolution for `github.com`, so no repository pytest execution was possible.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub repository reads and connector write succeeded.
- Fresh `git clone` attempt failed before checkout with `Could not resolve host: github.com`; this is treated as a transient runner/network blocker, not a project failure.
- Current official Grafana docs support the compose policy: `--disable-write` disables writes and `--enabled-tools` replaces the default category set; `--enable-query` is intentionally absent from StageGuard.
- No green pytest claim is made for the newly committed contract because repository execution remains unavailable.
- No GitHub Actions workflow was created or triggered.

### Decisions

1. Make the narrow MCP capability set executable policy, not documentation alone: compose changes that widen transport or tool categories should break a local unit test.
2. Keep `--disable-write` even with a least-privilege Grafana identity; process-level capability gating and Grafana RBAC are independent defense layers.
3. Keep `--enable-query` forbidden. StageGuard needs Prometheus/Loki evidence queries, not raw SQL query restoration.
4. Continue to treat `datasource,prometheus,loki` as the complete supported MCP category surface until a concrete production requirement justifies expansion.

### Blockers / unknowns

- The latest timeline scalar/integer hardening, public `audit_timeline()` reconciliation tests, and new MCP compose contract still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime/tests/test_observability_image_pins.py`, the focused timeline projection/public audit tests, and execution-safety reconciliation suite in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only smoke, then classify the historical full-suite failures.
