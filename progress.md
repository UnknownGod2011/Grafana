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
- Structured MCP evidence work is bounded by collection cardinality and scalar sizes: transport collections, Prometheus series, samples, label maps, sample-value strings, and label strings have explicit fail-closed ceilings.
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
- Added explicit fail-closed collection/work ceilings for MCP transport collections, Prometheus series, samples, metric labels, and expected-label maps.
- Added explicit scalar-size ceilings for numeric sample strings and metric/expected label names and values so bounded collection counts cannot still carry attacker-sized scalar work.

## Latest run — 2026-09-23 — MCP evidence scalar-size ceilings

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and `runtime/tests/test_mcp_evidence_work_limits.py`. The previous run correctly bounded collection cardinalities, but exact built-in strings inside already-structured MCP payloads remained independently unbounded. In particular, a sample value could force `strip()`/`float()` over an attacker-sized string and label matching could hash/compare attacker-sized names or values repeatedly despite the label-count ceiling.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `bb45ed20507ecd933514cb7551b2c744594e74f3`.
- Added fail-closed scalar ceilings: 128 characters for numeric sample-value strings, 1,024 characters for label names, and 4,096 characters for label values.
- Sample strings are length-checked before `strip()` and numeric conversion.
- Metric labels and caller-supplied expected labels now share one exact-built-in/type-and-size validator before matching.
- Preserved finite numeric semantics, collection ceilings, nesting limits, JSON text limits, exact-built-in checks, expected-label binding, and MCP envelope/resource trust boundaries.
- Extended `runtime/tests/test_mcp_evidence_work_limits.py` in commit `179d27b7ef1bda8a15ee07e2d6b86d70bccbc777` with at-limit/over-limit sample-value coverage and metric/expected-label scalar-bound regressions.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Static review confirms oversized sample strings are rejected before whitespace stripping/float parsing and oversized labels before evidence matching.
- This connector runtime does not expose an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for these connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. Cardinality bounds alone are insufficient for untrusted structured data; per-scalar bounds are part of the same release-gate resource-security invariant.
2. Keep label value allowance materially larger than names to accommodate legitimate media-workflow identifiers while still imposing a deterministic ceiling.
3. Apply the same label constraints to observed metrics and expected labels so caller-controlled matching cannot bypass the resource bound.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding is bounded by input character count but still materializes the complete <=1 MiB document before post-decode structural ceilings apply; executable memory/time profiling remains pending.

## Single best next step
Execute the focused MCP evidence/diagnostic suites in a real checkout and fix any regressions, then perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
