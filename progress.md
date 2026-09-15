# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's supported MCP deployment is stdio-only. Upstream network transports are not enabled merely because upstream supports them.
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

## Run log — 2026-09-15 — Grafana MCP production security review

### Inspected at start

Read `progress.md` completely first. Inspected the current `README.md`, `runtime/timeline_projection.py`, `runtime/incident_service.py`, and runtime test inventory. Confirmed the repository still intentionally treats Grafana MCP as a read-only evidence boundary and uses stdio-only launchers.

### Changes / actions

- Researched current official Grafana MCP documentation for server capabilities, transports, Docker setup, RBAC, and caller authentication.
- Added `docs/GRAFANA_MCP_SECURITY.md` with an explicit production threat boundary, credential isolation rules, least-privilege guidance, read-only evidence policy, transport policy, production checklist, and dated upstream references.
- Recorded that upstream now documents `--server-auth-token` / `MCP_GRAFANA_SERVER_TOKEN` for authenticating network-transport callers. StageGuard deliberately remains stdio-only because it does not need a remotely callable MCP service and should not add an unnecessary network trust boundary.
- Documented minimum requirements if remote MCP ever becomes an explicit future StageGuard mode: caller auth, network policy, TLS when appropriate, least-privilege Grafana RBAC, fixed query/tool policy, bounded timeouts, and negative authentication tests.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub repository inspection and connector writes succeeded.
- Current official Grafana docs confirm stdio remains supported and document authenticated SSE/Streamable HTTP options; this does not change StageGuard's narrower supported policy.
- No repository pytest execution was available in this connector-only run, and no green test claim is made.
- No GitHub Actions workflow was created or triggered.

### Decisions

1. Keep StageGuard's production MCP path stdio-only despite upstream adding/clarifying authenticated network transports; fewer exposed services is the safer architecture for this use case.
2. Treat upstream tool availability as capability, not StageGuard authorization: runtime queries remain policy-owned and remediation remains outside Grafana MCP.
3. Require a dedicated least-privilege Grafana identity and independent credential rotation; remediation credentials must never enter the MCP process environment.
4. Preserve the pinned-release live-smoke requirement before calling the current MCP integration production-validated.

### Blockers / unknowns

- The latest timeline scalar/integer hardening and public `audit_timeline()` reconciliation tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the focused timeline projection/public audit tests plus execution-safety reconciliation suite in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only smoke using the newly documented least-privilege/stdio boundary, then classify the historical full-suite failures.