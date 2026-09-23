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
- Standard MCP content blocks are transport envelopes. Text and embedded-resource evidence must come from their actual textual payload; image/audio/resource-link blocks cannot smuggle query evidence through extension fields.
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

## Latest run — 2026-09-23 — official MCP contract alignment

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py`, the embedded-resource regression suite, and the pinned upstream `grafana/mcp-grafana` v1.4.1 `tools/prometheus.go` source. The previous run intentionally retained a URI-less `resource: {data: ...}` compatibility branch pending evidence about the official response contract.

### Exact changes made
- Verified from the pinned upstream v1.4.1 source that `query_prometheus` returns `QueryPrometheusResult` with `Data model.Value` serialized as top-level JSON `data`, plus optional `hints` and `warnings`; the tool itself does not define a URI-less EmbeddedResource result contract.
- Updated `runtime/mcp_prometheus_evidence.py` in commit `9653754c16554dd159ae5aa7ff47ff5ed5d6fdcf` to remove the legacy URI-less `resource.data` acceptance branch. Embedded resources now expose evidence only through exact-string `resource.text`; blobs and arbitrary extension fields fail closed.
- Updated `runtime/tests/test_mcp_resource_evidence_boundary.py` in commit `92fdc00c7e0e8c82007d6d00e56c11bd7b5a22c2` with an explicit regression proving URI-less `resource.data` cannot satisfy the release gate.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation/test commits.
- Upstream source inspection was performed against the exact pinned `grafana/mcp-grafana` v1.4.1 tag, not an inferred/latest contract.
- This connector runtime still does not provide an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. Prefer the exact pinned upstream tool contract over preserving a speculative historical fixture.
2. Treat `QueryPrometheusResult.data` as the canonical structured evidence shape; MCP text/structured envelopes may transport that object, but unrelated resource extension fields cannot create evidence.
3. Keep EmbeddedResource text support as transport tolerance while maintaining a narrow fail-closed boundary.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout. Then run Grafana `13.2.1` + official MCP `1.4.1`, capture a sanitized real `query_prometheus` response to confirm the transport envelope around the now-verified `QueryPrometheusResult` payload, and rerun the release smoke without logging credentials, raw PromQL, or sample values.
