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
- Hardened embedded MCP resources so standards-shaped ResourceContents (`uri` present) only admit JSON evidence through their `text` payload; blob/resource-link extension fields cannot masquerade as telemetry.

## Latest run — 2026-09-23 — MCP embedded-resource boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and its existing regression suite. The prior content-block hardening correctly rejected a `data` sibling on the outer `type: resource` block, but recursively treated the entire inner `resource` object as a generic query-result envelope. A standards-shaped MCP EmbeddedResource could therefore put valid-looking series in an unrelated `resource.data` extension and satisfy StageGuard's release gate even when its real `text`/`blob` payload contained no query evidence.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commits `72976d22215d63767900246ef62854e16e87337f` and `06e1b44a463ebf6cb2c5282c57bd48c399eb952d`.
- Standard `type: resource` blocks now extract evidence only from exact-string `resource.text`; blob resources provide no JSON evidence path.
- `resource_link`, image, and audio content blocks fail closed rather than traversing extension fields.
- Preserved the repository's historical URI-less `resource: {data: ...}` fixture as an explicitly legacy compatibility branch; once a resource has `uri`, it is treated as standards-shaped ResourceContents and arbitrary `data` is ignored.
- Added `runtime/tests/test_mcp_resource_evidence_boundary.py` in commit `103f8318004b487dd4a8b360a59bfc532b896c1e`, covering valid JSON-in-resource-text plus resource-data, blob-data, and resource-link smuggling regressions.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted all implementation/test commits.
- This connector runtime does not expose a repository checkout to Python, so pytest and Docker acceptance were not executed. No runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Model MCP EmbeddedResource according to its payload semantics rather than recursively trusting every inner resource field.
2. Keep blob resources non-evidentiary because decoding arbitrary binary content is unnecessary for the Prometheus release gate.
3. Retain the URI-less historical structured-resource fixture temporarily to avoid silently breaking existing tests before executable validation; remove that compatibility branch after a real official MCP response fixture confirms it is unnecessary.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout. Then run Grafana `13.2.1` + official MCP `1.4.1`, capture a sanitized real `query_prometheus` response, replace the legacy URI-less resource compatibility path with the observed official transport shape, and rerun the release smoke without logging credentials, raw PromQL, or sample values.
