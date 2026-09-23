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
- Reconciled the older focused MCP regression suite with that hardened resource contract so it no longer expects forbidden `resource.data` evidence.

## Latest run — 2026-09-23 — MCP regression-suite consistency

### Inspected at start
Read `progress.md` completely, inspected the repository tree, `runtime/mcp_prometheus_evidence.py`, and `runtime/tests/test_mcp_prometheus_evidence.py`. The implementation correctly rejected URI-less `resource.data`, but the older focused regression suite still contained `test_supports_structured_mcp_content`, which expected that now-forbidden shape to pass. That stale test would make the next executable focused-suite run fail for the wrong reason and contradicted the security invariant established in the previous run.

### Exact changes made
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `e7280bd3a3e98f3636964466609c85c9460f8d9b`.
- Replaced the stale URI-less `resource.data` positive fixture with a standards-shaped EmbeddedResource carrying serialized query JSON in exact-string `resource.text` plus a URI.
- Preserved the rest of the focused evidence regression coverage, including label binding, timestamp/sample semantics, extension smuggling rejection, nesting limits, and hostile-subclass fail-closed tests.
- No implementation behavior was weakened to satisfy an obsolete test; the test was brought into alignment with the pinned upstream contract and current trust boundary.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the regression-suite commit.
- Static consistency review now shows the focused positive EmbeddedResource fixture agrees with the implementation and the dedicated resource-boundary tests.
- This connector runtime still does not provide an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. Never preserve a contradictory test merely because it predates a security hardening; positive fixtures must represent contracts StageGuard intentionally supports.
2. Keep EmbeddedResource compatibility narrow: JSON query evidence may arrive in `resource.text`, not arbitrary resource extensions.
3. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The evidence parser has depth and JSON-text-size limits, but collection cardinality/work limits should be reviewed before treating hostile oversized structured MCP payloads as fully resource-bounded.

## Single best next step
Add explicit work/cardinality ceilings to structured MCP evidence traversal (top-level content items, series, samples, and label counts) with fail-closed regression tests, then execute the focused MCP suite and pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke when a real checkout is available.
