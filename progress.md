# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Prometheus sample timestamps must be finite JSON numbers; numeric-looking timestamp strings are rejected.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured MCP evidence work is bounded by collection cardinality and scalar sizes.
- JSON text evidence is size-gated before whole-string whitespace processing; decoder resource-guard failures and duplicate JSON object keys fail closed.
- Standard MCP content blocks are transport envelopes; only actual textual payloads can carry JSON evidence.
- Embedded resources admit evidence only through exact-string `resource.text`; URI-less `resource.data`, blob payloads, and arbitrary resource extensions are non-evidentiary.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline
- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest lifecycle/security hardening.
- Historical official Grafana MCP smoke: PASS on `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work
- Hardened lifecycle startup/cleanup, Docker timeouts, teardown verification, loopback publishing, and MCP container privileges/resources.
- Pinned Grafana `13.2.1` and official Grafana MCP `1.4.1`; release smoke verifies read-only tools and exact datasource UID.
- Added bounded semantic Prometheus evidence parsing with expected-label binding and strict sample-pair semantics.
- Added secret-aware MCP diagnostics with hostile-object protection, collision preservation, display-control escaping, credential redaction, strict output ceilings, exact truncation accounting, and metaclass-hook isolation.
- Restricted evidence traversal so warning/annotation/extension lookalikes and standard content-block `data` siblings cannot create false release acceptance.
- Hardened embedded MCP resources so only textual payloads can carry JSON evidence; blob/resource-link/extension fields cannot masquerade as telemetry.
- Removed the temporary URI-less `resource.data` compatibility path after inspecting the pinned official mcp-grafana v1.4.1 `QueryPrometheusResult` contract.
- Added explicit fail-closed collection/work and scalar-size ceilings.
- Hardened JSON-text evidence decoding so the 1 MiB ceiling precedes `strip()`, parser resource-guard failures fail closed, and duplicate object member names are rejected.

## Latest run — 2026-09-23 — duplicate-key JSON evidence hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and `runtime/tests/test_mcp_evidence_work_limits.py`. The JSON evidence decoder used Python `json.loads` default object semantics, which silently keep the last value for duplicate member names. At a security-sensitive evidence boundary this permits parser-differential ambiguity: another component can interpret the same transport differently while StageGuard accepts the last duplicate `data`, `metric`, or other structural key.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `879b0f3ec57a1f5e8ccabb5dfd3ead41db906a9f`.
- Added a strict `object_pairs_hook` that rejects any duplicate JSON object member name at every nesting level before semantic evidence validation.
- Duplicate-key rejection uses an internal `ValueError` subtype and therefore follows the existing fail-closed decoder path without exposing hostile material.
- Extended `runtime/tests/test_mcp_evidence_work_limits.py` in commit `d7317c61d9d9ce9be85c033d38ab744340954713` with regressions for duplicate top-level `data`, duplicate nested metric labels, and a positive unique-key control.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the implementation and regression-test commits.
- Static review confirms duplicate detection runs during JSON object construction, including nested objects, before evidence matching can accept a sample.
- This connector runtime does not expose an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for these connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. Ambiguous JSON is not acceptable as release evidence even if Python can deterministically choose one duplicate value.
2. Reject duplicates globally rather than only `data`/`metric`, because structural meaning can move through MCP envelopes and future schema fields.
3. Preserve ordinary unique-key JSON compatibility and all existing size/cardinality ceilings.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding still materializes the complete document up to 1 MiB before post-decode structural ceilings apply; executable memory/time profiling remains pending.

## Single best next step
Execute the focused MCP evidence/diagnostic suites in a real checkout and fix any regressions, then perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
