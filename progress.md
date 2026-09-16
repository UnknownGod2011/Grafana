# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's supported MCP deployment is stdio-only and its compose evidence surface is restricted to `datasource,prometheus,loki` with writes and proxied tools disabled.
- MCP launcher overrides are bounded before subprocess creation: raw command length, argv count, individual argument length, terminal/control characters, Unicode line separators, and bidi formatting controls fail closed outside the supported contract while printable Unicode paths remain valid.
- Direct official `grafana/mcp-grafana` Docker launches, including explicit Docker Hub registry aliases, must opt into stdio; registry qualification cannot bypass the transport boundary.
- The Grafana MCP release smoke must negotiate the exact configured MCP protocol and return structurally valid, bounded server identity/capabilities before StageGuard trusts its advertised tool surface.
- MCP peer-advertised tool names are untrusted input and must be non-empty, bounded, and free of ASCII control/DEL characters before they are stored, compared, or rendered in release evidence/errors.
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

## Run log — 2026-09-16 — Docker Hub MCP image-alias transport hardening

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/command_line.py` and `runtime/tests/test_command_line_bounds.py`. The existing direct-Docker safety check recognized `grafana/mcp-grafana[:tag|@digest]`, but explicit Docker Hub registry spellings such as `docker.io/grafana/mcp-grafana:1.4.1` were not recognized as the same official image. That allowed registry qualification to bypass the rule requiring the official image to opt into `-t stdio`.

### Changes / actions

- Hardened `_is_official_mcp_docker_image()` to normalize the Docker Hub aliases `docker.io/`, `index.docker.io/`, and `registry-1.docker.io/` before matching the official Grafana MCP repository.
- Kept matching case-insensitive and preserved tag/digest recognition.
- Deliberately do not treat arbitrary third-party registries containing a `grafana/mcp-grafana` path as the official image; StageGuard should not infer image provenance across unrelated registries.
- Added regression coverage proving all supported Docker Hub aliases fail closed without explicit stdio and succeed when `-t stdio` is present.
- Added a negative regression proving an unrelated registry namespace is not misidentified as the official image.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub connector repository inspection and source/test commits succeeded.
- This automation runner still does not expose a materialized executable checkout through the GitHub connector, so the new tests were not executed and no green pytest claim is made.
- No GitHub Actions workflow was created or triggered as a substitute for local validation.

### Decisions

1. Treat explicit Docker Hub registry aliases as semantically equivalent to the short official image name for transport enforcement.
2. Keep the provenance match intentionally narrow: only known Docker Hub aliases are normalized, avoiding false trust in lookalike repositories on arbitrary registries.
3. Preserve stdio as the only supported StageGuard MCP transport rather than relying on network-server authentication to compensate for an accidental transport change.

### Blockers / unknowns

- Latest launcher tests, MCP negotiation/metadata/tool-name/surface tests, MCP compose contract, timeline scalar/integer hardening, public `audit_timeline()` reconciliation tests, and execution-safety reconciliation suite still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime/tests/test_command_line_bounds.py`, `runtime/tests/test_mcp_smoke_contract.py`, `runtime/tests/test_observability_image_pins.py`, the focused timeline/public-audit tests, and execution-safety reconciliation suite in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.
